# Chart rules for the settings that close ASVS gaps (plan M9 Task 18): each reaches the
# pods that read it, with its default, and a value set reaches them. Sourced by
# check-chart-rules.sh (uses its render, doc and fail).

# J7: the idle limit of login sessions, API pods alone.
out=$(render)
api=$(doc Deployment t-to-herd-cats-ai-api "$out")
grep -A1 -- "- name: HERD_SESSION_IDLE_HOURS" <<<"$api" | grep -q 'value: "24"' \
  || fail "the API lacks HERD_SESSION_IDLE_HOURS (24 by default)"
grep -q "HERD_SESSION_IDLE_HOURS" <<<"$(doc Deployment t-to-herd-cats-ai-worker "$out")" \
  && fail "the worker gets the idle limit"
out=$(render --set api.sessionIdleHours=0)
grep -A1 -- "- name: HERD_SESSION_IDLE_HOURS" <<<"$(doc Deployment t-to-herd-cats-ai-api "$out")" \
  | grep -q 'value: "0"' || fail "api.sessionIdleHours does not reach the API"
if render --set api.sessionIdleHours=-1 >/dev/null; then fail "api.sessionIdleHours took -1"; fi
