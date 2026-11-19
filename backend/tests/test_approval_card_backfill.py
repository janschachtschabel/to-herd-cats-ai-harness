"""Module review M8 5, L1 (follow-up): an approval card written before the fix carries
its old summary as its text, which could name a string the model chose. The data
migration gives every approval card the text new cards carry, the tool's name, and
touches nothing else; run again, it changes nothing. Run on the test's own
connection, inside its transaction, which is rolled back afterwards."""

import uuid

from alembic import command
from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from app.core.migrations import alembic_config
from app.modules.messaging.models import Message, MessageKind
from tests.factories_tools import call
from tests.factories_writing import Work
from tests.test_approvals import confirm

BEFORE = "7c2e9a4f1b86"
REVISION = "9e4b6d2f8a17"
OLD = "read_ticket: key=Geheim-4711"


def _migrate(connection: Connection) -> None:
    config = alembic_config()
    config.attributes["connection"] = connection
    command.downgrade(config, BEFORE)
    command.upgrade(config, REVISION)
    command.upgrade(config, "head")


async def _bodies(work: Work, *ids: uuid.UUID) -> list[str]:
    stmt = select(Message.id, Message.body_md).where(Message.id.in_(ids))
    found = {row.id: row.body_md for row in await work.bench.session.execute(stmt)}
    return [found[i] for i in ids]


async def test_an_old_approval_card_says_the_tool_only(work: Work) -> None:
    await confirm(work, "read_ticket")
    work.bench.stub.state.replies.extend(
        [call("read_ticket", key="Geheim-4711"), {"content": "Erledigt."}]
    )
    await work.bench.say("Lies das Ticket")
    assert await work.bench.run_next() is None  # waits for the release
    session = work.bench.session
    card = await session.scalar(select(Message).where(Message.kind == MessageKind.APPROVAL))
    asked = await session.scalar(select(Message).where(Message.kind == MessageKind.HUMAN))
    assert card is not None and asked is not None
    ids = (card.id, asked.id)
    await session.execute(update(Message).where(Message.id == ids[0]).values(body_md=OLD))
    await session.flush()  # as a card written before the fix
    connection = await session.connection()
    await connection.run_sync(_migrate)
    session.expire_all()
    assert await _bodies(work, *ids) == ["read_ticket", "Lies das Ticket"]
    await connection.run_sync(_migrate)  # once more: nothing changes
    session.expire_all()
    assert await _bodies(work, *ids) == ["read_ticket", "Lies das Ticket"]
