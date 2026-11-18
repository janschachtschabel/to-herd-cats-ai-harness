"""How long the rows of each table stay (plan M9 task 8): one rule per table, and a test
(`tests/test_retention.py`) fails for a table that has none.

- `Keep`: the rows stay until a person, an admin or a cascade from their parent removes
  them; the reason says why nothing removes them on a schedule. Deleting audit, usage
  or run history is the operator's decision (`docs/SICHERUNG.md`).
- `Upkeep`: the worker's due loop removes rows `after` the time `since` names (for the
  generic expiry upkeep, `EXPIRY`, a column of the table); `by` names the code that
  does it (`module:attribute`, resolved by the test).
- `Cleans`: the module that owns the rows removes them itself; `by` names that code.

The catalogue holds names, never imports: `app.core` knows no module. Code whose
retention is fixed here reads its period from it (`upkeep_after`).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta

EXPIRY = "app.worker.upkeep:remove_expired"  # the generic expiry upkeep of the due loop


@dataclass(frozen=True, slots=True)
class Keep:
    reason: str


@dataclass(frozen=True, slots=True)
class Upkeep:
    since: str
    after: timedelta
    by: str


@dataclass(frozen=True, slots=True)
class Cleans:
    by: str
    how: str


type Retention = Keep | Upkeep | Cleans

_CONTENT = "content of the organisation; removed by its people (or the trash) and cascades"
_SETTING = "configuration an admin changes or deletes"
_PROOF = "evidence (spec 12.6); deleting it is the operator's decision (docs/SICHERUNG.md)"

RETENTION: Mapping[str, Retention] = {
    # Identity and organisation (M1)
    "organization": Keep("the installation's tenant; everything else hangs on it"),
    "app_user": Keep(
        "people are deactivated, never deleted (authorship stays readable); only a"
        " rejected sign-up, never active, is deleted (users/removal_repository.py)"
    ),
    "user_group": Keep(_SETTING),
    "group_member": Keep(_SETTING),
    "space": Keep(_CONTENT),
    "space_member": Keep(_SETTING),
    "audit_log": Keep(_PROOF),
    "user_session": Upkeep("expires_at", timedelta(hours=1), EXPIRY),
    "rate_limit_hit": Upkeep("hit_at", timedelta(seconds=60), EXPIRY),
    # Second factor (M9 task 16)
    "user_totp": Keep("the person's own second factor; gone when they or an admin turn it off"),
    "totp_recovery_code": Cleans(
        "app.modules.totp.repository:TotpRepository",
        "each code is deleted by the statement that accepts it; all go with a new set or TOTP",
    ),
    "sign_in_challenge": Upkeep("expires_at", timedelta(0), EXPIRY),
    # Wiki (M2, M9)
    "page": Keep(_CONTENT),
    "page_version": Keep("a page's history; goes with its page"),
    "page_collab_state": Keep("one live-editing state per page; goes with its page"),
    "attachment": Keep(_CONTENT),
    "tag": Keep(_CONTENT),
    "tagging": Keep("goes with its tag or the tagged page or ticket"),
    "collab_grant": Upkeep("expires_at", timedelta(hours=1), EXPIRY),
    # A collab process that stopped beating an hour ago is gone for good (a running
    # one announces itself every 5 s and comes back by itself after a restore).
    "collab_instance": Upkeep("heartbeat_at", timedelta(hours=1), EXPIRY),
    "collab_page_owner": Keep(
        "one binding per page; goes with its page; kept so that its epoch only rises"
    ),
    "storage_tombstone": Upkeep(
        "buried_at", timedelta(hours=48), "app.core.storage_tombstones:remove_buried"
    ),
    # Messaging (M3)
    "conversation": Keep(_CONTENT),
    "conversation_participant": Keep("who is in a conversation; goes with it"),
    "conversation_read": Keep("one read position per person and conversation"),
    "message": Keep(_CONTENT),
    "message_mention": Keep("goes with its message"),
    "reaction": Keep("goes with its message"),
    "notification": Keep(
        "the person's own inbox; read and done are states, nothing deletes one but its"
        " message, thread, proposal or account going"
    ),
    "dm_inspection": Keep(_PROOF),
    "event_outbox": Cleans(
        "app.worker.dispatcher:Dispatcher.cleanup",
        "7 days after dispatch; failed events stay for the operator (`herd_outbox_failed`)",
    ),
    "event_lane": Cleans(
        "app.worker.repository:OutboxRepository.drop_lanes",
        "removed when its handler has had the event; goes with the event",
    ),
    "event_delivery": Cleans(
        "app.worker.repository:OutboxRepository.delete_dispatched_before",
        "goes with its event (cascade)",
    ),
    # Tickets (M4, M4b)
    "work_item": Keep(_CONTENT),
    "ticket_status": Keep(_SETTING),
    "ticket_counter": Keep("one counter per organisation: a ticket number is never reused"),
    "ticket_page_link": Keep("goes with its ticket or page"),
    "sprint": Keep(_CONTENT),
    # AI (M5)
    "ai_connection": Keep(_SETTING),
    "ai_org_assignment": Keep(_SETTING),
    "ai_group_assignment": Keep(_SETTING),
    "ai_user_assignment": Keep(_SETTING),
    "ai_budget": Keep(_SETTING),
    "ai_rate_window": Upkeep("window_start", timedelta(hours=1), EXPIRY),
    "usage_record": Keep(_PROOF),
    # Agents (M5, M6)
    "agent": Keep(_SETTING),
    "agent_tool": Keep(_SETTING),
    "agent_skill": Keep(_SETTING),
    "agent_memory": Keep("the agent's memory page reference; goes with agent or space"),
    "run": Keep(_PROOF),
    "run_event": Keep(_PROOF),
    "run_cancel_request": Keep("who stopped a run; goes with the run"),
    "run_question": Keep("part of a run's record; goes with the run"),
    "approval": Keep("part of a run's record; goes with the run"),
    "page_proposal": Keep("decided proposals are the record of an agent's edit"),
    "skill": Keep(_CONTENT),
    "skill_version": Keep("a skill's history; goes with its skill"),
    "skill_proposal": Keep("decided proposals are the record of an agent's edit"),
    # Automations (M7)
    "automation": Keep(_SETTING),
    "automation_firing": Upkeep(
        "fired_at",
        timedelta(days=90),
        "app.modules.automations.upkeep_repository:UpkeepRepository.delete_terms_before",
    ),
    "automation_event": Upkeep(
        "the fired_at of the term that took it",
        timedelta(days=7),
        "app.modules.automations.upkeep_repository:UpkeepRepository.delete_events_taken_before",
    ),
    # MCP (M8)
    "access_token": Keep("expired and revoked tokens stay listed: their calls name them"),
    "mcp_call": Upkeep(
        "created_at", timedelta(days=90), "app.modules.mcp_tools.repository:delete_calls_before"
    ),
    "mcp_server": Keep(_SETTING),
    "mcp_server_tool": Keep("a server's approved tools; go with the server"),
    "mcp_setting": Keep(_SETTING),
    "connector": Keep(_SETTING),
    "oauth_client": Keep(_SETTING),
    "oauth_flow": Upkeep("expires_at", timedelta(0), EXPIRY),
    # Operations and sign-in (M9)
    "backup_run": Keep("a row per backup: the history the backup gauges read, ~1 a day"),
    "maintenance": Keep("one row per organisation: whether it is in maintenance (M9b)"),
    "oidc_provider": Keep(_SETTING),
    "oidc_flow": Upkeep("expires_at", timedelta(0), EXPIRY),
    "user_identity": Keep("a person's link to a sign-in provider; she or an admin unlinks"),
    # Calendars (M10)
    "calendar": Keep(_CONTENT + "; archived calendars stay (their events and links point at them)"),
    "calendar_setting": Keep(_SETTING),
}


def upkeep_after(table: str) -> timedelta:
    """The period after which the due loop removes `table`'s rows."""
    rule = RETENTION[table]
    if not isinstance(rule, Upkeep):
        raise TypeError(f"{table} has no upkeep rule")
    return rule.after
