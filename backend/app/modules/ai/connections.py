"""AI connections (spec 7.1): set up, changed, checked and removed by holders of
`ai.manage`; everyone else gets 404 (`access.require_ai`).

- A base URL passes the egress rules of the connection's kind when it is written
  (`egress.check_base_url`) and again on every call (the guard in the client).
- A secret arrives as a value (stored as `enc:`) or as an `env:HERD_AI_*` name. It is
  never in an answer, an audit entry or a log line: audit details name fields, and for
  the secret only its kind (`secret: "enc" | "env" | null`).
- Checking a connection and listing its models talk to the provider with no
  transaction open (no pooled connection held while a provider answers slowly).
- Every write names the version it read (409 `ai.connection_version_conflict`).
"""

import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import egress, secrets
from app.core.access import Action, Actor
from app.core.config import get_settings
from app.core.errors import AppError, Conflict, NotFound, ValidationFailed
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.ai import provider
from app.modules.ai.access import require_ai
from app.modules.ai.models import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    AiConnection,
    ConnectionKind,
    DataLocation,
    ParamFamily,
    Purpose,
)
from app.modules.ai.provider import CheckStatus, ProviderFailure, Target
from app.modules.ai.repository import ConnectionRepository
from app.modules.ai.schemas import ConnectionCreate, ConnectionUpdate, SecretIn
from app.modules.audit.recorder import changes, record, snapshot

# Fields an update may change, besides the secret; audited by name and value.
_FIELDS = (
    "name",
    "base_url",
    "models",
    "param_family",
    "extra_body",
    "supports_tools",
    "data_location",
    "max_concurrency",
    "requests_per_minute",
    "purpose",
    "enabled",
)


class ProviderFailed(AppError):
    """The provider did not give what was asked; `details.status` says why."""

    status_code = 502
    code = "ai.provider_failed"


def connection_not_found() -> NotFound:
    return NotFound(code="ai.connection_not_found")


class ConnectionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def repo(self, actor: Actor) -> ConnectionRepository:
        return ConnectionRepository(self.session, actor.org_id)

    async def list(self, actor: Actor, params: PageParams) -> Page[AiConnection]:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.repo(actor).page(after, params.limit + 1)
        return id_page(rows, params.limit, lambda c: c.id)

    async def get(self, actor: Actor, connection_id: uuid.UUID) -> AiConnection:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        return _found(await self.repo(actor).get(connection_id))

    async def create(self, actor: Actor, data: ConnectionCreate) -> AiConnection:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        kind = data.kind
        openai = kind == ConnectionKind.OPENAI
        base_url = _base_url(data.base_url or DEFAULT_BASE_URL, kind)
        repo = self.repo(actor)
        await repo.lock_names()
        if await repo.name_taken(data.name):
            raise Conflict(code="ai.connection_name_taken")
        connection = await repo.add(
            AiConnection(
                org_id=actor.org_id,
                name=data.name,
                kind=kind,
                base_url=base_url,
                secret_ref=_secret_ref(data.secret),
                models=data.models if data.models is not None else _default_models(kind),
                param_family=data.param_family
                or (ParamFamily.MAX_COMPLETION_TOKENS if openai else ParamFamily.MAX_TOKENS),
                extra_body=data.extra_body or {},
                supports_tools=data.supports_tools,
                data_location=data.data_location
                or (DataLocation.LOCAL if kind == ConnectionKind.LOCAL else DataLocation.EXTERNAL),
                max_concurrency=data.max_concurrency,
                requests_per_minute=data.requests_per_minute,
                purpose=data.purpose,
                enabled=data.enabled,
            )
        )
        details = {**snapshot(connection, _FIELDS), "kind": kind}
        details["secret"] = _secret_kind(connection)
        await self._audit(actor, "ai_connection.created", connection, details)
        return connection

    async def update(
        self, actor: Actor, connection_id: uuid.UUID, data: ConnectionUpdate
    ) -> AiConnection:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        repo = self.repo(actor)
        if "name" in data.model_fields_set:
            await repo.lock_names()
        connection = await self._current(repo, connection_id, data.version)
        if data.name is not None and await repo.name_taken(data.name, other_than=connection.id):
            raise Conflict(code="ai.connection_name_taken")
        before = snapshot(connection, _FIELDS)
        for name in data.model_fields_set & set(_FIELDS):
            value = getattr(data, name)
            if name == "base_url":
                value = _base_url(value, connection.kind)
            setattr(connection, name, value)
        details: dict[str, Any] = {"changes": changes(before, connection)}
        if "secret" in data.model_fields_set:
            connection.secret_ref = _secret_ref(data.secret)
            details["secret"] = _secret_kind(connection)
        connection.version += 1
        await self.session.flush()
        await self._audit(actor, "ai_connection.updated", connection, details)
        return connection

    async def delete(self, actor: Actor, connection_id: uuid.UUID, version: int) -> None:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        repo = self.repo(actor)
        connection = await self._current(repo, connection_id, version)
        details = {"name": connection.name}
        await repo.delete(connection)
        await self._audit(actor, "ai_connection.deleted", connection, details)

    async def check(
        self, actor: Actor, connection_id: uuid.UUID, model: str | None
    ) -> tuple[CheckStatus, str | None, int]:
        """(status, model tried, duration in ms)."""
        connection = await self.get(actor, connection_id)
        model = model or next(iter(connection.models), None)
        target = _target(connection)
        await self.session.commit()  # nothing held while the provider answers
        if model is None:
            return CheckStatus.NO_MODEL, None, 0
        started = _now_ms()
        status = await provider.check(target, model, get_settings().ai_check_timeout_seconds)
        return status, model, _now_ms() - started

    async def fetch_models(
        self, actor: Actor, connection_id: uuid.UUID, version: int
    ) -> AiConnection:
        """Replace the models with those the provider lists; the standard model stays
        first if it is still listed."""
        connection = await self.get(actor, connection_id)
        _check_version(connection, version)
        target = _target(connection)
        await self.session.commit()  # nothing held while the provider answers
        try:
            listed = await provider.list_models(target, get_settings().ai_check_timeout_seconds)
        except ProviderFailure as failure:
            raise ProviderFailed(details={"status": failure.status.value}) from None
        connection = await self._current(self.repo(actor), connection_id, version)
        models = sorted({m.strip()[:200] for m in listed})[:500]
        standard = next(iter(connection.models), None)
        if standard in models:
            models = [standard, *(m for m in models if m != standard)]
        before = snapshot(connection, ("models",))
        connection.models = models
        connection.version += 1
        await self.session.flush()
        details = {"changes": changes(before, connection)}
        await self._audit(actor, "ai_connection.models_listed", connection, details)
        return connection

    async def _current(
        self, repo: ConnectionRepository, connection_id: uuid.UUID, version: int
    ) -> AiConnection:
        connection = _found(await repo.get(connection_id, lock=True))
        _check_version(connection, version)
        return connection

    async def _audit(
        self, actor: Actor, action: str, connection: AiConnection, details: dict[str, Any]
    ) -> None:
        await record(self.session, actor, action, "ai_connection", connection.id, details)


def _default_models(kind: ConnectionKind) -> list[str]:
    return [DEFAULT_MODEL] if kind == ConnectionKind.OPENAI else []


def _found(connection: AiConnection | None) -> AiConnection:
    if connection is None:
        raise connection_not_found()
    return connection


def _check_version(connection: AiConnection, version: int) -> None:
    if connection.version != version:
        raise Conflict(
            code="ai.connection_version_conflict",
            details={"current_version": connection.version},
        )


def _base_url(url: str, kind: ConnectionKind) -> str:
    try:
        return egress.check_base_url(url, provider.rules_for(ConnectionKind(kind)))
    except egress.EgressBlocked as blocked:
        details = {"reason": blocked.reason}
        raise ValidationFailed(code="ai.base_url_not_allowed", details=details) from None


def _secret_ref(secret: SecretIn | None) -> str | None:
    if secret is None:
        return None
    if secret.env is not None:
        return secrets.env_ref(secret.env)
    assert secret.value is not None
    return secrets.encrypt(secret.value.get_secret_value())


def _secret_kind(connection: AiConnection) -> str | None:
    ref = connection.secret_ref
    return secrets.kind_of(ref).value if ref is not None else None


def _target(connection: AiConnection) -> Target:
    return Target(
        kind=ConnectionKind(connection.kind),
        base_url=connection.base_url,
        secret_ref=connection.secret_ref,
        param_family=ParamFamily(connection.param_family),
        extra_body=dict(connection.extra_body),
        purpose=Purpose(connection.purpose),
    )


def _now_ms() -> int:
    return round(time.monotonic() * 1000)
