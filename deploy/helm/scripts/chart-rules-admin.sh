# Chart rules for the backups in the administration (plan M9 Task 13): the upload limit
# reaches the API pods alone; the API and worker pods mount the backups claim only where
# it can be shared (ReadWriteMany, or an existing claim), never the default ReadWriteOnce
# claim of 1.0, whose modes cannot change. Sourced by check-chart-rules.sh (uses its
# render, doc and fail).

out=$(render)
api=$(doc Deployment t-to-herd-cats-ai-api "$out")
grep -A1 -- "- name: HERD_BACKUP_UPLOAD_MAX_BYTES" <<<"$api" | grep -q 'value: "2147483648"' \
  || fail "the API lacks HERD_BACKUP_UPLOAD_MAX_BYTES (2 GiB by default)"
for name in worker collab; do
  grep -q "HERD_BACKUP_UPLOAD_MAX_BYTES" <<<"$(doc Deployment "t-to-herd-cats-ai-$name" "$out")" \
    && fail "the $name gets the upload limit"
done
for kind_name in "CronJob t-to-herd-cats-ai-backup" "Job t-to-herd-cats-ai-migrate"; do
  # shellcheck disable=SC2086
  grep -q "HERD_BACKUP_UPLOAD_MAX_BYTES" <<<"$(doc $kind_name "$out")" && fail "the ${kind_name%% *} gets the upload limit"
done
out=$(render --set backup.uploadMaxBytes=5368709120)
grep -A1 -- "- name: HERD_BACKUP_UPLOAD_MAX_BYTES" <<<"$(doc Deployment t-to-herd-cats-ai-api "$out")" \
  | grep -q 'value: "5368709120"' || fail "backup.uploadMaxBytes is not passed on (or not as an integer)"
if out=$(render --set backup.uploadMaxBytes=0); then fail "backup.uploadMaxBytes=0 rendered"; fi

# The default ReadWriteOnce claim stays the CronJob's: no API or worker pod mounts it.
out=$(render)
for name in api worker; do
  grep -q "claimName: t-to-herd-cats-ai-backups" <<<"$(doc Deployment "t-to-herd-cats-ai-$name" "$out")" \
    && fail "the $name mounts the ReadWriteOnce backups claim"
done
# ReadWriteMany: both mount it on /backups, the CronJob still does.
out=$(render --set "backup.persistence.accessModes={ReadWriteMany}")
for name in api worker; do
  workload=$(doc Deployment "t-to-herd-cats-ai-$name" "$out")
  grep -q "claimName: t-to-herd-cats-ai-backups" <<<"$workload" || fail "the $name does not mount a ReadWriteMany backups claim"
  grep -B1 -A1 -- "- name: backups$" <<<"$workload" | grep -q "mountPath: /backups" || fail "the $name's archives are not at /backups"
done
grep -q "claimName: t-to-herd-cats-ai-backups" <<<"$(doc CronJob t-to-herd-cats-ai-backup "$out")" \
  || fail "the CronJob lost the backups claim"
# An existing claim is the operator's: mounted as named.
out=$(render --set backup.persistence.existingClaim=archives)
for name in api worker; do
  grep -q "claimName: archives$" <<<"$(doc Deployment "t-to-herd-cats-ai-$name" "$out")" \
    || fail "the $name does not mount backup.persistence.existingClaim"
done
# Without backups, nothing to mount.
out=$(render --set backup.enabled=false --set "backup.persistence.accessModes={ReadWriteMany}")
grep -q "mountPath: /backups" <<<"$out" && fail "a pod mounts /backups with backup.enabled false"
true
