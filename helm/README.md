# Platform AI Helm Chart

Helm chart for deploying AI agents with MCP (Model Context Protocol) servers and optional Slack bot integration on Kubernetes.

## Installation

```bash
helm install my-release ./helm \
  --set image.repository=my-registry/agent \
  --set image.tag=v1.0.0 \
  --values my-values.yaml
```

## Chart Structure

### Components

The chart deploys three types of components:

1. **Agents** - A2A-compatible AI agents that process requests
2. **MCP Servers** - Model Context Protocol servers that provide tools to agents
3. **Slack Bot** - Optional Slack interface for interacting with agents

### Architecture Pattern

- Agents are defined in `values.yaml` under `agents{}` dict
- MCP servers are defined under `mcpServers[]` array
- Agents reference MCP servers by ID (auto-generates cluster URLs) or external URL
- Agents can reference peer agents by ID for A2A communication
- Slack bot references an agent by ID or external URL

## Configuration

### Global Settings

```yaml
image:
  repository: your-registry/default-agent
  tag: "latest"
  pullPolicy: IfNotPresent

imagePullSecrets: []
nameOverride: ""
fullnameOverride: ""
```

### Agent Defaults

`agentDefaults` provides base configuration inherited by all agents. Individual agents can override any setting:

```yaml
agentDefaults:
  # Override the LLM model provider for all agents
  model:
    provider: bedrock
    model_id: "us.anthropic.claude-sonnet-4-20250514-v1:0"
    bedrock:
      region: us-west-2

  # Override resource requests for all agents
  resources:
    limits:
      memory: 256Mi
    requests:
      cpu: 100m
      memory: 256Mi
```

### Defining Agents

Agents are defined as a dict where keys are agent IDs. Each agent has agent-specific fields plus any overrides from `agentDefaults`:

```yaml
agents:
  my-agent:
    name: "My Agent"
    description: "Agent description"
    system_prompt: "You are a helpful assistant"

    # Reference MCP servers by ID (deployed in this chart, see following section)
    mcpServers:
      - name: "GitHub MCP"
        id: "github-mcp"
        path: "/mcp"
        headers:
          Authorization: "Bearer token"

      # Or use external URLs
      - name: "External MCP"
        url: "https://mcp.example.com"

    # A2A peer agent configuration
    a2a:
      # Reference agents by ID (auto-generates URLs)
      peerAgents:
        - "other-agent-id"
      # Or use external URLs
      peerAgentUrls:
        - "https://external-agent.example.com"

    # Authentication configuration
    auth:
      mode: bearer # or "oidc" or "none"
      bearer:
        token: "your-token"
      oidc:
        configuration_url: "https://auth.example.com/.well-known/openid-configuration"
        audiences:
          - "audience"
```

### Defining MCP Servers

MCP servers are standalone deployments:

```yaml
mcpServers:
  - id: "github-mcp"
    image:
      repository: ghcr.io/example/github-mcp
      tag: "1.0.0"
      pullPolicy: IfNotPresent

    replicas: 1
    command: []
    args: []

    service:
      port: 3000

    secret:
      data:
        GITHUB_TOKEN: "your-token"

    serviceAccount:
      annotations:
        some/annotation: dummy
```

### Slack Bot

Optional Slack bot for user interaction:

```yaml
slackBot:
  enabled: true
  replicas: 1

  image:
    repository: your-registry/slack-bot
    tag: "latest"

  botToken: "xoxb-your-bot-token"
  appToken: "xapp-your-app-token"

  # Reference agent by ID
  a2a:
    agentId: "my-agent"
    # Or use external URL
    # url: "https://agent.example.com"

  auth:
    mode: bearer
    bearer:
      token: "shared-token"
    # oidc:
    #   configuration_url: ""
    #   client_id: ""
    #   client_secret: ""
    #   scope: "openid profile email"
    #   token_store:
    #     backend: memory
```
