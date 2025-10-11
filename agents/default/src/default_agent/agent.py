import asyncio
import logging
from typing import List
from fastapi import FastAPI
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from .server import A2AServer
from strands.models import Model, BedrockModel
from strands.models.openai import OpenAIModel
from strands.types.tools import AgentTool
from strands.session.file_session_manager import FileSessionManager
from a2a.types import AgentSkill, SecurityScheme, HTTPAuthSecurityScheme, OAuth2SecurityScheme, OAuthFlows, AuthorizationCodeOAuthFlow
from .bearer_auth import BearerAuthMiddleware
from .oauth_auth import OAuth2JWTAuthMiddleware
from .config import createConfig
from .agent_tool import createAgentTool
import uvicorn

async def run(loop):
    config = createConfig("agent_config.yaml")

    logging.basicConfig(level=logging.INFO)

    logging.info(f"Starting agent: {config.name}")

    model: Model

    logging.info(f"Model provider: {config.model.provider}")
    logging.info(f"Model ID: {config.model.model_id}")

    match config.model.provider:
        case "bedrock":
            logging.info(f"Bedrock region: {config.model.bedrock.region}")
            
            model = BedrockModel(
                model_id=config.model.model_id,
                temperature=config.model.temperature,
                top_p=config.model.temperature,
                region_name=config.model.bedrock.region
            )
            
        case "openai":
            logging.info(f"OpenAI base URL: {config.model.openai.base_url}")
            
            model = OpenAIModel(
                model_id=config.model.model_id,
                client_args={
                    "api_key": config.model.openai.api_key,
                    "base_url": config.model.openai.base_url
                },
                params={
                    "temperature":config.model.temperature,
                    "top_p":config.model.temperature
                }
            )
            
        case _:
            logging.error(f"Unknown model provider: {config.model.provider}")
            exit(1)
        
    all_tools : List[AgentTool] = []

    for server in config.mcp_servers:
        logging.info(f"Configuring MCP server: {server.name} -> {server.url}")
        # Create httpx
        mcp_client = MCPClient(lambda: streamablehttp_client(
            url=server.url, 
            headers=server.headers,
        ))
        mcp_client.start()
        all_tools.extend(mcp_client.list_tools_sync())
        
    for agent_url in config.a2a.peer_agents:
        agent_tool = await createAgentTool(agent_url=agent_url)
        all_tools.extend([agent_tool])

    def agent_generator(context_id: str | None)-> Agent:
        if context_id is None:
            context_id = "default"
            
        session_manager = FileSessionManager(session_id=context_id)
        return Agent(name=config.name,
            description=config.description,
            model=model,
            tools=all_tools,
            system_prompt=config.system_prompt,
            callback_handler=None, 
            session_manager=session_manager,
        )
        
    security_mode = config.a2a.security.mode
    
    security_schemes : dict[str, SecurityScheme] | None = None
    
    app = FastAPI() 

    match security_mode:
        case "none":
            logging.info("Security mode: none")
            
        case "bearer":
            logging.info("Security mode: bearer")
            bearer_auth = config.a2a.security.bearer
            
            if bearer_auth.token is None:
                logging.error("Bearer token not configured")
                exit(1)
            
            app.add_middleware(
                BearerAuthMiddleware, # type: ignore
                token=bearer_auth.token,
                public_paths=['/.well-known/agent.json', '/.well-known/agent-card.json', '/health', '/ping'],
            )
            
            security_schemes = {
                    "bearer": SecurityScheme(root=HTTPAuthSecurityScheme(
                        scheme="Bearer",
                        description="Bearer token",
                    )
                )
            }
            
        case "oauth":
            logging.info("Security mode: oauth")
            oauth2_auth = config.a2a.security.oauth
            
            app.add_middleware(
                OAuth2JWTAuthMiddleware, # type: ignore
                jwks_url=oauth2_auth.jwks_url,
                audience=oauth2_auth.audience,
                issuer=oauth2_auth.issuer,
                public_paths=['/.well-known/agent.json', '/.well-known/agent-card.json', '/health', '/ping'],
            )
            
        case _:
            logging.error(f"Unknown security mode: {security_mode}")
            exit(1)

    server_config = config.a2a.server

    skills = list(map(lambda skill: AgentSkill(id=skill.id, name=skill.name, description=skill.description, examples=skill.examples, tags=[]), config.a2a.skills))

    a2a_server = A2AServer(http_url=server_config.url, skills=skills, agent_generator=agent_generator, security_schemes=security_schemes)

    fastapi_app = a2a_server.to_fastapi_app()

    @app.get("/health")
    @app.get("/ping")
    async def health_check():
        return {"status": "healthy"}

    app.mount("/", fastapi_app)

    uvicorn_config = uvicorn.Config(app, loop=loop, host=server_config.host, port=server_config.port)
    
    uvicorn_server = uvicorn.Server(uvicorn_config)
    await uvicorn_server.serve()

def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(loop))
    
    