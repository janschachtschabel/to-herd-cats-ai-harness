"""The activity view's query stays one sound statement (review M7, finding 14): for a
reader who sees no automations (no `ai.use`), the part about automations is a plain
false, not a sub-select whose conditions SQLAlchemy drops into a cartesian product."""

import warnings

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SAWarning
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.compiler import COLLECT_CARTESIAN_PRODUCTS, WARN_LINTING

from app.modules.messaging.activity import ActivityService
from app.modules.messaging.notification_models import Notification
from tests.factories_wiki import Wiki
from tests.test_access import actor_of


async def test_the_activity_of_a_reader_without_ai_has_no_cartesian_product(
    wiki: Wiki, session: AsyncSession
) -> None:
    viewer = await actor_of(session, wiki.users["viewer"])
    repo = await ActivityService(session)._repo(viewer)
    assert not repo.automations.sees
    stmt = select(Notification.id).where(repo._mine())
    dialect = postgresql.dialect()
    with warnings.catch_warnings():
        warnings.simplefilter("error", SAWarning)
        dialect.statement_compiler(dialect, stmt, linting=COLLECT_CARTESIAN_PRODUCTS | WARN_LINTING)
