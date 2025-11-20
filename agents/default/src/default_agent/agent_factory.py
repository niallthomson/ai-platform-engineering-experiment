import logging
from typing import List
from default_agent.agent_registry import A2AAgentRegistry
from default_agent.model_factory import create_model
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, ToolContext, tool
from strands.tools.mcp import MCPClient
from strands.experimental.tools import ToolProvider
from strands.session import SessionManager
from strands.session.file_session_manager import FileSessionManager
from .config import AgentConfig
from .executor import StrandsAgentInstance
from typing import Any

logger = logging.getLogger(__name__)


@tool(context=True, description="Provides the username of the caller.")
def get_user_name(tool_context: ToolContext) -> str:
    return tool_context.agent.state.get("username")


def build_agent(
    config: AgentConfig,
    registry: A2AAgentRegistry,
    context_id: str | None,
    authorization_header: str | None,
    username: str | None,
):
    model = create_model(config.model)

    mcp_tools: List[ToolProvider] = []

    invocation_state: dict[str, Any] = {}
    session_manager: SessionManager | None = None
    state = {"username": "unknown"}
    trace_attributes = {}

    if context_id is not None:
        session_manager = FileSessionManager(session_id=context_id)

    if username:
        trace_attributes["user.id"] = username
        state["username"] = username
    else:
        state["username"] = "unknown"

    if authorization_header is not None:
        invocation_state["authorization_header"] = authorization_header
        token = authorization_header.split(" ", 1)[1]

    for server in config.mcp_servers:
        logger.debug(f"Configuring MCP server: {server.name} -> {server.url}")

        additional_headers = {}

        if server.authentication == "passthrough" and authorization_header is not None:
            if server.authentication_header is None:
                additional_headers["Authorization"] = authorization_header
            else:
                additional_headers[server.authentication_header] = token

        mcp_client = MCPClient(
            lambda: streamablehttp_client(
                url=server.url,
                headers=server.headers | additional_headers,
            ),
        )
        mcp_tools.append(mcp_client)

    agent_tools = mcp_tools + registry.get_tools() + [get_user_name]

    return StrandsAgentInstance(
        Agent(
            name=config.name,
            description=config.description,
            model=model,
            tools=agent_tools,
            system_prompt=config.system_prompt,
            callback_handler=None,
            session_manager=session_manager,
            state=state,
            trace_attributes=trace_attributes,
        ),
        invocation_state,
    )
