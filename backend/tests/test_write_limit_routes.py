"""Every unsafe `/api` route has a decision on the write limit per person (J10, review
M9b Task 18 R18-5): it is counted (`COUNTED`, on its router or at the route, once), or
it is on the commented list below. A new route that is neither fails this test, so it
cannot ship unlimited without anybody deciding it (the calendar's routes, say). Upload
routes are marked at the route (`UPLOAD`), never found by their path."""

from fastapi.routing import APIRoute, iter_route_contexts

from app.modules.auth.write_limits import count_write, is_upload
from app.web.public import create_public_app

UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Writes that count in the upload area instead of the write area.
UPLOADS = frozenset(
    {
        ("POST", "/api/pages/{page_id}/attachments"),
        ("POST", "/api/spaces/{space_id}/import"),
        ("POST", "/api/skills/import"),
    }
)

EXEMPT: frozenset[tuple[str, str]] = frozenset(
    {
        # Signing in and out, and the person's own account, sessions and second factor: not
        # content; the login limits guard what needs guarding (the touch is R18-4).
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/login/second-factor"),
        ("POST", "/api/auth/logout"),
        ("PATCH", "/api/auth/me"),
        ("DELETE", "/api/auth/me/identities/{identity_id}"),
        ("POST", "/api/auth/me/identities/{key}/link"),
        ("POST", "/api/auth/me/password"),
        ("POST", "/api/auth/me/sessions/sign-out-others"),
        ("DELETE", "/api/auth/me/sessions/{session_id}"),
        ("POST", "/api/auth/me/totp/confirm"),
        ("POST", "/api/auth/me/totp/disable"),
        ("POST", "/api/auth/me/totp/recovery-codes"),
        ("POST", "/api/auth/me/totp/setup"),
        ("POST", "/api/auth/me/touch"),
        # Read markers and notifications: they store no content.
        ("POST", "/api/activity/read-all"),
        ("POST", "/api/activity/{notification_id}/done"),
        ("POST", "/api/activity/{notification_id}/read"),
        ("POST", "/api/conversations/{conversation_id}/read"),
        # Administration (people, groups, providers, DM inspection, backups): admins only.
        ("POST", "/api/admin/dm-inspect"),
        ("POST", "/api/admin/groups"),
        ("PATCH", "/api/admin/groups/{group_id}"),
        ("DELETE", "/api/admin/groups/{group_id}"),
        ("POST", "/api/admin/groups/{group_id}/members"),
        ("DELETE", "/api/admin/groups/{group_id}/members/{member_type}/{member_id}"),
        ("POST", "/api/admin/oidc-providers"),
        ("PATCH", "/api/admin/oidc-providers/{provider_id}"),
        ("DELETE", "/api/admin/oidc-providers/{provider_id}"),
        ("POST", "/api/admin/oidc-providers/{provider_id}/check"),
        ("POST", "/api/admin/users"),
        ("PATCH", "/api/admin/users/{user_id}"),
        ("POST", "/api/admin/users/{user_id}/approve"),
        ("POST", "/api/admin/users/{user_id}/deactivate"),
        ("DELETE", "/api/admin/users/{user_id}/identities/{identity_id}"),
        ("POST", "/api/admin/users/{user_id}/reactivate"),
        ("POST", "/api/admin/users/{user_id}/reject"),
        ("POST", "/api/admin/users/{user_id}/sign-out"),
        ("POST", "/api/admin/users/{user_id}/totp/reset"),
        ("POST", "/api/backups"),
        ("POST", "/api/backups/archives"),
        ("POST", "/api/backups/archives/{name}/check"),
        ("POST", "/api/backups/archives/{name}/replace"),
        # AI configuration (connections, assignments, budgets, connectors, MCP servers, OAuth
        # apps, access tokens) and agents' setup: configuration, not content.
        ("POST", "/api/agents"),
        ("PATCH", "/api/agents/{agent_id}"),
        ("DELETE", "/api/agents/{agent_id}"),
        ("PUT", "/api/agents/{agent_id}/skills"),
        ("POST", "/api/agents/{agent_id}/tokens"),
        ("DELETE", "/api/agents/{agent_id}/tokens/{token_id}"),
        ("PUT", "/api/agents/{agent_id}/tools"),
        ("PUT", "/api/ai/assignments/default"),
        ("PUT", "/api/ai/assignments/groups"),
        ("PUT", "/api/ai/assignments/personal-agents"),
        ("PUT", "/api/ai/assignments/users/{user_id}"),
        ("DELETE", "/api/ai/assignments/users/{user_id}"),
        ("PUT", "/api/ai/budgets/agents/{agent_id}"),
        ("PUT", "/api/ai/budgets/organisation"),
        ("PUT", "/api/ai/budgets/users/{user_id}"),
        ("DELETE", "/api/ai/budgets/{budget_id}"),
        ("POST", "/api/ai/connections"),
        ("PATCH", "/api/ai/connections/{connection_id}"),
        ("DELETE", "/api/ai/connections/{connection_id}"),
        ("POST", "/api/ai/connections/{connection_id}/models"),
        ("POST", "/api/ai/connections/{connection_id}/test"),
        ("POST", "/api/ai/connectors"),
        ("PATCH", "/api/ai/connectors/{connector_id}"),
        ("DELETE", "/api/ai/connectors/{connector_id}"),
        ("POST", "/api/ai/connectors/{connector_id}/authorize"),
        ("POST", "/api/ai/connectors/{connector_id}/disconnect"),
        ("PUT", "/api/ai/mcp"),
        ("POST", "/api/ai/mcp-catalog/{entry_id}/install"),
        ("POST", "/api/ai/mcp-servers"),
        ("PATCH", "/api/ai/mcp-servers/{server_id}"),
        ("DELETE", "/api/ai/mcp-servers/{server_id}"),
        ("POST", "/api/ai/mcp-servers/{server_id}/refresh"),
        ("POST", "/api/ai/mcp-servers/{server_id}/test"),
        ("PATCH", "/api/ai/mcp-servers/{server_id}/tools/{tool_id}"),
        ("POST", "/api/ai/mcp-servers/{server_id}/tools/{tool_id}/approve"),
        ("POST", "/api/ai/mcp-servers/{server_id}/tools/{tool_id}/block"),
        ("DELETE", "/api/ai/mcp/tokens/{token_id}"),
        ("POST", "/api/ai/my-connectors"),
        ("PATCH", "/api/ai/my-connectors/{connector_id}"),
        ("DELETE", "/api/ai/my-connectors/{connector_id}"),
        ("POST", "/api/ai/my-connectors/{connector_id}/authorize"),
        ("POST", "/api/ai/my-connectors/{connector_id}/disconnect"),
        ("POST", "/api/ai/oauth-clients"),
        ("POST", "/api/ai/oauth-clients/discover"),
        ("PATCH", "/api/ai/oauth-clients/{client_id}"),
        ("DELETE", "/api/ai/oauth-clients/{client_id}"),
        ("POST", "/api/tokens"),
        ("DELETE", "/api/tokens/{token_id}"),
        # A space's settings, members and ticket statuses: configuration by the space's admins
        # (creating a space counts).
        ("PATCH", "/api/spaces/{space_id}"),
        ("PUT", "/api/spaces/{space_id}/members"),
        ("DELETE", "/api/spaces/{space_id}/members/{member_type}/{member_id}"),
        ("POST", "/api/spaces/{space_id}/ticket-statuses"),
        ("PATCH", "/api/ticket-statuses/{status_id}"),
        ("DELETE", "/api/ticket-statuses/{status_id}"),
        # Automations' setup (a manual run counts): configuration; a term's firing counts when
        # its run writes (`writing.effect`).
        ("POST", "/api/automations"),
        ("POST", "/api/automations/preview"),
        ("PATCH", "/api/automations/{automation_id}"),
        ("DELETE", "/api/automations/{automation_id}"),
        ("POST", "/api/automations/{automation_id}/pause"),
        ("POST", "/api/automations/{automation_id}/resume"),
        ("POST", "/api/automations/{automation_id}/take-over"),
        # Deciding on an agent's work (approvals, cancelling a run): no content of the person's;
        # what the run then writes counts on the agent's own key.
        ("POST", "/api/approvals/{approval_id}/decide"),
        ("POST", "/api/runs/{run_id}/cancel"),
    }
)


