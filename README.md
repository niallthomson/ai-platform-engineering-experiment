# AI Platform Engineering Experiment

This repository is code for experiments around applying Generative AI to Platform Engineering use-cases. Everything included in this repository is considered prototypes and experiments.

Objectives:

- Single flexible agent implementation that can be configured for different use-cases
- MCP for tool access to common platform engineering systems
- A2A for multi-agent architecture
- OIDC or shared key authentication with identity passed between agents
- Simple Slack bot to interface with A2A agents, also supports OIDC via device auth flow
- Runnable in Docker, Kubernetes or AWS Agentcore
- Emits OpenTelemetry traces

Working on:

- Running multiple replicas of all components
- Token exchange to down-scope credentials passed between agents and to MCP servers

NOTE: As a general rule the default configurations of components in this repository is for read-only operations. This is for safety purposes and if you want to take authorize more dangerous operations you will need to modify the appropriate configurations.

## Quick start

The quick start examples include three agents and one MCP server:

- Platform agent: Supervisor agent which can dispatch requests to the other agents
- AWS agent: Answers questions related to AWS and can connect to the AWS Knowledge MCP server
- Terraform agent: Answers questions related to Terraform and can connect to the Terraform MCP server
- Terraform MCP server: Runs the official [Terraform MCP server](https://github.com/hashicorp/terraform-mcp-server)

For more information on configuring individual agents see the default agent [README](./agents/default/README.md).

### Docker Compose

A simple example Docker Compose file has been included in `docker-compose.yml`.

Run Docker Compose:

```bash
docker compose up -d --wait --build
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
            "text": "What EKS resources exist in the AWS Terraform provider?"
          }
        ],
        "messageId": "12345678-1234-1234-1234-123456789012"
      }
    }
  }' | jq .
```

To clean up the containers:

```
docker compose down
```

### Amazon EKS

A quick-start EKS cluster can be created with `eksctl` like so:

```
eksctl create cluster -f ./cluster/eksctl.yaml
```

First, lets generate a random string for the shared key:

```
SHARED_KEY=$(openssl rand -base64 16)
echo "Shared key: ${SHARED_KEY}"
```

A sample values file has been provided at `./helm/values.example.yaml`, which you can install like so:

```
helm upgrade --install platform-ai helm -f helm/values.example.yaml --set agentDefaults.auth.bearer.token=${SHARED_KEY}
```

Then use `kubectl` to forward a port from the main agent locally:

```
kubectl port-forward service/myservice 9000:http
```

The A2A endpoint will be accessible at `http://localhost:9000`. You can test it with this command:

```bash
curl -s -X POST http://localhost:9000 \
  -H "Authorization: Bearer ${SHARED_TOKEN}" \
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
            "text": "What EKS resources exist in the AWS Terraform provider?"
          }
        ],
        "messageId": "12345678-1234-1234-1234-123456789012"
      }
    }
  }' | jq .
```

To uninstall run:

```
helm ininstall platform-ai
```

Then delete the EKS cluster:

```
eksctl delete cluster -f ./cluster/eksctl.yaml
```

### AWS AgentCore

TODO
