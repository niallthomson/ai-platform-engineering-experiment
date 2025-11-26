from .a2a.disable_a2a_tracing import disable_a2a_tracing

disable_a2a_tracing()

from strands.tools.mcp.mcp_instrumentation import mcp_instrumentation

mcp_instrumentation()

# ruff: noqa: E402
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .a2a.server import A2AServer
from a2a.types import AgentSkill
from .config import createConfig
from .agent_registry import A2AAgentRegistry
from .security_factory import configure_security
from default_agent.agent_factory import build_agent
from .mcp_factory import create_mcp_server
from .a2a.executor import StrandsAgentInstance
from .resource_manager import ResourceManager
from .strands.redis_session_repository import RedisSessionRepository
import uvicorn
import redis
from redis.asyncio import client as redis_async
import asyncio
from a2a.server.agent_execution import RequestContext
from uvicorn.config import LOGGING_CONFIG
from strands.telemetry import StrandsTelemetry
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from .a2a.redis_task_store import RedisTaskStore

if "OTEL_EXPORTER_OTLP_ENDPOINT" in os.environ:
    strands_telemetry = StrandsTelemetry()
    strands_telemetry.setup_otlp_exporter()  # Send traces to OTLP endpoint
    # strands_telemetry.setup_console_exporter()  # Print traces to console
    strands_telemetry.setup_meter(enable_otlp_exporter=True)

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

    resource_manager = ResourceManager()
    
    session_repository = None
    if config.sessions.mode == "redis":
        logger.info(f"Using Redis for session storage ({config.sessions.redis.url})")
        redis_client = redis.from_url(config.sessions.redis.url)
        resource_manager.register(
            "redis_session_client",
            lambda: asyncio.to_thread(redis_client.close)
        )
        session_repository = RedisSessionRepository(
            redis_client=redis_client,
            prefix=config.sessions.redis.key_prefix
        )
        
    task_store = None
    
    if config.a2a.task_store.mode == "redis":
        logger.info(f"Using Redis for task store ({config.a2a.task_store.redis.url})")
        async_redis_client = redis_async.Redis.from_url(config.a2a.task_store.redis.url)
        resource_manager.register(
            "redis_task_store_client",
            async_redis_client.aclose
        )

        task_store = RedisTaskStore(
            redis_client=async_redis_client,
            prefix=config.a2a.task_store.redis.key_prefix
        )
    
    registry = A2AAgentRegistry(agent_urls=config.a2a.peer_agents, refresh_interval=60)
    await registry.start()
    resource_manager.register("agent_registry", registry.stop)

    def agent_generator(context: RequestContext | None) -> StrandsAgentInstance:
        authorization_header: str | None = None
        username: str | None = None
        context_id: str | None = None

        if context is not None:
            if context.context_id is not None:
                context_id = context.context_id

            if context.call_context is not None:
                if context.call_context.user.is_authenticated:
                    username = context.call_context.user.user_name

                call_headers = context.call_context.state["headers"]

                authorization_header = call_headers.get("authorization", None)

        return build_agent(config, registry, session_repository, context_id, authorization_header, username)

    @asynccontextmanager
    async def resource_manager_lifespan(app: FastAPI):
        yield
        await resource_manager.cleanup_all()
        
    @asynccontextmanager
    async def dummy_lifespan(app: FastAPI):
        yield
        
    @asynccontextmanager
    async def combined_lifespan(app: FastAPI):
        async with resource_manager_lifespan(app):
            async with mcp_app.lifespan(app) if mcp_app is not None else dummy_lifespan(app):
                yield

    mcp_app = None

    if config.mcp.enabled:
        logger.info("MCP enabled")
        mcp_app = create_mcp_server(config, resource_manager)

    app = FastAPI(lifespan=combined_lifespan)

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
        task_store=task_store,
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
        timeout_graceful_shutdown=120,
    )

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/health,.well-known/*,/mcp*,/register,/authorize,/consent,/consent/submit,/auth/callback,/token",
        exclude_spans=["receive", "send"],
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
