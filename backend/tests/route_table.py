"""Every `/api` route with the guard it needs (`test_route_table.py` checks the list is
complete and the session and CSRF guards, `test_route_hiding.py` the hiding ones).

A new route that is not listed fails `test_every_api_route_is_listed`, so it cannot
ship without a decision on who may call it. Guards:
- `public`: no session needed (login; logout, which only ends the session it is sent
  with and answers 204 without one).
- `session`: any logged-in person; anonymous → 401.
- `admin`: an administration right; members and guests → 403
  (`test_route_guards.py` checks every one of these).
- `space`: a role in the space; anonymous → 401, a member without a role in a team
  space → 404 (the space's existence is not revealed).
- `page`: a role in the page's space; a member without a role in a team space gets
  404 `page.not_found`, as for an unknown page.
- `conversation`: whoever may see the conversation (a channel: its space); a member
  without a role in a team space gets 404 `conversation.not_found`.
- `message`: whoever may see the message's conversation; otherwise 404
  `message.not_found`.
- `ticket`: a role in the ticket's space; otherwise 404 `ticket.not_found`, as for a
  number nobody has.
- `ticket_status`: a role in the status's space; otherwise 404
  `ticket_status.not_found`.
- `sprint`: a role in the sprint's space; otherwise 404 `sprint.not_found`, as for an
  id nobody has (plan M4b).
- `ai`: an AI right (`ai.manage`); everyone else gets 404 `ai.not_found`, so people
  without it learn nothing about the AI set-up (plan M5).
Every unsafe method also needs the CSRF header (→ 403 `auth.csrf`).
"""

from uuid_utils.compat import uuid7

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

