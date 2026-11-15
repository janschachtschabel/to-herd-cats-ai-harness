{{/* Replicas, autoscalers and disruption budgets of the api and worker Deployments
(plan M9 decision 19). Each takes (dict "root" $ "component" "api"|"worker"). */}}

{{/* The fewest pods the component runs: autoscaling.minReplicas or replicas. */}}
{{- define "herd.minReplicas" -}}
{{- $values := index .root.Values .component -}}
{{- if $values.autoscaling.enabled -}}
{{- $values.autoscaling.minReplicas -}}
{{- else -}}
{{- $values.replicas -}}
{{- end -}}
{{- end -}}

{{/* The most pods the component runs: autoscaling.maxReplicas or replicas. */}}
{{- define "herd.maxReplicas" -}}
{{- $values := index .root.Values .component -}}
{{- if $values.autoscaling.enabled -}}
{{- $values.autoscaling.maxReplicas -}}
{{- else -}}
{{- $values.replicas -}}
{{- end -}}
{{- end -}}

{{/* A HorizontalPodAutoscaler on CPU for the component's Deployment. Scale-down is
gentle (one pod per two minutes after five quiet minutes): an API pod that goes takes
its live connections with it (browsers reconnect after 5 s), a worker its runs (taken
up after their lease). */}}
{{- define "herd.hpa" -}}
{{- $root := .root -}}
{{- $values := index $root.Values .component -}}
{{- if $values.autoscaling.enabled -}}
{{- $auto := $values.autoscaling -}}
{{- if gt (int $auto.minReplicas) (int $auto.maxReplicas) -}}
{{- fail (printf "%s.autoscaling.minReplicas must not exceed %s.autoscaling.maxReplicas" .component .component) -}}
{{- end -}}
{{- if not (dig "requests" "cpu" "" ($values.resources | default dict)) -}}
{{- fail (printf "%s.autoscaling needs %s.resources.requests.cpu: the CPU target is a share of the request" .component .component) -}}
{{- end -}}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "herd.fullname" $root }}-{{ .component }}
  labels:
    {{- include "herd.labels" $root | nindent 4 }}
    app.kubernetes.io/component: {{ .component }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "herd.fullname" $root }}-{{ .component }}
  minReplicas: {{ $auto.minReplicas }}
  maxReplicas: {{ $auto.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ $auto.targetCPUUtilizationPercentage }}
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
{{- end -}}
{{- end -}}

{{/* A PodDisruptionBudget for the component when it runs at least two pods. */}}
{{- define "herd.pdb" -}}
{{- $root := .root -}}
{{- if and $root.Values.podDisruptionBudget.enabled (ge (int (include "herd.minReplicas" .)) 2) -}}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "herd.fullname" $root }}-{{ .component }}
  labels:
    {{- include "herd.labels" $root | nindent 4 }}
    app.kubernetes.io/component: {{ .component }}
spec:
  maxUnavailable: {{ $root.Values.podDisruptionBudget.maxUnavailable }}
  unhealthyPodEvictionPolicy: AlwaysAllow
  selector:
    matchLabels:
      {{- include "herd.selectorLabels" $root | nindent 6 }}
      app.kubernetes.io/component: {{ .component }}
{{- end -}}
{{- end -}}