def _unsafe_routes() -> dict[tuple[str, str], tuple[int, bool]]:
    """(method, path) of every unsafe `/api` route: how often it is counted, and whether
    it is marked an upload."""
    found = {}
    for context in iter_route_contexts(create_public_app().routes):
        route = context.original_route
        path = context.path
        if not isinstance(route, APIRoute) or not path.startswith("/api") or "/_test" in path:
            continue
        counted = sum(1 for d in context.dependencies if d.dependency is count_write)
        for method in route.methods & UNSAFE:
            found[(method, path)] = (counted, is_upload(route))
    return found


def test_every_unsafe_route_is_counted_or_exempt() -> None:
    routes = _unsafe_routes()
    undecided = {key for key, (counted, _) in routes.items() if not counted} - EXEMPT
    assert not undecided, f"count these writes or exempt them with a reason: {sorted(undecided)}"
    both = {key for key, (counted, _) in routes.items() if counted} & EXEMPT
    assert not both, f"counted, yet listed as exempt: {sorted(both)}"
    assert EXEMPT <= routes.keys(), f"exempt but gone: {sorted(EXEMPT - routes.keys())}"


def test_no_route_counts_twice() -> None:
    twice = {key for key, (counted, _) in _unsafe_routes().items() if counted > 1}
    assert not twice


def test_the_routes_the_review_named_count() -> None:
    routes = _unsafe_routes()
    for key in (
        ("POST", "/api/skills"),
        ("PATCH", "/api/skills/{skill_id}"),
        ("POST", "/api/skills/{skill_id}/archive"),
        ("POST", "/api/skills/{skill_id}/unarchive"),
        ("POST", "/api/skills/{skill_id}/versions/{number}/restore"),
        ("POST", "/api/spaces"),
        ("POST", "/api/automations/{automation_id}/run"),
        ("POST", "/api/questions/{question_id}/answer"),
        ("POST", "/api/conversations/{conversation_id}/fresh-start"),
    ):
        assert routes[key][0] == 1, key


def test_uploads_are_marked_at_the_route_and_counted() -> None:
    routes = _unsafe_routes()
    marked = {key for key, (_, upload) in routes.items() if upload}
    assert marked == UPLOADS
    assert all(routes[key][0] == 1 for key in UPLOADS)
