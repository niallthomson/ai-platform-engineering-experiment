import json
import logging
from default_agent.agent_registry import A2AAgentRegistry
from fastmcp import FastMCP, Context
from fastmcp.server.auth.oidc_proxy import OIDCProxy
from .config import AgentConfig
from opentelemetry import trace
from uuid import uuid4
import httpx
from a2a.utils.parts import get_text_parts
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory, Client
from a2a.types import Message, Part, Role, TextPart, Task, AgentCard
from fastmcp.server.dependencies import get_access_token
from opentelemetry.propagate import inject

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class AgentCardResolver:
    card: AgentCard | None = None

    def __init__(self, config: AgentConfig, base_url: str):
        self.config = config
        self.base_url = base_url

    async def fetch_card(self):
        if self.card is not None:
            return self.card

        httpx_client = httpx.AsyncClient(timeout=120)

        try:
            resolver = A2ACardResolver(
                httpx_client=httpx_client, base_url=self.base_url
            )
            self.card = await resolver.get_agent_card()

            return self.card
        except Exception as e:
            logger.error(f"Error fetching agent card: {e}")
            raise e
        finally:
            await httpx_client.aclose()


def create_mcp_server(config: AgentConfig, registry: A2AAgentRegistry):
    """Create and configure MCP server with authentication."""

    mcp_auth = None

    base_url = config.server.url or f"http://127.0.0.1:{config.server.port}"

    if config.auth.mode == "oidc":
        mcp_auth = OIDCProxy(
            config_url=config.auth.oidc.configuration_url,
            client_id=config.auth.oidc.client_id,
            client_secret=config.auth.oidc.client_secret,
            base_url=base_url,
            algorithm="RS256",
            required_scopes=["openid", "profile"],
        )

    resolver = AgentCardResolver(config, base_url)
    mcp = FastMCP(name=config.name, auth=mcp_auth)

    @mcp.tool(description="Send a natural language question to the agent")
    async def query(query: str, ctx: Context) -> str:
        headers: dict[str, str] = {}

        card = await resolver.fetch_card()

        token = get_access_token()

        authorization_header = ctx.get_http_request().headers.get("authorization")

        if token is not None:
            headers["authorization"] = f"Bearer {token.token}"
        elif authorization_header is not None:
            headers["authorization"] = authorization_header

        """Execute a natural language query using the agent"""
        # This should probably be done with better, cross-cutting
        # instrumentation
        with tracer.start_as_current_span("mcp.query"):
            inject(headers)

            httpx_client = httpx.AsyncClient(timeout=120, headers=headers)

            try:
                config = ClientConfig(httpx_client=httpx_client, streaming=False)
                factory = ClientFactory(config)

                client = factory.create(card)

                msg = Message(
                    kind="message",
                    role=Role.user,
                    parts=[Part(TextPart(kind="text", text=query))],
                    message_id=uuid4().hex,
                    context_id=None,
                )

                output = ""

                async for event in client.send_message(msg):
                    if isinstance(event, tuple):
                        event = event[0]

                    if isinstance(event, Task) and event.artifacts:
                        artifact = event.artifacts[-1]

                        output = "\n".join(get_text_parts(artifact.parts))

                return output
            except Exception as e:
                logger.error(f"Error in tool: {e}")

            return "An error occurred"

    return mcp.http_app("/mcp")
