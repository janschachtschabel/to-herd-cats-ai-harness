"""The notification checks the invitations widen (plan M10 task 4, decision 7): the
migration replaces `ck_notification_reason` and `ck_notification_target` with wider
ones (`contract_of` the released revision, so `check_migrations` lets the drops pass).
Every (reason, target) a row could hold before the migration holds after it: each
released reason with every combination of set and unset target columns is judged by
the old conditions (as the migration names them, which are the previous head's) and
by the constraints the database holds now."""

import importlib.util
import itertools
from pathlib import Path
from types import ModuleType

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.check_migrations import ALEMBIC, check, load, released_revision

VERSIONS = ALEMBIC / "versions"
TARGETS = (
    "message_id",
    "conversation_id",
    "proposal_id",
    "skill_proposal_id",
    "space_id",
    "automation_id",
    "account_id",
)
CALENDAR_REASONS = {
    "invitation",
    "invite_reply",
    "event_reminder",
    "event_proposal",
    "calendar_sync",
}


def _module(name: str) -> ModuleType:
    (path,) = [p for p in VERSIONS.glob(f"*_{name}.py")]
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _released_conditions() -> tuple[str, str]:
    """The checks before the migration, as the revisions that made them wrote them."""
    lock, signup = _module("m9_totp_lock"), _module("m9_signup_approval")
    return f"reason IN ({lock.NOTIFY}, 'totp_locked')", str(signup.WIDER_TARGET)


async def _check(session: AsyncSession, name: str) -> str:
    found = await session.scalar(
        text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :name"),
        {"name": name},
    )
    assert isinstance(found, str) and found.startswith("CHECK ")
    return found.removeprefix("CHECK ")


async def test_the_widened_notification_checks_accept_every_released_row(
    session: AsyncSession,
) -> None:
    attendees = _module("m10_attendees")
    old_reason, old_target = _released_conditions()
    assert (attendees.BEFORE_REASONS, attendees.BEFORE_TARGET) == (old_reason, old_target)
    reason_now = await _check(session, "ck_notification_reason")
    target_now = await _check(session, "ck_notification_target")
    reasons = [r.strip(" '") for r in old_reason.removeprefix("reason IN (").rstrip(")").split(",")]
    assert len(reasons) == 13
    judged = 0
    for reason in [*reasons, *sorted(CALENDAR_REASONS)]:
        for bits in itertools.product((False, True), repeat=len(TARGETS)):
            values = ", ".join(
                f"{'gen_random_uuid()' if bit else 'NULL::uuid'} AS {name}"
                for name, bit in zip(TARGETS, bits, strict=True)
            )
            row = (
                f"SELECT CAST(:reason AS text) AS reason, NULL::uuid AS calendar_event_id, {values}"
            )
            before, after = (
                await session.execute(
                    text(
                        f"SELECT ({old_reason}) AND ({old_target}),"
                        f" ({reason_now}) AND ({target_now}) FROM ({row}) AS notification"
                    ),
                    {"reason": reason},
                )
            ).one()
            if before:
                judged += 1
                assert after, (reason, bits)
    assert judged > 13  # every released reason, each with its targets
    for reason in CALENDAR_REASONS:
        stmt = text(
            f"SELECT ({reason_now}) FROM (SELECT CAST(:r AS text) AS reason) AS notification"
        )
        assert (await session.execute(stmt, {"r": reason})).scalar_one()


def test_the_migration_contracts_only_the_released_checks() -> None:
    released = released_revision(ALEMBIC / "RELEASED")
    assert check(VERSIONS, released) == []
    revisions = {r.path.name: r for r in load(VERSIONS).values()}
    (mine,) = [r for name, r in revisions.items() if name.endswith("_m10_attendees.py")]
    assert mine.contract_of == released
    assert "only widens" in (Path(mine.path).read_text())
