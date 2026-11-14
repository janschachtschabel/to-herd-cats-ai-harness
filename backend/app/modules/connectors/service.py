"""Connectors (plan M8 decision 9, task 5).

- Shared connectors are the organisation's: holders of `ai.manage` set them up; anyone
  else gets 404 `ai.not_found`, as for the other AI administration.
- Personal connectors are one person's: only that person (with `ai.use`) sees and
  changes them; for everyone else, admins included, one is 404
  `connector.not_found`, as for an unknown id. Without `ai.use`: 404 `ai.not_found`.
- A secret arrives as a value (stored as `enc:`) or, for a shared connector only, as an
  `env:HERD_AI_*` name. It is never in an answer, an audit entry or a log line: audit
  details name the changed fields and, for the secret, only its kind.
- Every write names the version it read (409 `connector.version_conflict`).
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.access import Action, Actor
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.core.principal import PrincipalType
from app.modules.ai.access import ai_not_found, require_ai
from app.modules.ai.schemas import SecretIn
from app.modules.audit.recorder import record
from app.modules.connectors.models import AuthKind, Connector, ConnectorScope
from app.modules.connectors.repository import ConnectorRepository
from app.modules.connectors.schemas import ConnectorCreate, ConnectorUpdate, check_auth

_FIELDS = ("name", "auth_kind", "header_name")


def connector_not_found() -> NotFound:
    return NotFound(code="connector.not_found")


class ConnectorService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def repo(self, actor: Actor, scope: ConnectorScope) -> ConnectorRepository:
        """The connectors `actor` may manage in `scope`, after checking the right."""
        if scope == ConnectorScope.SHARED:
            await require_ai(self.session, actor, Action.AI_MANAGE)
            return ConnectorRepository(self.session, actor.org_id, None)
        if actor.principal.type != PrincipalType.USER:
            raise ai_not_found()
        await require_ai(self.session, actor, Action.AI_USE)
        return ConnectorRepository(self.session, actor.org_id, actor.principal.id)

    async def list(
        self, actor: Actor, scope: ConnectorScope, params: PageParams
    ) -> Page[Connector]:
        repo = await self.repo(actor, scope)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await repo.page(after, params.limit + 1)
        return id_page(rows, params.limit, lambda c: c.id)

    async def get(self, actor: Actor, scope: ConnectorScope, connector_id: uuid.UUID) -> Connector:
        repo = await self.repo(actor, scope)
        return _found(await repo.get(connector_id))

    async def create(self, actor: Actor, scope: ConnectorScope, data: ConnectorCreate) -> Connector:
        repo = await self.repo(actor, scope)
        await repo.lock_names()
        if await repo.name_taken(data.name):
            raise Conflict(code="connector.name_taken")
        connector = await repo.add(
            Connector(
                org_id=actor.org_id,
                scope=scope,
                owner_id=repo.owner_id,
                name=data.name,
                auth_kind=data.auth_kind,
                header_name=data.header_name,
                secret_ref=_secret_ref(data.secret, scope),
            )
        )
        details = {
            "scope": scope.value,
            "auth_kind": data.auth_kind.value,
            "secret": secrets.kind_of(connector.secret_ref).value,
        }
        await self._audit(actor, "connector.created", connector, details)
        return connector

    async def update(
        self,
        actor: Actor,
        scope: ConnectorScope,
        connector_id: uuid.UUID,
        data: ConnectorUpdate,
    ) -> Connector:
        repo = await self.repo(actor, scope)
        if "name" in data.model_fields_set:
            await repo.lock_names()
        connector = await self._current(repo, connector_id, data.version)
        if data.name is not None and await repo.name_taken(data.name, other_than=connector.id):
            raise Conflict(code="connector.name_taken")
        changed: set[str] = set()
        for name in data.model_fields_set & set(_FIELDS):
            value = getattr(data, name)
            if getattr(connector, name) != value:
                setattr(connector, name, value)
                changed.add(name)
        try:
            check_auth(AuthKind(connector.auth_kind), connector.header_name)
        except ValueError:
            raise ValidationFailed(code="connector.header_name_invalid") from None
        details: dict[str, Any] = {}
        if data.secret is not None:
            connector.secret_ref = _secret_ref(data.secret, scope)
            changed.add("secret")
            details["secret"] = secrets.kind_of(connector.secret_ref).value
        connector.version += 1
        await self.session.flush()
        await self._audit(
            actor, "connector.updated", connector, {"fields": sorted(changed), **details}
        )
        return connector

    async def delete(
        self, actor: Actor, scope: ConnectorScope, connector_id: uuid.UUID, version: int
    ) -> None:
        repo = await self.repo(actor, scope)
        connector = await self._current(repo, connector_id, version)
        await repo.delete(connector)
        await self._audit(actor, "connector.deleted", connector, {"scope": scope.value})

    async def _current(
        self, repo: ConnectorRepository, connector_id: uuid.UUID, version: int
    ) -> Connector:
        connector = _found(await repo.get(connector_id, lock=True))
        if connector.version != version:
            raise Conflict(
                code="connector.version_conflict",
                details={"current_version": connector.version},
            )
        return connector

    async def _audit(
        self, actor: Actor, action: str, connector: Connector, details: dict[str, Any]
    ) -> None:
        await record(self.session, actor, action, "connector", connector.id, details)


def _found(connector: Connector | None) -> Connector:
    if connector is None:
        raise connector_not_found()
    return connector


def _secret_ref(secret: SecretIn, scope: ConnectorScope) -> str:
    if secret.env is not None:
        if scope == ConnectorScope.PERSONAL:
            raise ValidationFailed(code="connector.env_not_allowed")
        return secrets.env_ref(secret.env)
    assert secret.value is not None
    return secrets.encrypt(secret.value.get_secret_value())