# (method, template, guard)
ROUTES: list[tuple[str, str, str]] = [
    ("POST", "/api/auth/login", "public"),
    ("POST", "/api/auth/logout", "public"),
    ("GET", "/api/auth/me", "session"),
    ("PATCH", "/api/auth/me", "session"),
    ("POST", "/api/auth/me/password", "session"),
    ("GET", "/api/directory", "session"),
    ("GET", "/api/spaces", "session"),
    ("POST", "/api/spaces", "session"),
    ("GET", "/api/spaces/{space_id}", "space"),
    ("PATCH", "/api/spaces/{space_id}", "space"),
    ("GET", "/api/spaces/{space_id}/members", "space"),
    ("PUT", "/api/spaces/{space_id}/members", "space"),
    ("DELETE", "/api/spaces/{space_id}/members/{member_type}/{member_id}", "space"),
    ("GET", "/api/spaces/{space_id}/pages/tree", "space"),
    ("POST", "/api/spaces/{space_id}/pages", "space"),
    ("GET", "/api/spaces/{space_id}/pages/by-path", "space"),
    ("GET", "/api/pages/{page_id}", "page"),
    ("PATCH", "/api/pages/{page_id}", "page"),
    ("POST", "/api/pages/{page_id}/publish", "page"),
    ("PUT", "/api/pages/{page_id}/ai-lock", "page"),
    ("POST", "/api/pages/{page_id}/move", "page"),
    ("POST", "/api/pages/{page_id}/trash", "page"),
    ("POST", "/api/pages/{page_id}/restore", "page"),
    ("GET", "/api/spaces/{space_id}/trash", "space"),
    ("DELETE", "/api/pages/{page_id}", "admin"),  # purge: page.purge (system admins)
    ("GET", "/api/pages/{page_id}/versions", "page"),
    ("GET", "/api/pages/{page_id}/versions/{number}", "page"),
    ("PATCH", "/api/pages/{page_id}/versions/{number}", "page"),
    ("POST", "/api/pages/{page_id}/versions/{number}/restore", "page"),
    ("GET", "/api/pages/{page_id}/diff", "page"),
    ("PUT", "/api/pages/{page_id}/tags", "page"),
    ("POST", "/api/pages/{page_id}/attachments", "page"),
    ("GET", "/api/pages/{page_id}/attachments", "page"),
    ("GET", "/api/attachments/{attachment_id}", "session"),
    ("DELETE", "/api/attachments/{attachment_id}", "session"),
    ("PUT", "/api/attachments/{attachment_id}/ai-lock", "session"),
    ("POST", "/api/spaces/{space_id}/import", "space"),
    ("GET", "/api/spaces/{space_id}/export", "space"),
    ("GET", "/api/pages/{page_id}/export", "page"),
    ("GET", "/api/pages/{page_id}/thread", "page"),  # the page's discussion
    ("GET", "/api/tags", "session"),
    ("GET", "/api/search", "session"),
    ("POST", "/api/tags", "session"),  # system tags: tag.manage; space tags: page.moderate
    ("PATCH", "/api/tags/{tag_id}", "session"),
    ("DELETE", "/api/tags/{tag_id}", "session"),
    ("GET", "/api/spaces/{space_id}/channels", "space"),
    ("POST", "/api/spaces/{space_id}/channels", "space"),
    ("GET", "/api/channels", "session"),
    ("GET", "/api/conversations/{conversation_id}", "conversation"),
    ("PATCH", "/api/conversations/{conversation_id}", "conversation"),
    ("POST", "/api/conversations/{conversation_id}/archive", "conversation"),
    ("POST", "/api/conversations/{conversation_id}/unarchive", "conversation"),
    ("GET", "/api/conversations/{conversation_id}/messages", "conversation"),
    ("POST", "/api/conversations/{conversation_id}/messages", "conversation"),
    ("GET", "/api/messages/{message_id}", "message"),
    ("GET", "/api/messages/{message_id}/replies", "message"),
    ("PATCH", "/api/messages/{message_id}", "message"),
    ("DELETE", "/api/messages/{message_id}", "message"),
    ("GET", "/api/conversations/unread", "session"),
    ("POST", "/api/conversations/{conversation_id}/read", "conversation"),
    ("PUT", "/api/messages/{message_id}/reactions/{emoji}", "message"),
    ("DELETE", "/api/messages/{message_id}/reactions/{emoji}", "message"),
    ("GET", "/api/activity", "session"),
    ("GET", "/api/activity/count", "session"),
    ("POST", "/api/activity/read-all", "session"),
    ("POST", "/api/activity/{notification_id}/read", "session"),
    ("POST", "/api/activity/{notification_id}/done", "session"),
    ("POST", "/api/dms", "session"),
    ("GET", "/api/dms", "session"),
    ("GET", "/api/admin/dm-inspect", "admin"),
    ("POST", "/api/admin/dm-inspect", "admin"),
    ("GET", "/api/admin/dm-inspect/{inspection_id}/messages", "admin"),
    ("POST", "/api/spaces/{space_id}/tickets", "space"),
    ("GET", "/api/tickets", "session"),
    ("GET", "/api/tickets/counts", "session"),
    ("GET", "/api/spaces/{space_id}/board", "space"),
    ("GET", "/api/spaces/{space_id}/board/{status_id}", "space"),
    ("GET", "/api/spaces/{space_id}/epics", "space"),
    ("GET", "/api/tickets/{number}", "ticket"),
    ("PATCH", "/api/tickets/{number}", "ticket"),
    ("GET", "/api/tickets/{number}/thread", "ticket"),  # the ticket's discussion
    ("PUT", "/api/tickets/{number}/tags", "ticket"),
    ("GET", "/api/tickets/{number}/pages", "ticket"),
    ("PUT", "/api/tickets/{number}/pages/{page_id}", "ticket"),
    ("DELETE", "/api/tickets/{number}/pages/{page_id}", "ticket"),
    ("GET", "/api/pages/{page_id}/tickets", "page"),
    ("GET", "/api/spaces/{space_id}/ticket-statuses", "space"),
    ("POST", "/api/spaces/{space_id}/ticket-statuses", "space"),
    ("PATCH", "/api/ticket-statuses/{status_id}", "ticket_status"),
    ("DELETE", "/api/ticket-statuses/{status_id}", "ticket_status"),
    ("GET", "/api/spaces/{space_id}/sprints", "space"),
    ("POST", "/api/spaces/{space_id}/sprints", "space"),
    ("PATCH", "/api/sprints/{sprint_id}", "sprint"),
    ("POST", "/api/sprints/{sprint_id}/start", "sprint"),
    ("POST", "/api/sprints/{sprint_id}/close", "sprint"),
    ("GET", "/api/stream", "session"),  # live delivery (server-sent events)
    ("GET", "/api/admin/audit", "admin"),
    ("GET", "/api/admin/users", "admin"),
    ("POST", "/api/admin/users", "admin"),
    ("PATCH", "/api/admin/users/{user_id}", "admin"),
    ("POST", "/api/admin/users/{user_id}/deactivate", "admin"),
    ("POST", "/api/admin/users/{user_id}/reactivate", "admin"),
    ("GET", "/api/admin/groups", "admin"),
    ("POST", "/api/admin/groups", "admin"),
    ("GET", "/api/admin/groups/{group_id}", "admin"),
    ("PATCH", "/api/admin/groups/{group_id}", "admin"),
    ("DELETE", "/api/admin/groups/{group_id}", "admin"),
    ("GET", "/api/admin/groups/{group_id}/members", "admin"),
    ("POST", "/api/admin/groups/{group_id}/members", "admin"),
    ("DELETE", "/api/admin/groups/{group_id}/members/{member_type}/{member_id}", "admin"),
    ("GET", "/api/ai/connections", "ai"),
    ("POST", "/api/ai/connections", "ai"),
    ("GET", "/api/ai/connections/{connection_id}", "ai"),
    ("PATCH", "/api/ai/connections/{connection_id}", "ai"),
    ("DELETE", "/api/ai/connections/{connection_id}", "ai"),
    ("POST", "/api/ai/connections/{connection_id}/test", "ai"),
    ("POST", "/api/ai/connections/{connection_id}/models", "ai"),
    ("GET", "/api/ai/assignments", "ai"),
    ("PUT", "/api/ai/assignments/default", "ai"),
    ("GET", "/api/ai/assignments/groups", "ai"),
    ("PUT", "/api/ai/assignments/groups", "ai"),
    ("GET", "/api/ai/assignments/users", "ai"),
    ("PUT", "/api/ai/assignments/users/{user_id}", "ai"),
    ("DELETE", "/api/ai/assignments/users/{user_id}", "ai"),
    ("GET", "/api/ai/usage", "ai"),
    ("GET", "/api/ai/usage/me", "ai"),
]


