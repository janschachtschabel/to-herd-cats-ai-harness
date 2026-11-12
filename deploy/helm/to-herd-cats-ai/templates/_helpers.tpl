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

{{/* Environment shared by the API and the migration job; `role` is api or migrate. */}}
{{- define "herd.env" -}}
{{- $root := .root -}}
- name: HERD_ROLE
  value: {{ .role }}
- name: HERD_DATABASE_URL
  value: {{ include "herd.databaseUrl" $root | quote }}
{{- if include "herd.databaseSecret" $root }}
- name: HERD_DATABASE_PASSWORD_FILE
  value: /var/run/secrets/herd/database/password
{{- end }}
{{- with $root.Values.tracing.otlpEndpoint }}
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: {{ . | quote }}
{{- end }}
{{- range $name, $value := $root.Values.api.env }}
- name: {{ $name }}
  value: {{ $value | quote }}
{{- end }}
{{- end -}}

{{/* Volumes of the app pods: a writable /tmp and the database password file. */}}
{{- define "herd.volumes" -}}
- name: tmp
  emptyDir: {}
{{- with include "herd.databaseSecret" . }}
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
