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

# J10: the write limit reaches the API (writes and uploads) and the worker (agents'
# writes, not uploads).
out=$(render)
api=$(doc Deployment t-to-herd-cats-ai-api "$out")
worker=$(doc Deployment t-to-herd-cats-ai-worker "$out")
grep -A1 -- "- name: HERD_WRITE_RATE_PER_MINUTE" <<<"$api" | grep -q 'value: "120"' \
  || fail "the API lacks HERD_WRITE_RATE_PER_MINUTE (120 by default)"
grep -A1 -- "- name: HERD_UPLOAD_RATE_PER_MINUTE" <<<"$api" | grep -q 'value: "30"' \
  || fail "the API lacks HERD_UPLOAD_RATE_PER_MINUTE (30 by default)"
grep -A1 -- "- name: HERD_WRITE_RATE_PER_MINUTE" <<<"$worker" | grep -q 'value: "120"' \
  || fail "the worker lacks HERD_WRITE_RATE_PER_MINUTE (agents count like people)"
grep -q "HERD_UPLOAD_RATE_PER_MINUTE" <<<"$worker" && fail "the worker gets the upload limit"
out=$(render --set writeLimit.perMinute=600 --set writeLimit.uploadsPerMinute=60)
for name in api worker; do
  grep -A1 -- "- name: HERD_WRITE_RATE_PER_MINUTE" <<<"$(doc Deployment "t-to-herd-cats-ai-$name" "$out")" \
    | grep -q 'value: "600"' || fail "writeLimit.perMinute does not reach the $name"
done
grep -A1 -- "- name: HERD_UPLOAD_RATE_PER_MINUTE" <<<"$(doc Deployment t-to-herd-cats-ai-api "$out")" \
  | grep -q 'value: "60"' || fail "writeLimit.uploadsPerMinute does not reach the API"
if render --set writeLimit.perMinute=0 >/dev/null; then fail "writeLimit.perMinute took 0"; fi
