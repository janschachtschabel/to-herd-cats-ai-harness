# Chart rules for scaling (plan M9 Task 7, decision 19): HorizontalPodAutoscalers for the
# API and the worker, PodDisruptionBudgets from two replicas, and the files claim with
# autoscaled API pods. Sourced by check-chart-rules.sh (uses its render, doc and fail).

# No autoscaler by default: the Deployments carry their replicas.
out=$(render)
grep -q "^kind: HorizontalPodAutoscaler" <<<"$out" && fail "an autoscaler without autoscaling.enabled"
grep -q "^  replicas: 2$" <<<"$(doc Deployment t-to-herd-cats-ai-api "$out")" || fail "the API has no replicas by default"

# api.autoscaling: autoscaling/v2 on CPU (70 % of the request), 2 to 6 pods by default;
# the Deployment then leaves replicas to the autoscaler (an upgrade would reset them).
out=$(render --set api.autoscaling.enabled=true)
hpa=$(doc HorizontalPodAutoscaler t-to-herd-cats-ai-api "$out")
[[ -n $hpa ]] || fail "no autoscaler for the API with api.autoscaling.enabled"
grep -q "^apiVersion: autoscaling/v2$" <<<"$hpa" || fail "the API's autoscaler is not autoscaling/v2"
grep -A3 "scaleTargetRef:" <<<"$hpa" | grep -q "name: t-to-herd-cats-ai-api$" || fail "the autoscaler does not scale the API"
grep -q "minReplicas: 2$" <<<"$hpa" || fail "the API's autoscaler does not start at 2"
grep -q "maxReplicas: 6$" <<<"$hpa" || fail "the API's autoscaler does not stop at 6"
grep -B4 "averageUtilization: 70$" <<<"$hpa" | grep -q "name: cpu" || fail "the API's autoscaler does not aim at 70 % CPU"
grep -q "^  replicas:" <<<"$(doc Deployment t-to-herd-cats-ai-api "$out")" && fail "the API keeps replicas beside its autoscaler"
grep -q "^  replicas: 1$" <<<"$(doc Deployment t-to-herd-cats-ai-worker "$out")" \
  || fail "api.autoscaling changes the worker"
[[ -z $(doc HorizontalPodAutoscaler t-to-herd-cats-ai-worker "$out") ]] || fail "api.autoscaling scales the worker"

# worker.autoscaling: 1 to 3 workers by default.
out=$(render --set worker.autoscaling.enabled=true --set worker.autoscaling.maxReplicas=2)
hpa=$(doc HorizontalPodAutoscaler t-to-herd-cats-ai-worker "$out")
[[ -n $hpa ]] || fail "no autoscaler for the worker with worker.autoscaling.enabled"
grep -A3 "scaleTargetRef:" <<<"$hpa" | grep -q "name: t-to-herd-cats-ai-worker$" || fail "the autoscaler does not scale the worker"
grep -q "minReplicas: 1$" <<<"$hpa" || fail "the worker's autoscaler does not start at 1"
grep -q "maxReplicas: 2$" <<<"$hpa" || fail "worker.autoscaling.maxReplicas is not used"
grep -q "^  replicas:" <<<"$(doc Deployment t-to-herd-cats-ai-worker "$out")" && fail "the worker keeps replicas beside its autoscaler"
render --set worker.autoscaling.enabled=true >/dev/null || fail "the worker's default bounds do not render"

# An autoscaler only with sound bounds and a CPU request to measure against.
if out=$(render --set api.autoscaling.enabled=true --set api.autoscaling.minReplicas=4 \
  --set api.autoscaling.maxReplicas=3); then fail "minReplicas above maxReplicas rendered"; fi
grep -q "api.autoscaling.minReplicas must not exceed api.autoscaling.maxReplicas" <<<"$out" || fail "unexpected error: $out"
if out=$(render --set worker.autoscaling.enabled=true --set worker.resources.requests.cpu=null); then
  fail "a worker autoscaler without a CPU request rendered"