def concrete(
    template: str,
    space_id: object | None = None,
    page_id: object | None = None,
    conversation_id: object | None = None,
    message_id: object | None = None,
    status_id: object | None = None,
    sprint_id: object | None = None,
) -> str:
    versioned_delete = template in (
        "/api/ai/connections/{connection_id}",
        "/api/ai/assignments/users/{user_id}",
    )
    ids = {
        "{message_id}": str(message_id or uuid7()),
        "{conversation_id}": str(conversation_id or uuid7()),
        "{space_id}": str(space_id or uuid7()),
        "{page_id}": str(page_id or uuid7()),
        "{user_id}": str(uuid7()),
        "{group_id}": str(uuid7()),
        "{member_type}": "user",
        "{member_id}": str(uuid7()),
        "{number}": "1",
        "{tag_id}": str(uuid7()),
        "{attachment_id}": str(uuid7()),
        "{inspection_id}": str(uuid7()),
        "{emoji}": "%F0%9F%91%8D",
        "{notification_id}": str(uuid7()),
        "{status_id}": str(status_id or uuid7()),
        "{connection_id}": str(uuid7()),
        "{sprint_id}": str(sprint_id or uuid7()),
    }
    for name, value in ids.items():
        template = template.replace(name, value)
    queries = {
        "/by-path": "?path=x",
        "/diff": "?from=1&to=1",
        "/attachments": "?filename=x.txt",
        "/dm-inspect": f"?user_id={uuid7()}",
    }
    if "/ticket-statuses/" in template or versioned_delete:
        return template + "?version=1"
    return template + next((q for end, q in queries.items() if template.endswith(end)), "")


