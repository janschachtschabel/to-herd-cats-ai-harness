# Chart rules for where the M9 settings and secrets go (plan M9 Task 7): each setting to
# the pods that read it and nowhere else, secrets only from Secrets, the egress of the
# sign-in providers, the backup pod beside a ReadWriteOnce files claim, and everything
# switched on at once (ci/full-values.yaml). Sourced by check-chart-rules.sh (uses its
# render, doc and fail).

full=(-f "$chart/ci/full-values.yaml")
out=$(render "${full[@]}")
api=$(doc Deployment t-to-herd-cats-ai-api "$out")
worker=$(doc Deployment t-to-herd-cats-ai-worker "$out")
collab=$(doc Deployment t-to-herd-cats-ai-collab "$out")
cron=$(doc CronJob t-to-herd-cats-ai-backup "$out")
migrate=$(doc Job t-to-herd-cats-ai-migrate "$out")
[[ -n $api && -n $worker && -n $collab && -n $cron && -n $migrate ]] \
  || fail "ci/full-values.yaml does not render every workload"

# Sign-in (OIDC): the API alone, never the worker, the migration job or the backup job.
for workload in "$worker" "$migrate" "$cron" "$collab"; do
  grep -q "HERD_OIDC_\|name: herd-oidc$" <<<"$workload" && fail "a pod other than the API gets the sign-in settings"
done
grep -A1 -- "- secretRef:" <<<"$api" | grep -q "name: herd-oidc$" || fail "the API lacks the OIDC client secrets"

# Backups: retention and directory reach the backup job alone, the alert's limit the
# worker alone (it exports the gauges); the offsite Secret only the backup job.
for workload in "$api" "$worker" "$migrate" "$collab"; do
  grep -q "HERD_BACKUP_KEEP_\|HERD_BACKUP_DIR\|herd-offsite" <<<"$workload" && fail "a pod other than the backup job gets its settings"
done
for workload in "$api" "$cron" "$migrate" "$collab"; do
  grep -q "HERD_BACKUP_ALERT_AFTER_HOURS" <<<"$workload" && fail "a pod other than the worker gets the backup alert's limit"
done
grep -A2 -- "envFrom:" <<<"$cron" | grep -q "name: herd-offsite$" || fail "the backup job lacks the offsite Secret"

# The collab process holds page grants only (M9 Task 6): no session cookie name, no
# database, no Secret but the internal token.
grep -q "HERD_SESSION_COOKIE_NAME\|HERD_DATABASE_\|envFrom" <<<"$collab" \
  && fail "the collab process gets a cookie name, the database or a Secret"
grep -A4 -- "- name: HERD_INTERNAL_TOKEN" <<<"$collab" | grep -q "name: herd-internal-token$" \
  || fail "the collab process lacks collab.internalToken.existingSecret"

# Secrets only from Secrets: no variable that names a password, token, key or proxy
# carries a value of its own (only valueFrom, envFrom or a file), and no ConfigMap.
leaks=$(awk '
  /- name: / { name = $NF; next }
  /^ *value: / && name ~ /(PASSWORD|SECRET|TOKEN|EGRESS_PROXY|OFFSITE)/ && name !~ /_FILE$/ { print name }
  { name = "" }' <<<"$out")
[[ -z $leaks ]] || fail "secrets as values: $leaks"
grep -q "^kind: ConfigMap" <<<"$out" && fail "a ConfigMap appeared with ci/full-values.yaml"
grep -q "^kind: Secret" <<<"$out" && fail "the chart makes a Secret although every one is named"
if render --set api.env.HERD_SECRET_KEY=x >/dev/null; then fail "api.env took HERD_SECRET_KEY"; fi
if render --set worker.env.HERD_DATABASE_PASSWORD=x >/dev/null; then fail "worker.env took a password"; fi
if render --set collab.env.HERD_INTERNAL_TOKEN=x >/dev/null; then fail "collab.env took the internal token"; fi

# The sign-in providers' egress (oidc.egress): the API pods alone, egress only, nothing
# without rules.
out=$(render --set networkPolicy.enabled=true)
[[ -z $(doc NetworkPolicy t-to-herd-cats-ai-oidc-egress "$out") ]] || fail "OIDC egress is open without oidc.egress"
out=$(render --set networkPolicy.enabled=true --set 'oidc.egress[0].to[0].ipBlock.cidr=198.51.100.0/24' \
  --set 'oidc.egress[0].ports[0].port=443')
policy=$(doc NetworkPolicy t-to-herd-cats-ai-oidc-egress "$out")
[[ -n $policy ]] || fail "no NetworkPolicy for oidc.egress"
grep -A6 "podSelector:" <<<"$policy" | grep -q "app.kubernetes.io/component: api$" || fail "OIDC egress is not the API's"
grep -q "policyTypes: \[Egress\]" <<<"$policy" || fail "the OIDC egress policy restricts more than egress"
grep -q "cidr: 198.51.100.0/24" <<<"$policy" || fail "oidc.egress is not passed on"
grep -q "198.51.100.0/24" <<<"$(doc NetworkPolicy t-to-herd-cats-ai "$out")$(doc NetworkPolicy t-to-herd-cats-ai-worker "$out")$(doc NetworkPolicy t-to-herd-cats-ai-ai-egress "$out")" \
  && fail "oidc.egress leaks into other policies"
out=$(render --set 'oidc.egress[0].ports[0].port=443')
grep -q "^kind: NetworkPolicy" <<<"$out" && fail "oidc.egress renders a policy without networkPolicy.enabled"

# The backup pod mounts the files claim beside the API: on a ReadWriteOnce claim it must
# run on an API pod's node; ReadWriteMany needs nothing; ReadWriteOncePod cannot work.
out=$(render)
grep -q "podAffinity" <<<"$(doc CronJob t-to-herd-cats-ai-backup "$out")" && fail "a pod affinity on a ReadWriteMany claim"
out=$(render --set api.replicas=1 --set "persistence.accessModes={ReadWriteOnce}")
cron=$(doc CronJob t-to-herd-cats-ai-backup "$out")
grep -A10 "podAffinity:" <<<"$cron" | grep -q "app.kubernetes.io/component: api$" \
  || fail "the backup pod may land away from the API on a ReadWriteOnce claim"
grep -A12 "podAffinity:" <<<"$cron" | grep -q "topologyKey: kubernetes.io/hostname" \
  || fail "the backup pod's affinity is not per node"
if out=$(render --set api.replicas=1 --set "persistence.accessModes={ReadWriteOncePod}"); then
  fail "a backup on a ReadWriteOncePod files claim rendered"
fi
grep -q "ReadWriteOncePod" <<<"$out" || fail "unexpected error: $out"
render --set api.replicas=1 --set "persistence.accessModes={ReadWriteOncePod}" --set backup.enabled=false >/dev/null \
  || fail "ReadWriteOncePod without backups did not render"
true
