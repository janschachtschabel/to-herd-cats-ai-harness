#!/usr/bin/env bash
# Behaviour of the chart that lint and kubeconform cannot see. Exits non-zero on the
# first rule that does not hold.
#
#   bash deploy/helm/scripts/check-chart-rules.sh
#   HELM="docker run --rm -v $PWD:$PWD -w $PWD alpine/helm:3.19.0" bash deploy/helm/scripts/check-chart-rules.sh
set -euo pipefail
root="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$root"
chart=deploy/helm/to-herd-cats-ai
read -r -a helm <<<"${HELM:-helm}"

fail() { echo "FAIL: $*" >&2; exit 1; }
render() { "${helm[@]}" template t "$chart" "$@" 2>&1; }

# The session cookie is Secure by default.
out=$(render)
grep -A1 -- "- name: HERD_COOKIE_SECURE" <<<"$out" | grep -q 'value: "true"' \
  || fail "HERD_COOKIE_SECURE is not true by default"

# With an Ingress the trusted proxies must be named, and are then passed on.
if out=$(render --set ingress.enabled=true); then
  fail "ingress.enabled without api.forwardedAllowIps rendered"
fi
grep -q "api.forwardedAllowIps is required" <<<"$out" || fail "unexpected error: $out"
out=$(render --set ingress.enabled=true --set api.forwardedAllowIps=10.0.0.0/8)
grep -A1 -- "- name: HERD_FORWARDED_ALLOW_IPS" <<<"$out" | grep -q '"10.0.0.0/8"' \
  || fail "HERD_FORWARDED_ALLOW_IPS is not passed on"

# Rollouts: the API pod waits before it stops accepting, while the endpoints are
# removed, and the grace period covers that wait plus the drain.
out=$(render)
api=$(awk '/^kind: Deployment/{d=1} d&&/^---/{exit} d' <<<"$out")
grep -q 'command: \["sleep", "5"\]' <<<"$api" || fail "the API has no preStop sleep of 5 s"
grep -q "terminationGracePeriodSeconds: 35" <<<"$api" || fail "the grace period does not cover preStop + 30 s"

