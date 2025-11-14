import asyncio
import logging
from typing import List
from fastapi import FastAPI
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from .server import A2AServer
from strands.types.tools import AgentTool
from strands.session import SessionManager
from strands.session.file_session_manager import FileSessionManager
from a2a.types import AgentSkill
from .config import createConfig
from .agent_tool import createAgentTool
from .model_factory import create_model
from .security_factory import configure_security
import uvicorn
from a2a.server.agent_execution import RequestContext
from fastmcp import FastMCP
from uvicorn.config import LOGGING_CONFIG

format_prefix = "%(levelname)s | %(name)s |"
format = "{} %(message)s".format(format_prefix)

logging.basicConfig(format=format, level=logging.INFO)

LOGGING_CONFIG["formatters"]["default"]["fmt"] = format
LOGGING_CONFIG["formatters"]["access"]["fmt"] = (
    '{} %(client_addr)s - "%(request_line)s" %(status_code)s'.format(format_prefix)
)

logger = logging.getLogger(__name__)


async def run(loop):
    config = createConfig("agent_config.yaml")

    logger.info(f"Starting agent: {config.name}")

    model = create_model(config.model)

    all_tools: List[AgentTool] = []

    for server in config.mcp_servers:
        logger.info(f"Configuring MCP server: {server.name} -> {server.url}")
        mcp_client = MCPClient(
            lambda: streamablehttp_client(
                url=server.url,
                headers=server.headers,
            )
        )
        mcp_client.start()
        all_tools.extend(mcp_client.list_tools_sync())

    for agent_url in config.a2a.peer_agents:
        agent_tool = await createAgentTool(agent_url=agent_url)
        all_tools.extend([agent_tool])

    def agent_generator(context: RequestContext | None) -> Agent:
        session_manager: SessionManager | None = None
        if context is not None:
            if context.context_id is not None:
                context_id = context.context_id
                session_manager = FileSessionManager(session_id=context_id)

        return Agent(
            name=config.name,
            description=config.description,
            model=model,
            tools=all_tools,
            system_prompt=config.system_prompt,
            callback_handler=None,
            session_manager=session_manager,
        )

    mcp = FastMCP(config.name)

    @mcp.tool()
    def query(query: str) -> list[str]:
        """Execute a natural language query using the agent"""
        agent = agent_generator(None)
        response = agent(query)

        return [
            content["text"]
            for content in response.message["content"]
            if "text" in content
        ]

    mcp_app = mcp.http_app("/http")

    app = FastAPI(lifespan=mcp_app.lifespan)

    app.mount("/mcp", mcp_app)

    security_schemes = configure_security(app, config.a2a.security)

    server_config = config.a2a.server

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
        http_url=server_config.url,
        skills=skills,
        agent_generator=agent_generator,
        security_schemes=security_schemes,
    )

    fastapi_app = a2a_server.to_fastapi_app()

    @app.get("/health")
    @app.get("/ping")
    async def health_check():
        return {"status": "healthy"}

    app.mount("/", fastapi_app)

    uvicorn_config = uvicorn.Config(
        app,
        loop=loop,
        host=server_config.host,
        port=server_config.port,
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
