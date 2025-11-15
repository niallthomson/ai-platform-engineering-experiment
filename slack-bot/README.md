# Slack Bot

A Slack bot that integrates with A2A agents to provide AI-powered responses via direct messages.

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

Configuration file format:

```yaml
slack:
  bot_token: xoxb-your-bot-token
  app_token: xapp-your-app-token

a2a:
  url: http://localhost:9000
  security:
    bearer:
      token: your-api-key
```

These settings can be overridden with environment variables:

```
export SLACKBOT_slack__bot_token="xoxb-your-bot-token"
export SLACKBOT_slack__app_token="xapp-your-app-token"
export SLACKBOT_a2a__url="http://localhost:9000"
export SLACKBOT_a2a__security__bearer__token="your-api-key"
```

## Features

- Direct message support for conversational interactions
- Formatted responses using Slack's mrkdwn syntax