# A valid body for every route that takes one, so the guard is what answers.
BODIES: dict[tuple[str, str], dict[str, object]] = {
    ("PATCH", "/api/spaces/{space_id}"): {"name": "X", "version": 1},
    ("PUT", "/api/spaces/{space_id}/members"): {
        "member_type": "user",
        "member_id": str(uuid7()),
        "role": "viewer",
    },
    ("POST", "/api/spaces/{space_id}/pages"): {"title": "X"},
    ("PATCH", "/api/pages/{page_id}"): {"title": "X", "version": 1},
    ("POST", "/api/pages/{page_id}/publish"): {"version": 1},
    ("PUT", "/api/pages/{page_id}/ai-lock"): {"no_ai": True, "version": 1},
    ("PUT", "/api/attachments/{attachment_id}/ai-lock"): {"no_ai": True, "version": 1},
    ("POST", "/api/pages/{page_id}/move"): {"parent_id": None, "version": 1},
    ("POST", "/api/pages/{page_id}/trash"): {"version": 1},
    ("PATCH", "/api/pages/{page_id}/versions/{number}"): {"label": "X"},
    ("POST", "/api/pages/{page_id}/versions/{number}/restore"): {"version": 1},
    ("PUT", "/api/pages/{page_id}/tags"): {"tag_ids": [], "version": 1},
    ("POST", "/api/spaces/{space_id}/channels"): {"name": "x"},
    ("PATCH", "/api/conversations/{conversation_id}"): {"topic": "x", "version": 1},
    ("POST", "/api/conversations/{conversation_id}/archive"): {"version": 1},
    ("POST", "/api/conversations/{conversation_id}/unarchive"): {"version": 1},
    ("POST", "/api/conversations/{conversation_id}/messages"): {"body_md": "x"},
    ("PATCH", "/api/messages/{message_id}"): {"body_md": "x"},
    ("POST", "/api/conversations/{conversation_id}/read"): {"message_id": str(uuid7())},
    ("POST", "/api/spaces/{space_id}/tickets"): {"title": "X"},
    ("PATCH", "/api/tickets/{number}"): {"title": "X", "version": 1},
    ("PUT", "/api/tickets/{number}/tags"): {"tag_ids": [], "version": 1},
    ("POST", "/api/spaces/{space_id}/ticket-statuses"): {"name": "X", "category": "open"},
    ("PATCH", "/api/ticket-statuses/{status_id}"): {"name": "X", "version": 1},
    ("POST", "/api/spaces/{space_id}/sprints"): {
        "name": "X",
        "starts_on": "2026-11-16",
        "ends_on": "2026-11-27",
    },
    ("PATCH", "/api/sprints/{sprint_id}"): {"name": "X", "version": 1},
    ("POST", "/api/sprints/{sprint_id}/start"): {"version": 1},
    ("POST", "/api/sprints/{sprint_id}/close"): {"version": 1, "move_open_to": "backlog"},
    ("POST", "/api/ai/connections"): {"name": "X"},
    ("PATCH", "/api/ai/connections/{connection_id}"): {"name": "X", "version": 1},
    ("POST", "/api/ai/connections/{connection_id}/models"): {"version": 1},
    ("PUT", "/api/ai/assignments/default"): {"target": None, "version": 1},
    ("PUT", "/api/ai/assignments/groups"): {"items": [], "version": 1},
    ("PUT", "/api/ai/assignments/users/{user_id}"): {"no_ai": True, "version": None},
}
