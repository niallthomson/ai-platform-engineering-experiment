# AI Platform Engineering Experiment

This repository is code for experiments around applying Generative AI to Platform Engineering use-cases. Everything included in this repository is considered prototypes and experiments.

Objectives:

- Single flexible agent implementation that can be configured for different use-cases
- MCP for tool access to common platform engineering systems
- A2A for multi-agent architecture
- Runnable in Docker, Kubernetes or AWS Agentcore

NOTE: As a general rule the default configurations of components in this repository is for read-only operations. This is for safety purposes and if you want to take authorize more dangerous operations you will need to modify the appropriate configurations.

## Quick start

For more information on configuring individual agents see the default agent [README](./agents/default/README.md).

### Docker Compose

Create a file called `.env` and populate it:

```
GITHUB_TOKEN="<your token>"
CONFLUENCE_TOKEN="<your token>"
```

Run Docker Compose:

```bash
docker compose up --build
```

The A2A endpoint will be accessible at `http://localhost:9000`. You can test it with this command:

```bash
curl -s -X POST http://localhost:9000 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "req-001",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [
          {
            "kind": "text",
            "text": "What can you do in 40 words?"
          }
        ],
        "messageId": "12345678-1234-1234-1234-123456789012"
      }
    }
  }' | jq .
```

### Kubernetes

TODO

### AWS AgentCore

TODO
