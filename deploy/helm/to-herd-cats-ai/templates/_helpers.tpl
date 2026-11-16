{{/* Names, labels and the shared pieces of the API and migration pods. */}}

{{- define "herd.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* The release name, suffixed with the chart name unless it already contains it. */}}
{{- define "herd.fullname" -}}
{{- if contains .Chart.Name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "herd.selectorLabels" -}}
app.kubernetes.io/name: {{ include "herd.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "herd.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{ include "herd.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: to-herd-cats-ai
{{- end -}}

{{/* repository:tag, or repository:tag@digest when a digest pins the image. */}}
{{- define "herd.image" -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion -}}
{{- if .Values.image.digest -}}
{{- printf "%s:%s@%s" .Values.image.repository $tag .Values.image.digest -}}
{{- else -}}
{{- printf "%s:%s" .Values.image.repository $tag -}}
{{- end -}}
{{- end -}}

{{/* The database URL without password: the bundled PostgreSQL or database.url. */}}
{{- define "herd.databaseUrl" -}}
{{- if .Values.postgresql.enabled -}}
{{- printf "postgresql+asyncpg://herd@%s-postgresql:5432/herd" (include "herd.fullname" .) -}}
{{- else -}}
{{- $url := required "database.url is required when postgresql.enabled is false" .Values.database.url -}}
{{- if regexMatch "://[^/@]*:[^/@]*@" $url -}}
{{- fail "database.url must not contain a password: put it into the Secret named by database.existingSecret (key \"password\")" -}}
{{- end -}}
{{- $url -}}
{{- end -}}
{{- end -}}

{{/* The Secret holding the database password (key "password"), or "" for none. */}}
{{- define "herd.databaseSecret" -}}
{{- if .Values.database.existingSecret -}}
{{- .Values.database.existingSecret -}}
{{- else if .Values.postgresql.enabled -}}
{{- printf "%s-postgresql" (include "herd.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/* Pod Security "restricted" for the app pods (image user 10001). */}}
{{- define "herd.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
fsGroup: 10001
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "herd.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
runAsNonRoot: true
capabilities:
  drop: ["ALL"]
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{/* The role and the database, for every Python pod (API, migration job, worker). */}}
{{- define "herd.databaseEnv" -}}
{{- $root := .root -}}
- name: HERD_ROLE
  value: {{ .role }}
- name: HERD_DATABASE_URL
  value: {{ include "herd.databaseUrl" $root | quote }}
{{- if include "herd.databaseSecret" $root }}
- name: HERD_DATABASE_PASSWORD_FILE
  value: /var/run/secrets/herd/database/password
{{- end }}
{{- end -}}

{{/* Environment shared by the API and the migration job; `role` is api or migrate. */}}
{{- define "herd.env" -}}
{{- $root := .root -}}
{{ include "herd.databaseEnv" . }}
- name: HERD_COOKIE_SECURE
  value: {{ $root.Values.api.cookieSecure | quote }}
{{- with $root.Values.api.forwardedAllowIps }}
- name: HERD_FORWARDED_ALLOW_IPS
  value: {{ . | quote }}
{{- end }}
{{- with $root.Values.tracing.otlpEndpoint }}
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: {{ . | quote }}
{{- end }}
{{- end -}}

{{/* A container's environment: the chart's own entries (`own`, a rendered list), then
the values' extra map (`extra`, named `where`). The render fails for an extra name that
names a secret (PASSWORD, SECRET, TOKEN, EGRESS_PROXY, OFFSITE) or that the chart sets
itself, in any case (the app reads its settings case-insensitively, and the last of two
entries would win): secrets come from Secrets, the chart's settings from its values. */}}
{{- define "herd.withExtraEnv" -}}
{{- $taken := dict -}}
{{- range regexFindAll "(?m)^- name: \\S+" .own -1 }}
{{- $_ := set $taken (upper (trimPrefix "- name: " .)) true -}}
{{- end }}
{{- range $name, $value := .extra }}
{{- if regexMatch "PASSWORD|SECRET|TOKEN|EGRESS_PROXY|OFFSITE" (upper $name) }}
{{- fail (printf "%s.%s names a secret: it comes from a Secret, never from values" $.where $name) }}
{{- end }}
{{- if hasKey $taken (upper $name) }}
{{- fail (printf "%s.%s is set by the chart itself (or twice): use the chart's value for it" $.where $name) }}
{{- end }}
{{- $_ := set $taken (upper $name) true -}}
{{- end }}
{{- .own }}
{{- range $name, $value := .extra }}
- name: {{ $name }}
  value: {{ $value | quote }}
{{- end }}
{{- end -}}

{{/* Volumes of the app pods: a writable /tmp and the database password file
(the files volume /data is the API's alone, see deployment-api.yaml). */}}
{{- define "herd.volumes" -}}
{{- include "herd.volumesSized" (dict "root" . "tmpSizeLimit" "") -}}
{{- end -}}

{{/* herd.volumes with a sizeLimit on /tmp ("" for none): dict root, tmpSizeLimit. */}}
{{- define "herd.volumesSized" -}}
- name: tmp
{{- if .tmpSizeLimit }}
  emptyDir:
    sizeLimit: {{ .tmpSizeLimit }}
{{- else }}
  emptyDir: {}
{{- end }}
{{- with include "herd.databaseSecret" .root }}
- name: database-password
  secret:
    secretName: {{ . }}
    defaultMode: 0440
    items:
      - key: password
        path: password
{{- end }}
{{- end -}}

{{- define "herd.volumeMounts" -}}
- name: tmp
  mountPath: /tmp
{{- if include "herd.databaseSecret" . }}
- name: database-password
  mountPath: /var/run/secrets/herd/database
  readOnly: true
{{- end }}
{{- end -}}

{{/* HERD_PUBLIC_URL: publicUrl, else the first Ingress host (https with TLS), else "". */}}
{{- define "herd.publicUrl" -}}
{{- if .Values.publicUrl -}}
{{- .Values.publicUrl -}}
{{- else if and .Values.ingress.enabled .Values.ingress.hosts -}}
{{- printf "%s://%s" (ternary "https" "http" (not (empty .Values.ingress.tls))) (first .Values.ingress.hosts).host -}}
{{- end -}}
{{- end -}}

{{/* The Secret holding the token API and collab process share (key "token"). */}}
{{- define "herd.internalTokenSecret" -}}
{{- .Values.collab.internalToken.existingSecret | default (printf "%s-internal-token" (include "herd.fullname" .)) -}}
{{- end -}}

{{/* HERD_PUBLIC_URL, when there is one (API and collab process). */}}
{{- define "herd.publicUrlEnv" -}}
{{- with include "herd.publicUrl" . }}
- name: HERD_PUBLIC_URL
  value: {{ . | quote }}
{{- end }}
{{- end -}}

{{/* HERD_INTERNAL_TOKEN from its Secret (API and collab process). */}}
{{- define "herd.internalTokenEnv" -}}
- name: HERD_INTERNAL_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ include "herd.internalTokenSecret" . }}
      key: token
{{- end -}}

{{/* AI settings of the API pods (connection tests, personal agents, automations). */}}
{{- define "herd.aiApiEnv" -}}
- name: HERD_AI_CHECK_TIMEOUT_SECONDS
  value: {{ .Values.ai.checkTimeoutSeconds | quote }}
- name: HERD_AI_PERSONAL_AGENTS_MAX
  value: {{ .Values.ai.personalAgentsMax | quote }}
- name: HERD_AI_AUTOMATIONS_MAX
  value: {{ .Values.ai.automationsMax | quote }}
{{- end -}}

{{/* MCP settings of the API pods (they serve /mcp). */}}
{{- define "herd.mcpApiEnv" -}}
- name: HERD_MCP_RATE_PER_MINUTE
  value: {{ .Values.mcp.ratePerMinute | quote }}
- name: HERD_MCP_CATALOG_DIR
  value: {{ ternary (include "herd.mcpCatalogDir" .) "" (ne .Values.mcp.catalogConfigMap "") | quote }}
{{ include "herd.mcpServersEnv" . }}
{{- end -}}

{{/* Sign-in through OIDC (API pods: start, callback, discovery, keys). */}}
{{- define "herd.oidcApiEnv" -}}
- name: HERD_OIDC_ALLOWED_HOSTS
  value: {{ join "," .Values.oidc.allowedHosts | quote }}
- name: HERD_OIDC_RATE_PER_MINUTE
  value: {{ .Values.oidc.ratePerMinute | quote }}
{{- end -}}

{{/* Where the operator's catalogue entries (mcp.catalogConfigMap) are mounted. */}}
{{- define "herd.mcpCatalogDir" -}}
/etc/herd/mcp-catalog
{{- end -}}

{{/* Where external MCP servers may run (API pods: their tool lists; worker pods: runs). */}}
{{- define "herd.mcpServersEnv" -}}
- name: HERD_MCP_ALLOWED_HOSTS
  value: {{ join "," .Values.mcp.allowedHosts | quote }}
{{- end -}}

{{/* AI settings of the worker pods (agent runs). */}}
{{- define "herd.aiWorkerEnv" -}}
- name: HERD_AI_APPROVAL_HOURS
  value: {{ .Values.ai.approvalHours | quote }}
- name: HERD_RUN_CONCURRENCY
  value: {{ .Values.ai.runConcurrency | quote }}
- name: HERD_RUN_LEASE_SECONDS
  value: {{ .Values.ai.runLeaseSeconds | quote }}
{{- end -}}

{{/* MCP settings of the worker pods (agent runs call external tools). */}}
{{- define "herd.mcpWorkerEnv" -}}
- name: HERD_MCP_MAX_CALLS_PER_RUN
  value: {{ .Values.mcp.maxCallsPerRun | quote }}
{{ include "herd.mcpServersEnv" . }}
{{- end -}}

{{/* The API container's own environment (api.env comes after, herd.withExtraEnv). */}}
{{- define "herd.apiOwnEnv" -}}
{{ include "herd.env" (dict "root" . "role" "api") }}
{{ include "herd.aiApiEnv" . }}
# The administration's archive uploads (docs/SICHERUNG.md).
- name: HERD_BACKUP_UPLOAD_MAX_BYTES
  value: {{ .Values.backup.uploadMaxBytes | int64 | quote }}
{{ include "herd.mcpApiEnv" . }}
{{ include "herd.oidcApiEnv" . }}
{{- with include "herd.s3Env" . }}
{{ . }}
{{- end }}
{{- if include "herd.publicUrl" . }}
{{ include "herd.publicUrlEnv" . }}
{{- end }}
{{- if .Values.collab.enabled }}
# Live editing: /collab/ WebSockets are checked here and relayed to the
# collab process, which calls back on the internal port with the token.
{{ include "herd.internalTokenEnv" . }}
- name: HERD_COLLAB_URL
  value: {{ printf "ws://%s-collab:1234" (include "herd.fullname" .) | quote }}
{{- end }}
{{- end -}}

{{/* The worker container's own environment (worker.env comes after). */}}
{{- define "herd.workerOwnEnv" -}}
{{ include "herd.databaseEnv" (dict "root" . "role" "worker") }}
{{- with .Values.tracing.otlpEndpoint }}
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: {{ . | quote }}
{{- end }}
{{ include "herd.aiWorkerEnv" . }}
{{ include "herd.mcpWorkerEnv" . }}
{{- with include "herd.s3Env" . }}
{{ . }}
{{- end }}
# The backups' gauges (docs/SICHERUNG.md): HerdBackupTooOld's limit.
- name: HERD_BACKUP_ALERT_AFTER_HOURS
  value: {{ .Values.backup.alertAfterHours | quote }}
{{- end -}}

{{/* The collab container's own environment (collab.env comes after). */}}
{{- define "herd.collabOwnEnv" -}}
- name: HERD_ROLE
  value: collab
- name: HERD_COLLAB_PORT
  value: "1234"
# The API's internal port (/internal/collab/*), guarded by the token.
- name: HERD_COLLAB_API_URL
  value: {{ printf "http://%s-internal:9090" (include "herd.fullname" .) | quote }}
{{ include "herd.internalTokenEnv" . }}
{{- if include "herd.publicUrl" . }}
{{ include "herd.publicUrlEnv" . }}
{{- end }}
{{- end -}}

{{/* Attachments in S3 (s3.*, plan M9 decision 18): the settings of the API, worker
and backup pods. The access key comes from the Secret by reference, the secret key as a
file (HERD_S3_SECRET_ACCESS_KEY_FILE); neither is ever a value. */}}
{{- define "herd.s3Env" -}}
{{- if .Values.s3.enabled -}}
{{- $secret := required "s3.existingSecret is required with s3.enabled (keys access-key-id and secret-access-key)" .Values.s3.existingSecret -}}
- name: HERD_STORAGE
  value: s3
- name: HERD_S3_ENDPOINT
  value: {{ required "s3.endpoint is required with s3.enabled" .Values.s3.endpoint | quote }}
- name: HERD_S3_REGION
  value: {{ .Values.s3.region | quote }}
- name: HERD_S3_BUCKET
  value: {{ required "s3.bucket is required with s3.enabled" .Values.s3.bucket | quote }}
{{- with .Values.s3.prefix }}
- name: HERD_S3_PREFIX
  value: {{ . | quote }}
{{- end }}
- name: HERD_S3_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ $secret }}
      key: access-key-id
- name: HERD_S3_SECRET_ACCESS_KEY_FILE
  value: /var/run/secrets/herd/s3/secret-access-key
{{- end }}
{{- end -}}

{{- define "herd.s3Volume" -}}
{{- if .Values.s3.enabled -}}
- name: s3-secret
  secret:
    secretName: {{ .Values.s3.existingSecret }}
    defaultMode: 0440
    items:
      - key: secret-access-key
        path: secret-access-key
{{- end }}
{{- end -}}

{{- define "herd.s3VolumeMount" -}}
{{- if .Values.s3.enabled -}}
- name: s3-secret
  mountPath: /var/run/secrets/herd/s3
  readOnly: true
{{- end }}
{{- end -}}

{{/* Whether the API and worker pods mount the backups claim on /backups, for the
administration's page: with backup.enabled, on a ReadWriteMany claim the chart creates
or an existing claim (the operator's to make reachable). "true" or "". */}}
{{- define "herd.backupsShared" -}}
{{- $b := .Values.backup -}}
{{- if and $b.enabled (or $b.persistence.existingClaim (has "ReadWriteMany" $b.persistence.accessModes)) -}}
true
{{- end -}}
{{- end -}}

{{/* The backups claim's volume and mount for the API and worker pods (herd.backupsShared). */}}
{{- define "herd.backupsVolume" -}}
{{- if include "herd.backupsShared" . -}}
- name: backups
  persistentVolumeClaim:
    claimName: {{ .Values.backup.persistence.existingClaim | default (printf "%s-backups" (include "herd.fullname" .)) }}
{{- end -}}
{{- end -}}

{{- define "herd.backupsVolumeMount" -}}
{{- if include "herd.backupsShared" . -}}
# The archives, for the administration's page (Verwaltung → Sicherung).
- name: backups
  mountPath: /backups
{{- end -}}
{{- end -}}
