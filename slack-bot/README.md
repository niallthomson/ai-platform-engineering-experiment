# Slack Bot

A Slack bot that integrates with A2A agents to provide AI-powered responses via direct messages and channel mentions.

## Features

- Direct message support for conversational interactions
- Channel mentions with threaded responses
- Context-aware conversations (maintains conversation history per DM/thread)
- Per-user OIDC authentication with device flow
- Formatted responses using Slack's mrkdwn syntax
- Reset conversation context with "reset" command

## Running

Run with `uv`:

```bash
uv run slack-bot
```

Run with Docker:

```bash
docker build -t slack-bot .
docker run -it slack-bot
```

## Configuration

The bot will detect a file named `bot_config.yaml` in the current working directory.

### Basic Configuration

```yaml
slack:
  bot_token: xoxb-your-bot-token
  app_token: xapp-your-app-token

a2a:
  url: http://localhost:9000

auth:
  mode: bearer  # or "oidc"
  bearer:
    token: your-shared-token
```

### Environment Variables

```bash
export SLACKBOT_SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACKBOT_SLACK_APP_TOKEN="xapp-your-app-token"
export SLACKBOT_A2A_URL="http://localhost:9000"
export SLACKBOT_AUTH_MODE="bearer"
export SLACKBOT_AUTH_BEARER_TOKEN="your-shared-token"
```

## Authentication Modes

The bot supports two authentication modes for calling the A2A agent:

### Bearer Token (Shared)

Simple shared token authentication where all users share the same bearer token.

```yaml
auth:
  mode: bearer
  bearer:
    token: your-shared-token
```

**Use case:** Simple deployments, internal tools, trusted environments.

### OIDC (Per-User)

OAuth2/OIDC device authorization flow where each Slack user authenticates individually and gets their own JWT token.

```yaml
auth:
  mode: oidc
  oidc:
    configuration_url: https://auth.example.com/realms/platform/.well-known/openid-configuration
    client_id: ai-agent
    client_secret: your-client-secret  # optional
    scope: "openid profile email"
    token_store:
      backend: memory  # or "redis"
      redis_url: redis://localhost:6379
      key_prefix: "slack_token:"
```

**Environment variables:**
```bash
export SLACKBOT_AUTH_MODE="oidc"
export SLACKBOT_AUTH_OIDC_CONFIGURATION_URL="https://auth.example.com/realms/platform/.well-known/openid-configuration"
export SLACKBOT_AUTH_OIDC_CLIENT_ID="ai-agent"
export SLACKBOT_AUTH_OIDC_CLIENT_SECRET="your-client-secret"
export SLACKBOT_AUTH_OIDC_SCOPE="openid profile email"
```

**Use case:** Multi-user environments, user-specific authorization, audit trails.

**How it works:**
1. User messages the bot without authentication
2. Bot initiates OIDC device flow and DMs user with verification URL and code
3. User visits URL in browser and enters code to authenticate
4. Bot receives JWT token and stores it for that user
5. Future requests use the user's JWT token when calling the A2A agent

### Token Storage

**In-Memory (Default):** Tokens stored in process memory. Simple but not suitable for multi-instance deployments.

**Redis:** Tokens stored in Redis for production and multi-instance deployments. Requires `redis` package.

```yaml
token_store:
  backend: redis
  redis_url: redis://localhost:6379
  key_prefix: "slack_token:"
```
