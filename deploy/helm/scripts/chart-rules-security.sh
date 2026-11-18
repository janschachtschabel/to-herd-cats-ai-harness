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

# J11: the optional clamd address reaches the API alone (empty by default), a bad one is
# refused, and its egress policy is the API's, only with networkPolicy.enabled.
out=$(render)
grep -A1 -- "- name: HERD_CLAMAV_ADDRESS" <<<"$(doc Deployment t-to-herd-cats-ai-api "$out")" \
  | grep -q 'value: ""' || fail "the API lacks HERD_CLAMAV_ADDRESS (empty by default)"
grep -q "HERD_CLAMAV_ADDRESS" <<<"$(doc Deployment t-to-herd-cats-ai-worker "$out")" \
  && fail "the worker gets the clamd address"
out=$(render --set virusScan.clamavAddress=clamav.tools.svc:3310)
grep -A1 -- "- name: HERD_CLAMAV_ADDRESS" <<<"$(doc Deployment t-to-herd-cats-ai-api "$out")" \
  | grep -q 'value: "clamav.tools.svc:3310"' || fail "virusScan.clamavAddress does not reach the API"
if render --set virusScan.clamavAddress=clamav >/dev/null; then fail "virusScan.clamavAddress took a host without port"; fi
out=$(render --set networkPolicy.enabled=true)
[[ -z $(doc NetworkPolicy t-to-herd-cats-ai-virus-scan-egress "$out") ]] || fail "clamd egress is open without virusScan.egress"
out=$(render --set networkPolicy.enabled=true --set 'virusScan.egress[0].ports[0].port=3310')
policy=$(doc NetworkPolicy t-to-herd-cats-ai-virus-scan-egress "$out")
[[ -n $policy ]] || fail "no NetworkPolicy for virusScan.egress"
grep -A6 "podSelector:" <<<"$policy" | grep -q "app.kubernetes.io/component: api$" || fail "clamd egress is not the API's"
grep -q "port: 3310" <<<"$policy" || fail "virusScan.egress is not passed on"
out=$(render --set 'virusScan.egress[0].ports[0].port=3310')
if grep -q "^kind: NetworkPolicy" <<<"$out"; then
  fail "virusScan.egress renders a policy without networkPolicy.enabled"
fi
