"""A retention rule for every table (plan M9 task 8): the catalogue `app/core/retention.py`
names one for each, every rule's code exists, and the periods the code reads are the
catalogue's. The generic expiry upkeep of the due loop has a test per table in
`tests/test_retention_upkeep.py`."""

import importlib
from datetime import timedelta

from sqlalchemy import DateTime

from app.core.ratelimit import WINDOW
from app.core.retention import EXPIRY, RETENTION, Cleans, Keep, Upkeep, upkeep_after
from app.core.storage_tombstones import GRACE
from app.models_registry import Base
from app.modules.auth.service import ENDED_SESSION_KEEP
from app.modules.wiki.collab_grants import EXPIRED_GRANT_KEEP
from app.worker.due import EVENT_RETENTION, FIRING_RETENTION, MCP_CALL_RETENTION


def _resolve(ref: str) -> object:
    module, _, path = ref.partition(":")
    found: object = importlib.import_module(module)
    for name in path.split("."):
        found = getattr(found, name)
    return found


def test_every_table_has_a_retention_rule() -> None:
    tables = set(Base.metadata.tables)
    missing = sorted(tables - set(RETENTION))
    assert missing == [], f"tables without a retention rule in app/core/retention.py: {missing}"
    assert sorted(set(RETENTION) - tables) == [], "rules for tables that do not exist"


def test_every_rule_names_code_that_exists_or_a_reason() -> None:
    for table, rule in RETENTION.items():
        match rule:
            case Keep(reason):
                assert reason.strip(), table
            case Upkeep(_, after, by):
                assert after >= timedelta(0), table
                assert callable(_resolve(by)), table
            case Cleans(by, how):
                assert callable(_resolve(by)) and how.strip(), table


def test_expiry_rules_name_a_timestamp_column_of_their_table() -> None:
    expiring = {t: r for t, r in RETENTION.items() if isinstance(r, Upkeep) and r.by == EXPIRY}
    assert set(expiring) >= {
        "user_session",
        "oauth_flow",
        "oidc_flow",
        "collab_grant",
        "rate_limit_hit",
        "ai_rate_window",
    }
    for table, rule in expiring.items():
        column = Base.metadata.tables[table].c[rule.since]
        assert isinstance(column.type, DateTime) and column.type.timezone, table


def test_the_code_reads_its_periods_from_the_catalogue() -> None:
    assert upkeep_after("user_session") == ENDED_SESSION_KEEP
    assert upkeep_after("collab_grant") == EXPIRED_GRANT_KEEP
    assert upkeep_after("rate_limit_hit") == WINDOW
    assert upkeep_after("storage_tombstone") == GRACE
    assert upkeep_after("mcp_call") == MCP_CALL_RETENTION
    assert upkeep_after("automation_firing") == FIRING_RETENTION
    assert upkeep_after("automation_event") == EVENT_RETENTION
