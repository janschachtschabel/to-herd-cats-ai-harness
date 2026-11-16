# Chart rules for attachments in S3 (plan M9 Task 14): the settings reach the API, the
# worker and the backup job and nothing else, the keys come from a Secret (the secret
# key as a file), what s3.enabled needs is required, the backup job then mounts no files
# claim, and the store's egress opens for exactly those pods. Sourced by
# check-chart-rules.sh (uses its render, doc and fail).

# Off by default: no pod gets an S3 setting.
out=$(render)
grep -q "HERD_STORAGE\|HERD_S3_" <<<"$out" && fail "S3 settings render with s3.enabled false"

# s3.enabled needs the Secret, the endpoint and the bucket.
s3=(--set s3.enabled=true --set s3.existingSecret=herd-s3 --set s3.endpoint=http://seaweedfs.storage.svc:8333 --set s3.bucket=herd)
for missing in s3.existingSecret s3.endpoint s3.bucket; do
  if out=$(render "${s3[@]}" --set "$missing="); then
    fail "s3.enabled without $missing rendered"
  fi
  grep -q "$missing is required" <<<"$out" || fail "unexpected error without $missing: $out"
done

out=$(render "${s3[@]}" --set s3.prefix=herd/prod --set persistence.enabled=false) \
  || fail "s3.enabled with persistence.enabled false does not render: $out"
api=$(doc Deployment t-to-herd-cats-ai-api "$out")
worker=$(doc Deployment t-to-herd-cats-ai-worker "$out")
cron=$(doc CronJob t-to-herd-cats-ai-backup "$out")
migrate=$(doc Job t-to-herd-cats-ai-migrate "$out")
collab=$(doc Deployment t-to-herd-cats-ai-collab "$out")
[[ -n $cron ]] || fail "s3.enabled with persistence.enabled false renders no backup job"
for workload in "$api" "$worker" "$cron"; do
  grep -A1 -- "- name: HERD_STORAGE$" <<<"$workload" | grep -q "value: s3" || fail "a pod lacks HERD_STORAGE=s3"
  grep -A1 -- "- name: HERD_S3_ENDPOINT$" <<<"$workload" | grep -q '"http://seaweedfs.storage.svc:8333"' \
    || fail "a pod lacks HERD_S3_ENDPOINT"
  grep -A1 -- "- name: HERD_S3_PREFIX$" <<<"$workload" | grep -q '"herd/prod"' || fail "a pod lacks HERD_S3_PREFIX"
  grep -A4 -- "- name: HERD_S3_ACCESS_KEY_ID$" <<<"$workload" | grep -q "key: access-key-id" \
    || fail "the access key does not come from the Secret"
  grep -A1 -- "- name: HERD_S3_SECRET_ACCESS_KEY_FILE$" <<<"$workload" \
    | grep -q "value: /var/run/secrets/herd/s3/secret-access-key" || fail "the secret key is not a file"
  grep -q "mountPath: /var/run/secrets/herd/s3" <<<"$workload" || fail "the secret key is not mounted"
  grep -q "name: HERD_S3_SECRET_ACCESS_KEY$" <<<"$workload" && fail "the secret key is passed as a variable"
done
for workload in "$migrate" "$collab"; do
  grep -q "HERD_S3_\|herd-s3" <<<"$workload" && fail "the migration job or collab gets the S3 settings"
done
# With the store the backup job mounts no files claim and needs no API pod beside it.
grep -q "claimName: t-to-herd-cats-ai-data" <<<"$cron" && fail "the backup job mounts the files claim with s3.enabled"
grep -q "podAffinity" <<<"$cron" && fail "the backup job seeks an API pod with s3.enabled"
grep -q "PersistentVolumeClaim" <<<"$(doc PersistentVolumeClaim t-to-herd-cats-ai-data "$out")" \
  && fail "a files claim renders with persistence.enabled false"

# Values never carry the keys: the schema has no field for them.
if out=$(render "${s3[@]}" --set s3.secretAccessKey=x 2>&1); then
  fail "a secret key value was accepted"
fi
for name in HERD_S3_SECRET_ACCESS_KEY HERD_S3_SECRET_ACCESS_KEY_FILE HERD_S3_ACCESS_KEY_ID HERD_STORAGE; do
  if out=$(render "${s3[@]}" --set "api.env.$name=x"); then fail "api.env.$name rendered"; fi
done

# The store's egress: one policy for the API, worker and backup pods, only when set.
out=$(render "${s3[@]}" --set networkPolicy.enabled=true) || fail "s3 with NetworkPolicy: $out"
[[ -z $(doc NetworkPolicy t-to-herd-cats-ai-s3-egress "$out") ]] || fail "an empty s3.egress renders a policy"
out=$(render "${s3[@]}" --set networkPolicy.enabled=true \
  --set 's3.egress[0].to[0].ipBlock.cidr=10.40.0.0/16' --set 's3.egress[0].ports[0].port=8333') \
  || fail "s3.egress does not render: $out"
policy=$(doc NetworkPolicy t-to-herd-cats-ai-s3-egress "$out")
[[ -n $policy ]] || fail "s3.egress renders no policy"
grep -q "values: \[api, worker, backup\]" <<<"$policy" || fail "the S3 egress is not for api, worker and backup"
grep -q "cidr: 10.40.0.0/16" <<<"$policy" || fail "the S3 egress lacks its rule"
