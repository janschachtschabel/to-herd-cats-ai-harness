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

# J12 a: TLS to the database reaches every pod that connects (API, worker, migration,
# backup), with the CA mounted from its Secret; nothing by default; the bundled
# PostgreSQL (no TLS) refuses the modes that need it.
ext=(--set postgresql.enabled=false --set database.url=postgresql+asyncpg://herd@db.example:5432/herd
  --set database.existingSecret=db)
out=$(render "${ext[@]}")
grep -q "HERD_DATABASE_SSL" <<<"$out" && fail "TLS settings without database.sslMode"
grep -q "database-ca" <<<"$out" && fail "a CA volume without database.caSecret"
out=$(render "${ext[@]}" --set database.sslMode=verify-full --set database.caSecret=db-ca)
for pod in "Deployment t-to-herd-cats-ai-api" "Deployment t-to-herd-cats-ai-worker" \
  "Job t-to-herd-cats-ai-migrate" "CronJob t-to-herd-cats-ai-backup"; do
  # shellcheck disable=SC2086
  manifest=$(doc $pod "$out")
  grep -A1 -- "- name: HERD_DATABASE_SSLMODE" <<<"$manifest" | grep -q 'value: "verify-full"' \
    || fail "database.sslMode does not reach $pod"
  grep -A1 -- "- name: HERD_DATABASE_SSLROOTCERT" <<<"$manifest" \
    | grep -q "value: /var/run/secrets/herd/database-ca/ca.crt" || fail "no CA path in $pod"
  grep -A1 -- "- name: database-ca" <<<"$manifest" | grep -q "mountPath: /var/run/secrets/herd/database-ca" \
    || fail "the CA is not mounted in $pod"
  grep -A2 -- "- name: database-ca" <<<"$manifest" | grep -q "secretName: db-ca" \
    || fail "the CA volume of $pod is not database.caSecret"
done
grep -q "HERD_DATABASE_SSL" <<<"$(doc Deployment t-to-herd-cats-ai-collab "$out")" \
  && fail "the collab process gets database settings"
if render --set database.sslMode=verify-full >/dev/null 2>&1; then
  fail "the bundled PostgreSQL took database.sslMode verify-full"
fi
if render "${ext[@]}" --set database.sslMode=sometimes >/dev/null 2>&1; then
  fail "database.sslMode took an unknown mode"
fi

# J12 c: the API takes the previous internal token from the Secret's optional key
# "previous"; the collab process sends only the current one.
out=$(render)
grep -A5 -- "- name: HERD_INTERNAL_TOKEN_PREVIOUS" <<<"$(doc Deployment t-to-herd-cats-ai-api "$out")" \
  | tr -d ' ' | grep -q "key:previous" || fail "the API lacks HERD_INTERNAL_TOKEN_PREVIOUS"
grep -A6 -- "- name: HERD_INTERNAL_TOKEN_PREVIOUS" <<<"$(doc Deployment t-to-herd-cats-ai-api "$out")" \
  | grep -q "optional: true" || fail "HERD_INTERNAL_TOKEN_PREVIOUS is not optional"
if grep -q "HERD_INTERNAL_TOKEN_PREVIOUS" <<<"$(doc Deployment t-to-herd-cats-ai-collab "$out")"; then
  fail "the collab process gets the previous token"
fi

# J14: separate database roles. The schema owner's URL, password file and the runtime
# role reach the migration and backup jobs only; the API and worker keep database.url.
# Both values go together, never with the bundled PostgreSQL, never with a password.
roles=("${ext[@]}" --set database.migrate.url=postgresql+asyncpg://herd@db.example:5432/herd
  --set database.migrate.existingSecret=db-owner --set database.migrate.runtimeRole=herd_app)
out=$(render "${ext[@]}")
grep -q "HERD_MIGRATE_DATABASE\|HERD_DATABASE_RUNTIME_ROLE\|database-migrate" <<<"$out" \
  && fail "separate roles without database.migrate"
out=$(render "${roles[@]}")
for pod in "Job t-to-herd-cats-ai-migrate" "CronJob t-to-herd-cats-ai-backup"; do
  # shellcheck disable=SC2086
  manifest=$(doc $pod "$out")
  grep -A1 -- "- name: HERD_MIGRATE_DATABASE_URL" <<<"$manifest" \
    | grep -q 'value: "postgresql+asyncpg://herd@db.example:5432/herd"' || fail "no owner URL in $pod"
  grep -A1 -- "- name: HERD_MIGRATE_DATABASE_PASSWORD_FILE" <<<"$manifest" \
    | grep -q "value: /var/run/secrets/herd/database-migrate/password" || fail "no owner password in $pod"
  grep -A1 -- "- name: HERD_DATABASE_RUNTIME_ROLE" <<<"$manifest" | grep -q 'value: "herd_app"' \
    || fail "no runtime role in $pod"
  grep -A2 -- "- name: database-migrate-password" <<<"$manifest" | grep -q "secretName: db-owner" \
    || fail "the owner's password is not mounted in $pod"
done
for pod in api worker collab; do
  grep -q "HERD_MIGRATE_DATABASE\|database-migrate" <<<"$(doc Deployment "t-to-herd-cats-ai-$pod" "$out")" \
    && fail "the $pod pods get the schema owner's access"
done
if render "${ext[@]}" --set database.migrate.url=postgresql+asyncpg://herd@db.example:5432/herd >/dev/null 2>&1; then
  fail "database.migrate.url took no runtime role"
fi
if render --set database.migrate.url=postgresql+asyncpg://herd@x:5432/herd --set database.migrate.runtimeRole=herd_app >/dev/null 2>&1; then
  fail "database.migrate took the bundled PostgreSQL"
fi
if render "${roles[@]}" --set database.migrate.url=postgresql+asyncpg://herd:pw@db.example:5432/herd >/dev/null 2>&1; then
  fail "database.migrate.url took a password"
fi
if render "${roles[@]}" --set 'database.migrate.runtimeRole=Herd App' >/dev/null 2>&1; then
  fail "database.migrate.runtimeRole took a name that needs quoting"
fi
