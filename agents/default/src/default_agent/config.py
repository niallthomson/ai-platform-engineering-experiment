# type: ignore

from dynaconf import Dynaconf, LazySettings
from typing import List, Dict
from dataclasses import dataclass


class ModelConfig:
    def __init__(self, settings: LazySettings):
        self.provider = settings.get("model.provider", "bedrock")
        self.model_id = settings.get(
            "model.name", "us.anthropic.claude-sonnet-4-20250514-v1:0"
        )
        self.temperature = float(settings.get("model.temperature", 0))
        self.top_p = float(settings.get("model.name", 1.0))

        self.bedrock = BedrockProviderConfig(settings)
        self.openai = OpenAIProviderConfig(settings)


class BedrockProviderConfig:
    def __init__(self, settings: LazySettings):
        self.region = settings.get("model.bedrock.region", "us-west-2")


class OpenAIProviderConfig:
    def __init__(self, settings: LazySettings):
        self.api_key = settings.get("model.openai.api_key", "")
        self.base_url = settings.get("model.openai.base_url", "")


class A2AConfig:
    def __init__(self, settings: LazySettings):
        self.server = ServerConfig(settings)
        self.skills = [AgentSkill(**skill) for skill in settings.get("a2a.skills", [])]
        self.peer_agents = settings.get("a2a.peer_agents", [])
        self.security = A2ASecurityConfig(settings)


class A2ASecurityConfig:
    def __init__(self, settings: LazySettings):
        self.mode = settings.get("a2a.security.mode", "none")
        self.bearer = SecurityBearerAuth(settings)
        self.oauth = SecurityOAuth2Auth(settings)


class SecurityBearerAuth:
    def __init__(self, settings: LazySettings):
        self.token = settings.get("a2a.security.bearer.token", None)


class SecurityOAuth2Auth:
    def __init__(self, settings: LazySettings):
        self.jwks_url = settings.get("a2a.security.oauth.jwks_url", None)
        self.audience = settings.get("a2a.security.oauth.audience", None)
        self.issuer = settings.get("a2a.security.oauth.issuer", None)


class ServerConfig:
    def __init__(self, settings: LazySettings):
        self.host = settings.get("a2a.server.host", "127.0.0.1")
        self.port = settings.get("a2a.server.port", 9000)
        self.url = settings.get("a2a.server.url", None)


@dataclass
class MCPServer:
    name: str
    url: str
    timeout: int = 30
    env: Dict[str, str] = None
    headers: Dict[str, str] = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.env is None:
            self.env = {}


@dataclass
class AgentSkill:
    id: str
    name: str
    description: str
    examples: List[str]


@dataclass
class AgentConfig:
    """Agent configuration abstraction using dynaconf"""

    def __init__(self, settings: LazySettings):
        self.settings = settings

        self.name = settings.get("name", "Default Agent")
        self.description = settings.get(
            "description", "This is the default agent configuration"
        )
        self.system_prompt = settings.get("system_prompt", "")

        self.model = ModelConfig(settings)

        self.mcp_servers = [
            MCPServer(**server) for server in settings.get("mcp_servers", [])
        ]

        self.a2a = A2AConfig(settings)


def createConfig(config_file: str = "agent_config.yaml"):
    settings = Dynaconf(
        settings_files=[config_file],
        envvar_prefix="AGENT",
        environments=True,
        load_dotenv=True,
    )

    return AgentConfig(settings)
