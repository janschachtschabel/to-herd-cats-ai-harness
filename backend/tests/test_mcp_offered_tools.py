"""Plan M8 decisions 1 and 3: `/mcp` offers the catalog's own tools, not a second
list; a `read` token only reading ones."""

from app.modules.agents.toolbox.base import Effect
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.mcp_tools.exposed import READ_TOOLS, WRITE_TOOLS, tools_for
from app.modules.tokens.models import TokenMode


def test_every_offered_tool_is_the_catalogs_own() -> None:
    for mode in TokenMode:
        for tool in tools_for(mode):
            assert CATALOG[tool.name] is tool.spec
            assert tool.run is tool.spec.run, tool.name


def test_a_read_token_gets_reading_tools_only() -> None:
    assert tools_for(TokenMode.READ) == READ_TOOLS
    assert all(tool.spec.effect == Effect.READ and tool.read_only for tool in READ_TOOLS)


def test_no_tool_that_needs_a_run_or_a_release() -> None:
    offered = {tool.name for mode in TokenMode for tool in tools_for(mode)}
    run_bound = {
        "ask_user",
        "submit_result",
        "read_conversation",
        "search_past_runs",
        "load_skill",
        "update_memory",
        "propose_skill",
        "assign_ticket",
    }
    assert not offered & run_bound


def test_a_write_token_gets_the_writing_tools_of_decision_3() -> None:
    assert tools_for(TokenMode.WRITE) == READ_TOOLS + WRITE_TOOLS
    assert {tool.name for tool in WRITE_TOOLS} == {
        "propose_page_change",
        "propose_new_page",
        "comment_ticket",
        "set_ticket_status",
        "create_ticket",
        "link_ticket_page",
        "update_page",
        "post_message",
    }
    assert not any(tool.read_only for tool in WRITE_TOOLS)


def test_every_schema_is_closed() -> None:
    for tool in READ_TOOLS + WRITE_TOOLS:
        schema = tool.input_schema()
        assert schema["type"] == "object"
        assert schema.get("additionalProperties") is False, tool.name