# Documents of one kind and name from a render.
doc() { awk -v k="kind: $1" -v n="name: $2" '
  /^---/ { if (hit) exit; buf=""; kind=0; next }
  { buf = buf $0 "\n" }
  $0 == k { kind=1 }
  kind && $0 == "  " n { hit=1 }
  END { if (hit) printf "%s", buf }' <<<"$3"; }

# Live editing: one collab replica, replaced with Recreate (documents live in memory).
out=$(render)
collab=$(doc Deployment t-to-herd-cats-ai-collab "$out")
[[ -n $collab ]] || fail "no collab Deployment by default"
grep -q "replicas: 1$" <<<"$collab" || fail "collab is not one replica"
grep -q "type: Recreate" <<<"$collab" || fail "collab is not replaced with Recreate"
grep -A1 -- "- name: HERD_ROLE" <<<"$collab" | grep -q "value: collab" || fail "collab role not set"
grep -q 'value: "http://t-to-herd-cats-ai-internal:9090"' <<<"$collab" \
  || fail "collab does not reach the API's internal port"
api=$(doc Deployment t-to-herd-cats-ai-api "$out")
grep -q 'value: "ws://t-to-herd-cats-ai-collab:1234"' <<<"$api" || fail "the API does not relay to collab"

# The internal token is never a chart value: generated into a kept Secret, or taken
# from collab.internalToken.existingSecret.
grep -E "^\s+token: " "$chart/values.yaml" && fail "values.yaml carries a token"
secret=$(doc Secret t-to-herd-cats-ai-internal-token "$out")
grep -q "helm.sh/resource-policy: keep" <<<"$secret" || fail "the generated token Secret is not kept"
for workload in "$api" "$collab"; do
  grep -A4 -- "- name: HERD_INTERNAL_TOKEN" <<<"$workload" | grep -q "name: t-to-herd-cats-ai-internal-token" \
    || fail "HERD_INTERNAL_TOKEN does not come from the generated Secret"
done
out=$(render --set collab.internalToken.existingSecret=herd-token)
[[ -z $(doc Secret t-to-herd-cats-ai-internal-token "$out") ]] || fail "token Secret generated despite existingSecret"
grep -A4 -- "- name: HERD_INTERNAL_TOKEN" <<<"$out" | grep -q "name: herd-token" \
  || fail "collab.internalToken.existingSecret is not used"
out=$(render --set collab.enabled=false)
grep -q "HERD_INTERNAL_TOKEN\|HERD_COLLAB_URL" <<<"$out" && fail "live-editing settings without collab"

# HERD_PUBLIC_URL: from the Ingress (https with TLS) unless publicUrl is set.
out=$(render --set ingress.enabled=true --set api.forwardedAllowIps=10.0.0.0/8 \
  --set "ingress.tls[0].secretName=tls" --set "ingress.tls[0].hosts[0]=herd.example.com")
grep -A1 -- "- name: HERD_PUBLIC_URL" <<<"$out" | grep -q '"https://herd.example.com"' \
  || fail "HERD_PUBLIC_URL is not derived from the TLS Ingress"
out=$(render --set publicUrl=https://wiki.example)
grep -A1 -- "- name: HERD_PUBLIC_URL" <<<"$out" | grep -q '"https://wiki.example"' || fail "publicUrl not passed on"

# Files: /data on a claim every API replica can write; one replica may use ReadWriteOnce.
out=$(render)
grep -q "claimName: t-to-herd-cats-ai-data" <<<"$out" || fail "the API does not mount the files claim"
if out=$(render --set "persistence.accessModes={ReadWriteOnce}"); then
  fail "two API replicas on a ReadWriteOnce claim rendered"
fi
grep -q "needs persistence.accessModes \[ReadWriteMany\]" <<<"$out" || fail "unexpected error: $out"
render --set api.replicas=1 --set "persistence.accessModes={ReadWriteOnce}" >/dev/null \
  || fail "one API replica with ReadWriteOnce did not render"

# NetworkPolicy: the collab process takes connections only from the API pods.
out=$(render --set networkPolicy.enabled=true)
policy=$(doc NetworkPolicy t-to-herd-cats-ai-collab "$out")
grep -A3 "ingress:" <<<"$policy" | grep -q "podSelector" || fail "collab ingress is not limited to pods"
grep -B8 "port: 1234" <<<"$policy" | grep -q "app.kubernetes.io/component: api" \
  || fail "collab does not take its port from the API pods"
# The collab process's memory (review M4-1 P12): 1Gi by default, with a modest request;
# its /metrics (memory budget) is scraped like the API's, and the scrapers named in
# internalFrom may reach its port.
out=$(render)
collab=$(doc Deployment t-to-herd-cats-ai-collab "$out")
grep -A4 "limits:" <<<"$collab" | grep -q "memory: 1Gi" || fail "the collab memory limit is not 1Gi"
grep -A3 "requests:" <<<"$collab" | grep -q "memory: 128Mi" || fail "the collab memory request is not 128Mi"
out=$(render --set metrics.serviceMonitor.enabled=true)
service=$(doc Service t-to-herd-cats-ai-collab-metrics "$out")
[[ -n $service ]] || fail "no Service for the collab process's metrics"
grep -q "app.kubernetes.io/endpoint: internal" <<<"$service" || fail "the ServiceMonitor does not select the collab metrics"
grep -A3 "selector:" <<<"$service" | grep -q "app.kubernetes.io/component: collab" || fail "the collab metrics Service selects other pods"
grep -A3 -- "- name: internal" <<<"$service" | grep -q "targetPort: collab" || fail "the collab metrics are not on its port"
out=$(render --set networkPolicy.enabled=true \
  --set 'networkPolicy.internalFrom[0].namespaceSelector.matchLabels.name=monitoring')
policy=$(doc NetworkPolicy t-to-herd-cats-ai-collab "$out")
grep -q "name: monitoring" <<<"$policy" || fail "the scrapers in internalFrom cannot reach the collab metrics"

# The worker (outbox dispatcher, HERD_ROLE=worker): its own Deployment, one replica by
# default, more on request (they claim disjoint batches); probes and metrics on the
# internal port, no public port, no files, no live-editing token. Its container has the
# API's name, so HerdNotReady covers it.
out=$(render)
worker=$(doc Deployment t-to-herd-cats-ai-worker "$out")
[[ -n $worker ]] || fail "no worker Deployment by default"
grep -q "replicas: 1$" <<<"$worker" || fail "the worker is not one replica by default"
grep -A1 -- "- name: HERD_ROLE" <<<"$worker" | grep -q "value: worker$" || fail "worker role not set"
grep -q -- "- name: to-herd-cats-ai$" <<<"$worker" || fail "the worker container is not named to-herd-cats-ai"
grep -A3 "readinessProbe:" <<<"$worker" | grep -q "path: /ready" || fail "the worker's readiness is not /ready"
grep -A4 "readinessProbe:" <<<"$worker" | grep -q "port: internal" || fail "the worker's probes are not on 9090"
grep -B1 "containerPort: 9090" <<<"$worker" | grep -q "name: internal" || fail "the worker has no internal port"
grep -q "containerPort: 8080\|HERD_INTERNAL_TOKEN\|HERD_COLLAB_URL\|mountPath: /data" <<<"$worker" \
  && fail "the worker has a public port, the live-editing token or the files"
grep -q "HERD_DATABASE_PASSWORD_FILE" <<<"$worker" || fail "the worker has no database password"
api=$(doc Deployment t-to-herd-cats-ai-api "$out")
grep -A1 -- "- name: HERD_ROLE" <<<"$api" | grep -q "value: api$" || fail "the API pods do not run role api"
out=$(render --set worker.replicas=3 --set worker.env.HERD_LOG_LEVEL=DEBUG)
worker=$(doc Deployment t-to-herd-cats-ai-worker "$out")
grep -q "replicas: 3$" <<<"$worker" || fail "worker.replicas is not used"
grep -A1 -- "- name: HERD_LOG_LEVEL" <<<"$worker" | grep -q '"DEBUG"' || fail "worker.env is not passed on"

# The worker's metrics are scraped like the API's: a Service on its internal port with
# the label the ServiceMonitor selects.
out=$(render --set metrics.serviceMonitor.enabled=true)
service=$(doc Service t-to-herd-cats-ai-worker "$out")
[[ -n $service ]] || fail "no Service for the worker's metrics"
grep -q "app.kubernetes.io/endpoint: internal" <<<"$service" || fail "the ServiceMonitor does not select the worker Service"
grep -A3 "selector:" <<<"$service" | grep -q "app.kubernetes.io/component: worker" || fail "the worker Service selects other pods"
grep -q "port: 9090" <<<"$service" || fail "the worker Service is not on 9090"

# NetworkPolicy: the worker reaches only the database (plus DNS and networkPolicy.egress)
# and takes connections only on 9090 from internalFrom; the bundled PostgreSQL admits it.
out=$(render --set networkPolicy.enabled=true)
policy=$(doc NetworkPolicy t-to-herd-cats-ai-worker "$out")
[[ -n $policy ]] || fail "no NetworkPolicy for the worker"
grep -A16 "egress:" <<<"$policy" | grep -q "port: 5432" || fail "the worker cannot reach the database"
grep -q "port: 8080\|port: 1234\|component: api\|component: collab" <<<"$policy" \
  && fail "the worker reaches or is reached by more than the database and the scrapes"
grep -q "ingress: \[\]" <<<"$policy" || fail "the worker takes connections without internalFrom"
postgres=$(doc NetworkPolicy t-to-herd-cats-ai-postgresql "$out")
grep -q "values: \[api, migrate, worker\]" <<<"$postgres" || fail "the bundled PostgreSQL does not admit the worker"
out=$(render --set networkPolicy.enabled=true \
  --set "networkPolicy.internalFrom[0].namespaceSelector.matchLabels.team=monitoring")
policy=$(doc NetworkPolicy t-to-herd-cats-ai-worker "$out")
grep -B6 "team: monitoring" <<<"$policy" | grep -q "port: 9090" || fail "internalFrom does not reach the worker's 9090"

# AI and agents (M5, M6): the settings reach the pods that read them (API: connection
# tests and personal agents; worker: runs), the keys come only from the Secret named in
# ai.existingSecret (API and worker, never the migration job, never a ConfigMap or a
# value), and providers are reachable only through networkPolicy.aiEgress.
out=$(render --set ai.runConcurrency=8 --set ai.approvalHours=24 --set ai.personalAgentsMax=2 \
  --set ai.automationsMax=7)
api=$(doc Deployment t-to-herd-cats-ai-api "$out")
worker=$(doc Deployment t-to-herd-cats-ai-worker "$out")
grep -A1 -- "- name: HERD_AI_CHECK_TIMEOUT_SECONDS" <<<"$api" | grep -q 'value: "20"' \
  || fail "the API has no HERD_AI_CHECK_TIMEOUT_SECONDS"
grep -A1 -- "- name: HERD_AI_PERSONAL_AGENTS_MAX" <<<"$api" | grep -q 'value: "2"' \
  || fail "ai.personalAgentsMax does not reach the API"
grep -A1 -- "- name: HERD_AI_AUTOMATIONS_MAX" <<<"$api" | grep -q 'value: "7"' \
  || fail "ai.automationsMax does not reach the API"
grep -A1 -- "- name: HERD_RUN_CONCURRENCY" <<<"$worker" | grep -q 'value: "8"' \
  || fail "ai.runConcurrency does not reach the worker"
grep -A1 -- "- name: HERD_AI_APPROVAL_HOURS" <<<"$worker" | grep -q 'value: "24"' \
  || fail "ai.approvalHours does not reach the worker"
grep -A1 -- "- name: HERD_RUN_LEASE_SECONDS" <<<"$worker" | grep -q 'value: "30"' \
  || fail "the worker has no HERD_RUN_LEASE_SECONDS"
grep -q "HERD_RUN_CONCURRENCY\|HERD_RUN_LEASE_SECONDS" <<<"$api" && fail "the API gets the worker's run settings"
grep -q "envFrom" <<<"$worker" && fail "the worker gets a Secret without ai.existingSecret"
grep -E "^\s+(HERD_SECRET_KEY|HERD_AI_EGRESS_PROXY|secretKey|egressProxy):" "$chart/values.yaml" \
  && fail "values.yaml carries an AI secret"
out=$(render --set ai.existingSecret=herd-ai --set secrets.existingSecret=herd-app)
api=$(doc Deployment t-to-herd-cats-ai-api "$out")
worker=$(doc Deployment t-to-herd-cats-ai-worker "$out")
for workload in "$api" "$worker"; do
  grep -A6 "envFrom:" <<<"$workload" | grep -q "name: herd-ai" || fail "ai.existingSecret is not given to the API and the worker"
done
grep -A6 "envFrom:" <<<"$api" | grep -q "name: herd-app" || fail "secrets.existingSecret is lost beside ai.existingSecret"
grep -q "name: herd-app" <<<"$worker" && fail "the worker gets the bootstrap Secret"
grep -q "herd-ai" <<<"$(doc Job t-to-herd-cats-ai-migrate-1 "$out")" && fail "the migration job gets the AI keys"
grep -q "^kind: ConfigMap" <<<"$out" && fail "a ConfigMap appeared (secrets must stay in Secrets)"
out=$(render --set networkPolicy.enabled=true)
[[ -z $(doc NetworkPolicy t-to-herd-cats-ai-ai-egress "$out") ]] || fail "AI egress is open without networkPolicy.aiEgress"
grep -q "port: 443" <<<"$out" && fail "a NetworkPolicy opens port 443 by default"
out=$(render --set networkPolicy.enabled=true --set 'networkPolicy.aiEgress[0].to[0].ipBlock.cidr=203.0.113.0/24' \
  --set 'networkPolicy.aiEgress[0].ports[0].port=443')
policy=$(doc NetworkPolicy t-to-herd-cats-ai-ai-egress "$out")
[[ -n $policy ]] || fail "no NetworkPolicy for networkPolicy.aiEgress"
grep -q "values: \[api, worker\]" <<<"$policy" || fail "AI egress is not for exactly the API and the worker"
grep -q "cidr: 203.0.113.0/24" <<<"$policy" || fail "networkPolicy.aiEgress is not passed on"
grep -q "policyTypes: \[Egress\]" <<<"$policy" || fail "the AI egress policy restricts more than egress"
grep -q "203.0.113.0/24" <<<"$(doc NetworkPolicy t-to-herd-cats-ai "$out")$(doc NetworkPolicy t-to-herd-cats-ai-worker "$out")" \
  && fail "networkPolicy.aiEgress leaks into the general policies (the migration job)"

# MCP (M8): the access tokens' rate limit reaches the API pods (they serve /mcp) only.
out=$(render)
grep -A1 -- "- name: HERD_MCP_RATE_PER_MINUTE" <<<"$(doc Deployment t-to-herd-cats-ai-api "$out")" \
  | grep -q 'value: "120"' || fail "the API has no HERD_MCP_RATE_PER_MINUTE"
out=$(render --set mcp.ratePerMinute=30)
grep -A1 -- "- name: HERD_MCP_RATE_PER_MINUTE" <<<"$(doc Deployment t-to-herd-cats-ai-api "$out")" \
  | grep -q 'value: "30"' || fail "mcp.ratePerMinute does not reach the API"
grep -q "HERD_MCP_RATE_PER_MINUTE" <<<"$(doc Deployment t-to-herd-cats-ai-worker "$out")" \
  && fail "the worker gets the API's MCP settings"
if render --set mcp.ratePerMinute=0 >/dev/null; then fail "mcp.ratePerMinute=0 rendered"; fi

# MCP (M8 Task 7): private hosts of external MCP servers reach the API (tool lists) and
# the worker (runs), empty by default; nothing but names and networks renders.
out=$(render)
for workload in t-to-herd-cats-ai-api t-to-herd-cats-ai-worker; do
  grep -A1 -- "- name: HERD_MCP_ALLOWED_HOSTS" <<<"$(doc Deployment "$workload" "$out")" \
    | grep -q 'value: ""' || fail "$workload has no empty HERD_MCP_ALLOWED_HOSTS by default"
done
out=$(render --set 'mcp.allowedHosts={gitlab.corp.example,10.20.0.0/16}')
for workload in t-to-herd-cats-ai-api t-to-herd-cats-ai-worker; do
  grep -A1 -- "- name: HERD_MCP_ALLOWED_HOSTS" <<<"$(doc Deployment "$workload" "$out")" \
    | grep -q 'value: "gitlab.corp.example,10.20.0.0/16"' \
    || fail "mcp.allowedHosts does not reach $workload"
done
if render --set 'mcp.allowedHosts={a b}' >/dev/null; then fail "mcp.allowedHosts took a space"; fi

# The outbox and worker alerts (review M3 N3, N4). HerdWorkerAbsent pairs a release's
# API scrape job "<fullname>-internal" with its worker job "<fullname>-worker": the jobs
# are the names of the Services the ServiceMonitor selects, so both must keep them.
out=$(render --set metrics.prometheusRule.enabled=true --set metrics.serviceMonitor.enabled=true)
rule=$(doc PrometheusRule t-to-herd-cats-ai "$out")
for alert in HerdNotReady HerdOutboxBacklog HerdOutboxFailed HerdWorkerStalled HerdWorkerAbsent \
  HerdRunsStuck HerdRunsQueued HerdRunsFailing HerdAutomationsLagging HerdAutomationsFailing; do
  grep -q -- "- alert: $alert$" <<<"$rule" || fail "the PrometheusRule lacks $alert"
done
grep -qF '"$1-internal", "job", "(.+)-worker"' <<<"$rule" \
  || fail "HerdWorkerAbsent does not pair the worker job with the API job"
for name in t-to-herd-cats-ai-internal t-to-herd-cats-ai-worker; do
  service=$(doc Service "$name" "$out")
  [[ -n $service ]] || fail "no Service $name (a scrape job the alerts name)"
  grep -q "app.kubernetes.io/endpoint: internal" <<<"$service" || fail "the ServiceMonitor does not scrape $name"
done
grep -q "HERD_ROLE" <<<"$(doc Deployment t-to-herd-cats-ai-worker "$out")" || fail "no worker to report"

echo "chart rules OK"
