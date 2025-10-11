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
agent:
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
  mcp:
    - name: Some MCP server
      url: https://some-mcp-server/mcp
      headers:
        Authorization: Bearer dummytoken
      env:
        SOME_ENV_VAR: dummyvalue

  a2a:
    server:
      host: 127.0.0.1
      port: 9000
      url: http://127.0.0.1
    security:
      mode: bearer # or oauth
      bearer:
        token: somesecuretoken
      oauth:
        jwks_url: "https://idp/oauth2/default/v1/keys"
        audience: "someaudience"
        issuer: "https://idp/oauth2/default"
    peer_agents:
      - https://someagent
```

These settings can be overridden with environment variables, for example:

```
export AGENT_name="Overridden name"
export AGENT_model__bedrock__region="us-west-2"
export AGENT_a2a__peer_agents='["http://someagent"]'
```
