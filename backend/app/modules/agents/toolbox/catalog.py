"""Every tool a run can have (plan M6 decision 3), with the lowest autonomy level
whose default allows it (1 reads, 2 proposes, 3 writes inside; spec 8.2) and its
effect. A tool that is not listed here can never run: a run offers only listed tools
its grants allow (`policy.py`), and a call to any other name is a bad call.

To add a tool: write its arguments' model and its `run` (see `base.py`; reading tools
in `reading.py`, `listing.py`, `conversation.py`, `past_runs.py`,
`skill_tools.py`), and list it here
with its description, level and effect. A writing tool writes through the services
with `ctx.actor` in `ctx.session` (its effect and its journal entry commit together);
it checks its rights itself, before it writes.
"""

from app.core.permissions import Action
from app.modules.agents.toolbox import (
    conversation,
    listing,
    message_tools,
    past_runs,
    questions,
    reading,
    skill_tools,
    ticket_tools,
    wiki_tools,
)
from app.modules.agents.toolbox.base import Effect, ToolSpec

READ = Effect.READ
PROPOSE = Effect.PROPOSE
WRITE = Effect.WRITE

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
            "load_skill",
            "Load one of the skills listed in your instructions by its name: its text, in "
            "parts when it is long (part=2 and on, as the text says).",
            skill_tools.LoadSkillArgs,
            skill_tools.load_skill,
            1,
            READ,
        ),
        ToolSpec(
            "ask_user",
            "Ask the person you work for a question you cannot answer yourself, and wait "
            "for the answer (it may take a while). Ask only what you need to go on.",
            questions.AskUserArgs,
            questions.ask_user,
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
        ToolSpec(
            "propose_page_change",
            "Propose new content for a wiki page (by its id): your full Markdown and a short "
            "reason. A moderator accepts or rejects it.",
            wiki_tools.ProposePageChangeArgs,
            wiki_tools.propose_page_change,
            2,
            PROPOSE,
            wiki_tools.page_subjects,
            Action.PAGE_EDIT,
        ),
        ToolSpec(
            "propose_new_page",
            "Propose a new wiki page in a space (under parent_id, or at the top): title, "
            "Markdown and a short reason. A moderator accepts or rejects it.",
            wiki_tools.ProposeNewPageArgs,
            wiki_tools.propose_new_page,
            2,
            PROPOSE,
            wiki_tools.new_page_subjects,
            Action.PAGE_EDIT,
        ),
        ToolSpec(
            "comment_ticket",
            "Comment on a ticket (by its key, such as HC-12) in its thread.",
            ticket_tools.CommentTicketArgs,
            ticket_tools.comment_ticket,
            2,
            WRITE,
            ticket_tools.ticket_subjects,
            Action.CHANNEL_POST,
        ),
        ToolSpec(
            "set_ticket_status",
            "Set a ticket's status (by its key) to one of its space's statuses, by name. You "
            "may set statuses up to review; done and cancelled are set by people.",
            ticket_tools.SetTicketStatusArgs,
            ticket_tools.set_ticket_status,
            2,
            WRITE,
            ticket_tools.ticket_subjects,
            Action.TICKET_EDIT,
        ),
        ToolSpec(
            "create_ticket",
            "Create a ticket in a space: title, Markdown description, kind, priority and "
            "optionally a parent ticket's key. Returns its key.",
            ticket_tools.CreateTicketArgs,
            ticket_tools.create_ticket,
            2,
            WRITE,
            ticket_tools.create_subjects,
            Action.TICKET_CREATE,
        ),
        ToolSpec(
            "link_ticket_page",
            "Link a wiki page (by its id) to a ticket (by its key).",
            ticket_tools.LinkTicketPageArgs,
            ticket_tools.link_ticket_page,
            2,
            WRITE,
            ticket_tools.link_subjects,
            Action.TICKET_EDIT,
        ),
        ToolSpec(
            "update_page",
            "Change a wiki page's content directly (only where the space allows it). First "
            "call without token: you get the diff and a token. Then call again with the same "
            "content, reason and that token to save.",
            wiki_tools.UpdatePageArgs,
            wiki_tools.update_page,
            3,
            WRITE,
            wiki_tools.update_subjects,
            Action.PAGE_EDIT,
        ),
        ToolSpec(
            "assign_ticket",
            "Assign a ticket (by its key) to a person or an agent (type and id), with the "
            "reason for the handover, which is posted in the ticket's thread.",
            ticket_tools.AssignTicketArgs,
            ticket_tools.assign_ticket,
            3,
            WRITE,
            ticket_tools.ticket_subjects,
            Action.TICKET_ASSIGN,
        ),
        ToolSpec(
            "post_message",
            "Post a message in the conversation you answer in (reply_to: a message id), or "
            "in a channel of a space you belong to.",
            message_tools.PostMessageArgs,
            message_tools.post_message,
            3,
            WRITE,
            message_tools.post_subjects,
            Action.CHANNEL_POST,
        ),
    )
}


def offered() -> list[ToolSpec]:
    """The tools a run offers the model, in the catalog's order."""
    return list(CATALOG.values())
