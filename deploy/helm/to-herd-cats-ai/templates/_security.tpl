{{/* Settings of the API pods that close ASVS gaps (plan M9 Task 18, docs/SICHERHEIT.md). */}}
{{- define "herd.securityApiEnv" -}}
# A login session ends after this many hours without a request (J7).
- name: HERD_SESSION_IDLE_HOURS
  value: {{ .Values.api.sessionIdleHours | quote }}
# Writes per person (and agent) and minute, uploads apart (J10).
- name: HERD_WRITE_RATE_PER_MINUTE
  value: {{ .Values.writeLimit.perMinute | quote }}
- name: HERD_UPLOAD_RATE_PER_MINUTE
  value: {{ .Values.writeLimit.uploadsPerMinute | quote }}
{{- end -}}

{{/* Settings of the worker pods that close ASVS gaps (plan M9 Task 18). */}}
{{- define "herd.securityWorkerEnv" -}}
# An agent's writes count like a person's, on its own count (J10).
- name: HERD_WRITE_RATE_PER_MINUTE
  value: {{ .Values.writeLimit.perMinute | quote }}
{{- end -}}
