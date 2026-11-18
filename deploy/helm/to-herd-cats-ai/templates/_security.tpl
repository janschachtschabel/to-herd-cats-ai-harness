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
# A clamd of the operator's to scan uploads; empty: no scan (J11).
- name: HERD_CLAMAV_ADDRESS
  value: {{ .Values.virusScan.clamavAddress | quote }}
{{- end -}}

{{/* Settings of the worker pods that close ASVS gaps (plan M9 Task 18). */}}
{{- define "herd.securityWorkerEnv" -}}
# An agent's writes count like a person's, on its own count (J10).
- name: HERD_WRITE_RATE_PER_MINUTE
  value: {{ .Values.writeLimit.perMinute | quote }}
{{- end -}}


{{/* TLS to the database (J12 a): every pod that connects to it (API, worker, migration,
backup). The bundled PostgreSQL speaks no TLS, so it refuses the modes that need it. */}}
{{- define "herd.databaseTlsEnv" -}}
{{- $mode := .Values.database.sslMode -}}
{{- if and .Values.postgresql.enabled (has $mode (list "require" "verify-ca" "verify-full")) -}}
{{- fail (printf "database.sslMode %s needs a database that speaks TLS; the bundled PostgreSQL does not (postgresql.enabled)" $mode) -}}
{{- end -}}
{{- if $mode }}
- name: HERD_DATABASE_SSLMODE
  value: {{ $mode | quote }}
{{- end }}
{{- if .Values.database.caSecret }}
- name: HERD_DATABASE_SSLROOTCERT
  value: /var/run/secrets/herd/database-ca/ca.crt
{{- end }}
{{- end -}}

{{/* Separate database roles (J14): the schema owner's URL and password file for the
migration job and the backup job only; the API and worker pods keep database.url, the
runtime role, which migrations give data rights only. */}}
{{- define "herd.migrateDatabaseEnv" -}}
{{- $m := .Values.database.migrate -}}
{{- if or $m.url $m.runtimeRole -}}
{{- if .Values.postgresql.enabled -}}
{{- fail "database.migrate needs an external database (postgresql.enabled false)" -}}
{{- end -}}
{{- if not (and $m.url $m.runtimeRole) -}}
{{- fail "database.migrate.url and database.migrate.runtimeRole go together" -}}
{{- end -}}
{{- if regexMatch "://[^/@]*:[^/@]*@" $m.url -}}
{{- fail "database.migrate.url must not contain a password: put it into the Secret named by database.migrate.existingSecret (key \"password\")" -}}
{{- end -}}
- name: HERD_MIGRATE_DATABASE_URL
  value: {{ $m.url | quote }}
{{- if $m.existingSecret }}
- name: HERD_MIGRATE_DATABASE_PASSWORD_FILE
  value: /var/run/secrets/herd/database-migrate/password
{{- end }}
- name: HERD_DATABASE_RUNTIME_ROLE
  value: {{ $m.runtimeRole | quote }}
{{- end -}}
{{- end -}}

{{/* The schema owner's password file (database.migrate.existingSecret, key
"password"): a volume and its mount, migration and backup pods only. */}}
{{- define "herd.migrateVolume" -}}
{{- with .Values.database.migrate.existingSecret }}
- name: database-migrate-password
  secret:
    secretName: {{ . }}
    defaultMode: 0440
    items:
      - key: password
        path: password
{{- end }}
{{- end -}}

{{- define "herd.migrateVolumeMount" -}}
{{- if .Values.database.migrate.existingSecret }}
- name: database-migrate-password
  mountPath: /var/run/secrets/herd/database-migrate
  readOnly: true
{{- end }}
{{- end -}}
