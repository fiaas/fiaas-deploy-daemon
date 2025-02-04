{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "fiaas-deploy-daemon.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "fiaas-deploy-daemon.labels" -}}
app: {{ .Values.name }}
app.kubernetes.io/name: fiaas-deploy-daemon
helm.sh/chart: {{ include "fiaas-deploy-daemon.chart" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.labels.global }}
{{ toYaml . }}
{{- end -}}
{{- end -}}

{{- define "fiaas-deploy-daemon.labelsOrAnnotations" -}}
{{- if . }}
{{ toYaml . }}
{{- end -}}
{{- end -}}

{{- define "fiaas-deploy-daemon.RoleCertificateRules" -}}
- apiGroups:
  - cert-manager.io
  resources:
  - certificates
  verbs:
  - get
  - list
  - watch
{{- end -}}