fi
grep -q "worker.autoscaling needs worker.resources.requests.cpu" <<<"$out" || fail "unexpected error: $out"
if render --set api.autoscaling.enabled=true --set api.autoscaling.maxReplicas=0 >/dev/null; then
  fail "an autoscaler without pods rendered"
fi
if render --set api.autoscaling.enabled=true --set api.autoscaling.targetCPUUtilizationPercentage=0 >/dev/null; then
  fail "a CPU target of 0 % rendered"
fi

# The files claim: an autoscaled API may reach maxReplicas, so more than one needs
# ReadWriteMany; min = max = 1 is a single pod.
if out=$(render --set api.replicas=1 --set "persistence.accessModes={ReadWriteOnce}" --set api.autoscaling.minReplicas=1 \
  --set api.autoscaling.enabled=true); then fail "an autoscaled API on a ReadWriteOnce claim rendered"; fi
grep -q "needs persistence.accessModes \[ReadWriteMany\]" <<<"$out" || fail "unexpected error: $out"
render --set "persistence.accessModes={ReadWriteOnce}" --set api.autoscaling.enabled=true \
  --set api.autoscaling.minReplicas=1 --set api.autoscaling.maxReplicas=1 >/dev/null \
  || fail "an autoscaler of one API pod on ReadWriteOnce did not render"

# PodDisruptionBudgets: one per component that runs at least two pods (the API's two by
# default; the worker from two; collab is one pod by design), at most one pod away at a
# time, and pods that are not ready may always be evicted (a drain is never stuck).
out=$(render)
pdb=$(doc PodDisruptionBudget t-to-herd-cats-ai-api "$out")
[[ -n $pdb ]] || fail "no PodDisruptionBudget for the API's two pods"
grep -q "^apiVersion: policy/v1$" <<<"$pdb" || fail "the PodDisruptionBudget is not policy/v1"
grep -q "maxUnavailable: 1$" <<<"$pdb" || fail "the API's budget lets more than one pod go"
grep -A4 "selector:" <<<"$pdb" | grep -q "app.kubernetes.io/component: api$" || fail "the API's budget selects other pods"
grep -q "unhealthyPodEvictionPolicy: AlwaysAllow" <<<"$pdb" || fail "pods that are not ready block a drain"
[[ -z $(doc PodDisruptionBudget t-to-herd-cats-ai-worker "$out") ]] || fail "a budget for one worker (a drain would hang)"
[[ -z $(doc PodDisruptionBudget t-to-herd-cats-ai-collab "$out") ]] || fail "a budget for the one collab pod"
out=$(render --set worker.replicas=2 --set api.replicas=1 --set "persistence.accessModes={ReadWriteOnce}")
[[ -n $(doc PodDisruptionBudget t-to-herd-cats-ai-worker "$out") ]] || fail "no budget for two workers"
grep -A4 "selector:" <<<"$(doc PodDisruptionBudget t-to-herd-cats-ai-worker "$out")" \
  | grep -q "app.kubernetes.io/component: worker$" || fail "the worker's budget selects other pods"
[[ -z $(doc PodDisruptionBudget t-to-herd-cats-ai-api "$out") ]] || fail "a budget for one API pod"
out=$(render --set api.autoscaling.enabled=true --set api.autoscaling.minReplicas=1 \
  --set worker.autoscaling.enabled=true --set worker.autoscaling.minReplicas=2)
[[ -z $(doc PodDisruptionBudget t-to-herd-cats-ai-api "$out") ]] || fail "a budget for an API that may run one pod"
[[ -n $(doc PodDisruptionBudget t-to-herd-cats-ai-worker "$out") ]] || fail "no budget for an autoscaler from two workers"
out=$(render --set podDisruptionBudget.maxUnavailable=2 --set api.replicas=3)
grep -q "maxUnavailable: 2$" <<<"$(doc PodDisruptionBudget t-to-herd-cats-ai-api "$out")" \
  || fail "podDisruptionBudget.maxUnavailable is not used"
