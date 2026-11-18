{{/* Settings of the API pods that close ASVS gaps (plan M9 Task 18, docs/SICHERHEIT.md). */}}
{{- define "herd.securityApiEnv" -}}
# A login session ends after this many hours without a request (J7).
- name: HERD_SESSION_IDLE_HOURS
  value: {{ .Values.api.sessionIdleHours | quote }}
{{- end -}}
