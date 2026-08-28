{{/*
SentraAura — Generic Service Helm Helpers
*/}}
{{- define "sentra-service.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "sentra-service.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s-%s" $name .Values.serviceName | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "sentra-service.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "sentra-service.labels" -}}
helm.sh/chart: {{ include "sentra-service.chart" . }}
{{ include "sentra-service.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- range $key, $value := .Values.extraLabels }}
{{ $key }}: {{ $value | quote }}
{{- end }}
{{- end }}

{{- define "sentra-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "sentra-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: {{ .Values.serviceName }}
{{- end }}

{{- define "sentra-service.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "sentra-service.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