out=$(render --set podDisruptionBudget.enabled=false --set worker.replicas=2)
grep -q "^kind: PodDisruptionBudget" <<<"$out" && fail "a budget with podDisruptionBudget.enabled=false"
if render --set podDisruptionBudget.maxUnavailable=0 >/dev/null; then fail "a budget that lets no pod go rendered"; fi

# Default requests and limits come from the load test (plan M9 Task 10, docs/STECKBRIEF.md,
# Empfehlung Request und Limit): the autoscaler's 70 % of the CPU request is where the
# measured P95 was still far below its targets; memory is the RSS under load + 20 %.
out=$(render)
resources() { awk '/^ *resources:/{r=1} r&&/^ *(ports|volumeMounts|env|securityContext|livenessProbe):/{exit} r' \
  <<<"$(doc "$1" "$2" "$out")"; }
api=$(resources Deployment t-to-herd-cats-ai-api)
grep -A2 "requests:" <<<"$api" | grep -q "cpu: 500m" || fail "the API's CPU request is not the measured 500m"
grep -A2 "requests:" <<<"$api" | grep -q "memory: 320Mi" || fail "the API's memory request is not the measured 320Mi"
grep -A2 "limits:" <<<"$api" | grep -q "memory: 512Mi" || fail "the API's memory limit is not 512Mi"
grep -A2 "limits:" <<<"$api" | grep -q "cpu:" && fail "the API has a CPU limit (throttling costs latency)"
worker=$(resources Deployment t-to-herd-cats-ai-worker)
grep -A2 "requests:" <<<"$worker" | grep -q "cpu: 250m" || fail "the worker's CPU request is not the measured 250m"
grep -A2 "requests:" <<<"$worker" | grep -q "memory: 256Mi" || fail "the worker's memory request is not the measured 256Mi"
grep -A2 "limits:" <<<"$worker" | grep -q "memory: 384Mi" || fail "the worker's memory limit is not 384Mi"
db=$(resources StatefulSet t-to-herd-cats-ai-postgresql)
grep -A2 "requests:" <<<"$db" | grep -q "cpu: 250m" || fail "the bundled PostgreSQL's CPU request is not the measured 250m"

# The bundled PostgreSQL allows the connections the pods may hold at their most: 16 per
# API or worker pod (pool 5 + overflow 10 + LISTEN, measured in the load test) plus 10
# for the backup job, the migration and an operator's psql (plan M9 Task 11). Its
# max_connections is a value (200 by default, above the 154 of the full default bounds),
# and bounds that need more do not render.
db=$(doc StatefulSet t-to-herd-cats-ai-postgresql "$(render)")
grep -q 'args: \["-c", "max_connections=200"\]' <<<"$db" || fail "the bundled PostgreSQL does not get max_connections 200"
db=$(doc StatefulSet t-to-herd-cats-ai-postgresql "$(render --set postgresql.maxConnections=300)")
grep -q '"max_connections=300"' <<<"$db" || fail "postgresql.maxConnections is not used"
render --set api.autoscaling.enabled=true --set worker.autoscaling.enabled=true >/dev/null \
  || fail "the full default autoscaler bounds do not fit the bundled PostgreSQL"
if out=$(render --set api.autoscaling.enabled=true --set api.autoscaling.maxReplicas=10 \
  --set worker.autoscaling.enabled=true); then
  fail "autoscaler bounds above the bundled PostgreSQL's max_connections rendered"
fi
grep -q "postgresql.maxConnections (200) is below the 218 connections" <<<"$out" || fail "unexpected error: $out"
if out=$(render --set api.replicas=12 --set worker.replicas=1); then
  fail "replicas above the bundled PostgreSQL's max_connections rendered"
fi
grep -q "postgresql.maxConnections (200) is below the 218 connections" <<<"$out" || fail "unexpected error: $out"
render --set postgresql.enabled=false --set database.url=postgresql+asyncpg://herd@db:5432/herd \
  --set database.existingSecret=db --set api.autoscaling.enabled=true \
  --set api.autoscaling.maxReplicas=10 --set worker.autoscaling.enabled=true >/dev/null \
  || fail "an external database's connections are checked (the chart cannot know its limit)"
true
