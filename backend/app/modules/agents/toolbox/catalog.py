"""Every tool a run can have (plan M6 decision 3), with the lowest autonomy level
whose default allows it (1 reads, 2 proposes, 3 writes inside; spec 8.2) and its
effect. A tool that is not listed here can never run: a run offers only listed tools
its grants allow (`policy.py`), and a call to any other name is a bad call.

To add a tool: write its arguments' model and its `run` (see `base.py`; reading tools
in `reading.py`, `listing.py`, `conversation.py`, `past_runs.py`), and list it here
with its description, level and effect. A writing tool writes through the services
with `ctx.actor` in `ctx.session` (its effect and its journal entry commit together);
it checks its rights itself, before it writes.
"""

from app.modules.agents.toolbox import conversation, listing, past_runs, reading
from app.modules.agents.toolbox.base import Effect, ToolSpec

READ = Effect.READ

CATALOG: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec(
            "search",
            "Full-text search in the wiki pages and tickets you may read. Returns the best "
            "hits with type, id or key, title, space and a short snippet.",
            reading.SearchArgs,
            reading.search,
            1,
            READ,
        ),
        ToolSpec(
            "read_page",
            "Read one wiki page by its id (from a search hit). Returns its Markdown.",
            reading.ReadPageArgs,
            reading.read_page,
            1,
            READ,
        ),
        ToolSpec(
            "read_ticket",
            "Read one ticket by its key (such as HC-12). Returns its fields and text.",
            reading.ReadTicketArgs,
            reading.read_ticket,
            1,
            READ,
        ),
        ToolSpec(
            "list_tree",
            "Without space_id: the spaces you may read, with their ids. With space_id: that "
            "space's wiki pages by path (ids, paths, titles; no content). A long tree comes "
            "in pages: pass the cursor you were given to get the next one.",
            listing.ListTreeArgs,
            listing.list_tree,
            1,
            READ,
        ),
        ToolSpec(
            "list_versions",
            "The saved versions of one wiki page by its id, newest first: number, time, "
            "author, label and change summary (no content).",
            listing.ListVersionsArgs,
            listing.list_versions,
            1,
            READ,
        ),
        ToolSpec(
            "search_tickets",
            "Find tickets by text and filters (status categories, assigned to the person "
            "who asked or to nobody, kind, priority, space). Returns key, title, status, "
            "priority and assignee, last changed first.",
            listing.SearchTicketsArgs,
            listing.search_tickets,
            1,
            READ,
        ),
        ToolSpec(
            "read_conversation",
            "Read the conversation you are answering in: its newest messages, older ones "
            "with before (a message id), or the replies to one message with replies_to.",
            conversation.ReadConversationArgs,
            conversation.read_conversation,
            1,
            READ,
        ),
        ToolSpec(
            "search_past_runs",
            "Search your earlier work for the person who asks: what you read and said in "
            "earlier runs, as far as you may still read it here.",
            past_runs.SearchPastRunsArgs,
            past_runs.search_past_runs,
            1,
            READ,
        ),
        ToolSpec(
            "submit_result",
            "Hand in your result: its text becomes your answer and ends your work. Call it "
            "alone, as your last step.",
            conversation.SubmitResultArgs,
            conversation.submit_result,
            1,
            READ,
        ),
    )
}


def offered() -> list[ToolSpec]:
    """The tools a run offers the model, in the catalog's order."""
    return list(CATALOG.values())
