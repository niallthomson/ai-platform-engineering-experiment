import logging
from typing import Callable
from .executor import StrandsAgentInstance
from fastmcp import FastMCP
from fastmcp.server.auth.oidc_proxy import OIDCProxy
from .config import AgentConfig

logger = logging.getLogger(__name__)


def create_mcp_server(
    config: AgentConfig, agent_generator: Callable[[None], StrandsAgentInstance]
):
    """Create and configure MCP server with authentication."""

    mcp_auth = None

    if config.auth.mode == "oidc":
        base_url = config.server.url or f"http://127.0.0.1:{config.server.port}"
        mcp_auth = OIDCProxy(
            config_url=config.auth.oidc.configuration_url,
            client_id=config.auth.oidc.client_id,
            client_secret=config.auth.oidc.client_secret,
            base_url=base_url,
            algorithm="RS256",
            required_scopes=["openid", "profile"],
        )

    mcp = FastMCP(name=config.name, auth=mcp_auth)

    @mcp.tool()
    def query(query: str) -> list[str]:
        """Execute a natural language query using the agent"""
        agent = agent_generator(None).agent
        response = agent(query)

        return [
            content["text"]
            for content in response.message["content"]
            if "text" in content
        ]

    return mcp.http_app("/mcp")
