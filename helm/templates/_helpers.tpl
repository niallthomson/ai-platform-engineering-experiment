{{/*
Expand the name of the chart.
*/}}
{{- define "platform-ai.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "platform-ai.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "platform-ai.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "platform-ai.labels" -}}
helm.sh/chart: {{ include "platform-ai.chart" . }}
{{ include "platform-ai.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "platform-ai.selectorLabels" -}}
app.kubernetes.io/name: {{ include "platform-ai.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Agent-specific selector labels
*/}}
{{- define "platform-ai.agentSelectorLabels" -}}
app.kubernetes.io/name: {{ include "platform-ai.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/type: agent
app.kubernetes.io/component: {{ .agent.id }}
{{- end }}

{{/*
Agent fullname
*/}}
{{- define "platform-ai.agentFullname" -}}
{{- printf "%s-agent-%s" (include "platform-ai.fullname" .root) .agent.id | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
MCP Server fullname
*/}}
{{- define "platform-ai.mcpServerFullname" -}}
{{- printf "%s-mcp-%s" (include "platform-ai.fullname" .root) .mcpServer.id | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
MCP Server selector labels
*/}}
{{- define "platform-ai.mcpServerSelectorLabels" -}}
app.kubernetes.io/name: {{ include "platform-ai.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/type: mcp-server
app.kubernetes.io/component: {{ .mcpServer.id }}
{{- end }}

{{/*
Merge agent-specific config with defaults
*/}}
{{- define "platform-ai.agentConfig" -}}
{{- $defaults := .defaults }}
{{- $override := .override }}
{{- if $override }}
{{- toYaml $override }}
{{- else }}
{{- toYaml $defaults }}
{{- end }}
{{- end }}

{{/*
Convert MCP servers to Python dict format
*/}}
{{- define "platform-ai.mcpServersToPython" -}}
{{- $ctx := . }}
{{- $servers := $ctx.servers }}
{{- $root := $ctx.root }}
{{- $result := list }}
{{- range $servers }}
  {{- $parts := list }}
  {{- $parts = append $parts (printf "name='%s'" .name) }}
  {{- if .url }}
    {{- $parts = append $parts (printf "url='%s'" .url) }}
  {{- else if .id }}
    {{- $mcpCtx := dict "root" $root "mcpServer" (dict "id" .id) }}
    {{- $url := printf "http://%s.%s.svc.cluster.local" (include "platform-ai.mcpServerFullname" $mcpCtx) $root.Release.Namespace }}
    {{- if .path }}
      {{- $url = printf "%s%s" $url .path }}
    {{- end }}
    {{- $parts = append $parts (printf "url='%s'" $url) }}
  {{- end }}
  {{- if .headers }}
    {{- $headerParts := list }}
    {{- range $key, $value := .headers }}
      {{- $headerParts = append $headerParts (printf "%s='%s'" $key $value) }}
    {{- end }}
    {{- $parts = append $parts (printf "headers={%s}" (join ", " $headerParts)) }}
  {{- end }}
  {{- if .authentication }}
  {{- $parts = append $parts (printf "authentication='%s'" .authentication) }}
  {{- end }}
  {{- if .authentication_header }}
  {{- $parts = append $parts (printf "authentication_header='%s'" .authentication_header) }}
  {{- end }}
  {{- if .tools }}
    {{- $toolParts := list }}
    {{- if .tools.allowed }}
      {{- $toolParts = append $toolParts (printf "allowed=%s" (toJson .tools.allowed)) }}
    {{- end }}
    {{- if .tools.rejected }}
      {{- $toolParts = append $toolParts (printf "rejected=%s" (toJson .tools.rejected)) }}
    {{- end }}
    {{- if .tools.prefix }}
      {{- $toolParts = append $toolParts (printf "prefix='%s'" .tools.prefix) }}
    {{- end }}
    {{- if $toolParts }}
      {{- $parts = append $parts (printf "tools={%s}" (join ", " $toolParts)) }}
    {{- end }}
  {{- end }}
  {{- $result = append $result (printf "{%s}" (join ", " $parts)) }}
{{- end }}
{{- printf "[%s]" (join "," $result) }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "platform-ai.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "platform-ai.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Slack Bot fullname
*/}}
{{- define "platform-ai.slackBotFullname" -}}
{{- printf "%s-slack-bot" (include "platform-ai.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Slack Bot selector labels
*/}}
{{- define "platform-ai.slackBotSelectorLabels" -}}
app.kubernetes.io/name: {{ include "platform-ai.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/type: slack-bot
{{- end }}
