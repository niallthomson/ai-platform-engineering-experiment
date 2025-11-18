import asyncio
import logging
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.client.streamable_http import streamablehttp_client
from strands import tool, Agent, ToolContext
from strands.tools.mcp import MCPClient
from .server import A2AServer
from strands.experimental.tools import ToolProvider
from strands.session import SessionManager
from strands.session.file_session_manager import FileSessionManager
from a2a.types import AgentSkill
from .config import createConfig
from .agent_registry import A2AAgentRegistry
from .model_factory import create_model
from .security_factory import configure_security
from .mcp_factory import create_mcp_server
from .executor import StrandsAgentInstance
import uvicorn
from a2a.server.agent_execution import RequestContext
from uvicorn.config import LOGGING_CONFIG
from typing import Any

format_prefix = "%(levelname)s | %(name)s |"
format = "{} %(message)s".format(format_prefix)

logging.basicConfig(format=format, level=logging.INFO)

LOGGING_CONFIG["formatters"]["default"]["fmt"] = format
LOGGING_CONFIG["formatters"]["access"]["fmt"] = (
    '{} %(client_addr)s - "%(request_line)s" %(status_code)s'.format(format_prefix)
)

logger = logging.getLogger(__name__)


@tool(context=True)
def get_user_name(tool_context: ToolContext) -> str:
    return tool_context.agent.state.get("username")


async def run(loop):
    config = createConfig("agent_config.yaml")

    logger.info(f"Starting agent: {config.name}")

    model = create_model(config.model)

    registry = A2AAgentRegistry(agent_urls=config.a2a.peer_agents, refresh_interval=60)
    await registry.start()

    def agent_generator(context: RequestContext | None) -> StrandsAgentInstance:
        invocation_state: dict[str, Any] = {}
        session_manager: SessionManager | None = None
        state = {"username": "unknown"}

        authorization_header: str | None = None

        # Workaround until this issue is resolved: https://github.com/modelcontextprotocol/python-sdk/issues/1509
        mcp_tools: List[ToolProvider] = []

        if context is not None:
            if context.context_id is not None:
                context_id = context.context_id
                session_manager = FileSessionManager(session_id=context_id)

            if context.call_context is not None:
                state["username"] = context.call_context.user.user_name

                call_headers = context.call_context.state["headers"]

                authorization_header = call_headers.get("authorization", None)

            token: str | None = None

            if authorization_header is not None:
                invocation_state["authorization_header"] = authorization_header
                token = authorization_header.split(" ", 1)[1]

            for server in config.mcp_servers:
                logger.debug(f"Configuring MCP server: {server.name} -> {server.url}")

                additional_headers = {}

                if (
                    server.authentication == "passthrough"
                    and authorization_header is not None
                ):
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
            ),
            invocation_state,
        )

    lifespan = None
    mcp_app = None

    if config.mcp.enabled:
        mcp_app = create_mcp_server(config, agent_generator)
        lifespan = mcp_app.lifespan

    app = FastAPI(lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    security_schemes = configure_security(app, config.auth)

    skills = list(
        map(
            lambda skill: AgentSkill(
                id=skill.id,
                name=skill.name,
                description=skill.description,
                examples=skill.examples,
                tags=[],
            ),
            config.a2a.skills,
        )
    )

    a2a_server = A2AServer(
        http_url=config.server.url,
        skills=skills,
        agent_generator=agent_generator,
        security_schemes=security_schemes,
    )

    fastapi_app = a2a_server.to_fastapi_app()

    if mcp_app is not None:
        fastapi_app.mount("/", mcp_app)

    @app.get("/health")
    @app.get("/ping")
    async def health_check():
        return {"status": "healthy"}

    @app.get("/agents/status")
    async def agents_status():
        return registry.get_status()

    app.mount("/", fastapi_app)

    uvicorn_config = uvicorn.Config(
        app,
        loop=loop,
        host=config.server.host,
        port=config.server.port,
        ws="websockets-sansio",
    )

    uvicorn_server = uvicorn.Server(uvicorn_config)
    await uvicorn_server.serve()


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        asyncio.run(run(loop=loop))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
