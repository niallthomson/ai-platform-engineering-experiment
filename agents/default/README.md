# Default Agent

This is a "standard" agent implementation thats designed to be configurable for a number of different scenarios and situations.

## Running

Run with `uv`:

```bash
uv run default-agent
```

Run with Docker:

```bash
docker build -t default-agent .
docker run -p 9000:9000 -it default-agent
```

The endpoints are available on port 9000:

```bash
curl localhost:9000/health
```

## Configuration

The agent will detect a file named `agent_config.yaml` in the current working directory.

Configuration file format:

```yaml
name: Agent name
description: My agent description
system_prompt: You are an example agent

model:
  provider: bedrock # or openai
  model_id: "us.anthropic.claude-sonnet-4-20250514-v1:0"
  bedrock:
    region: us-west-2
  openai:
    base_url: http://endpoint

mcp_servers:
  - name: Some MCP server
    url: https://some-mcp-server/mcp
    headers:
      Authorization: Bearer dummytoken
    env:
      SOME_ENV_VAR: dummyvalue
    tools:
      allowed: []
      rejected: []
      prefix: ""

server:
  host: 0.0.0.0
  port: 9000
  url: http://127.0.0.1:9000

a2a:
  peer_agents:
    - https://someagent
  task_store:
    mode: memory  # or "redis" (default: "memory")
    # redis:
    #   url: redis://localhost:6379
    #   key_prefix: "a2a"  # default: "a2a"
  queue_manager:
    mode: none  # or "redis" (default: "none")
    # redis:
    #   url: redis://localhost:6379
    #   key_prefix: "a2a"  # default: "a2a"

auth:
  mode: bearer # or "oidc" or "none"
  bearer:
    token: somesecuretoken
  # oidc:
  #   configuration_url: "https://auth.example.com/realms/platform/.well-known/openid-configuration"
  #   audience: "someaudience"

sessions:
  storage:
    mode: file  # or "redis" (default: "file")
    # redis:
    #   url: redis://localhost:6379
    #   key_prefix: "agent"  # default: "agent"
```

## Authentication Modes

The agent supports three authentication modes:

### None

No authentication required (not recommended for production).

```yaml
auth:
  mode: none
```

### Bearer Token

Shared bearer token authentication.

```yaml
auth:
  mode: bearer
  bearer:
    token: your-secure-token
```

### OIDC

OIDC/OAuth2 JWT token validation. MCP endpoints (`/mcp/*`) are public when OIDC is enabled.

```yaml
auth:
  mode: oidc
  oidc:
    configuration_url: https://auth.example.com/realms/platform/.well-known/openid-configuration
    audience: your-audience
```

## Environment Variables

Settings can be overridden with environment variables:

```bash
export AGENT_NAME="Overridden name"
export AGENT_MODEL__BEDROCK__REGION="us-west-2"
export AGENT_SERVER__PORT="9000"
export AGENT_A2A__PEER_AGENTS='["http://someagent"]'
export AGENT_A2A__TASK_STORE__MODE="redis"
export AGENT_A2A__TASK_STORE__REDIS__URL="redis://localhost:6379"
export AGENT_A2A__TASK_STORE__REDIS__KEY_PREFIX="a2a"
export AGENT_A2A__QUEUE_MANAGER__MODE="redis"
export AGENT_A2A__QUEUE_MANAGER__REDIS__URL="redis://localhost:6379"
export AGENT_A2A__QUEUE_MANAGER__REDIS__KEY_PREFIX="a2a"
export AGENT_AUTH__MODE="oidc"
export AGENT_AUTH__OIDC__CONFIGURATION_URL="https://auth.example.com/.well-known/openid-configuration"
export AGENT_SESSIONS__STORAGE__MODE="redis"
export AGENT_SESSIONS__STORAGE__REDIS__URL="redis://localhost:6379"
export AGENT_SESSIONS__STORAGE__REDIS__KEY_PREFIX="agent1"
```
