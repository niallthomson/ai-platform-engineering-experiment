# type: ignore

from dynaconf import Dynaconf, LazySettings
from dynaconf.vendor.box.box import Box
from typing import List, Dict
from dataclasses import dataclass

## IMPORTANT: Whenever changes are made to this file then
## Also update the documentation in 'agents/default/README.md'
## Also update Helm chart values and ConfigMaps it generates in 'helm/'


class ModelConfig:
    """Model configuration for LLM provider and parameters."""

    provider: str  # LLM provider (bedrock, openai)
    model_id: str  # Model identifier/name
    temperature: float  # Sampling temperature (0-1)
    top_p: float  # Nucleus sampling threshold (0-1)
    bedrock: "BedrockProviderConfig"  # AWS Bedrock configuration
    openai: "OpenAIProviderConfig"  # OpenAI configuration

    def __init__(self, settings: LazySettings):
        self.provider = settings.get("model.provider", "bedrock")
        self.model_id = settings.get(
            "model.model_id", "us.anthropic.claude-sonnet-4-20250514-v1:0"
        )
        self.temperature = float(settings.get("model.temperature", 0))
        self.top_p = float(settings.get("model.top_p", 1.0))
        self.bedrock = BedrockProviderConfig(settings)
        self.openai = OpenAIProviderConfig(settings)


class BedrockProviderConfig:
    """AWS Bedrock provider configuration."""

    region: str  # AWS region for Bedrock

    def __init__(self, settings: LazySettings):
        self.region = settings.get("model.bedrock.region", "us-west-2")


class OpenAIProviderConfig:
    """OpenAI provider configuration."""

    api_key: str  # OpenAI API key
    base_url: str  # OpenAI API base URL

    def __init__(self, settings: LazySettings):
        self.api_key = settings.get("model.openai.api_key", "")
        self.base_url = settings.get("model.openai.base_url", "")


class RedisTokenStoreConfig:
    """Redis configuration."""
    
    url: str  # Redis connection URL
    key_prefix: str  # Redis key prefix for tokens
    
    def __init__(self, settings: LazySettings):
        self.url = settings.get(
            "mcp.token_store.redis.url", "redis://localhost:6379"
        )
        self.key_prefix = settings.get(
            "mcp.token_store.redis.key_prefix", ""
        )


class TokenStoreConfig:
    """Token storage configuration."""
    
    mode: str  # Token storage mode (memory, redis)
    redis: RedisTokenStoreConfig  # Redis configuration
    encryption_key: str  # Encryption key for token storage
    
    def __init__(self, settings: LazySettings):
        self.mode = settings.get("mcp.token_store.mode", "memory")
        self.redis = RedisTokenStoreConfig(settings)
        self.encryption_key = settings.get("mcp.token_store.encryption_key", "")


class MCPConfig:
    """Model Context Protocol configuration."""

    enabled: bool  # Enable MCP server endpoint
    token_store: TokenStoreConfig  # Token storage configuration

    def __init__(self, settings: LazySettings):
        self.enabled = settings.get("mcp.enabled", False)
        self.token_store = TokenStoreConfig(settings)
        

class A2ATaskStoreRedisConfig:
    """Redis configuration for A2A task store."""

    url: str  # Redis connection URL
    key_prefix: str  # Key prefix for Redis keys

    def __init__(self, settings: LazySettings):
        self.url = settings.get("a2a.task_store.redis.url", "redis://localhost:6379")
        self.key_prefix = settings.get("a2a.task_store.redis.key_prefix", "")


class A2ATaskStoreConfig:
    """A2A task store configuration."""

    mode: str  # Storage mode (memory, redis)
    redis: A2ATaskStoreRedisConfig  # Redis configuration

    def __init__(self, settings: LazySettings):
        self.mode = settings.get("a2a.task_store.mode", "memory")
        self.redis = A2ATaskStoreRedisConfig(settings)
        
        
class A2AQueueManagerRedisConfig:
    """Redis configuration for A2A queue manager."""

    url: str  # Redis connection URL
    key_prefix: str  # Key prefix for Redis keys

    def __init__(self, settings: LazySettings):
        self.url = settings.get("a2a.queue_manager.redis.url", "redis://localhost:6379")
        self.key_prefix = settings.get("a2a.queue_manager.redis.key_prefix", "")


class A2AQueueManagerConfig:
    """A2A queue manager configuration."""

    mode: str  # Queue mode (none, redis)
    redis: A2AQueueManagerRedisConfig  # Redis configuration

    def __init__(self, settings: LazySettings):
        self.mode = settings.get("a2a.queue_manager.mode", "none")
        self.redis = A2AQueueManagerRedisConfig(settings)


class A2AConfig:
    """Agent-to-Agent configuration."""

    skills: List["AgentSkill"]  # Agent-to-Agent skills
    peer_agents: List[str]  # List of peer agent endpoint URLs
    task_store: A2ATaskStoreConfig  # Task store configuration
    queue_manager: A2AQueueManagerConfig  # Queue manager configuration

    def __init__(self, settings: LazySettings):
        self.skills = [AgentSkill(**skill) for skill in settings.get("a2a.skills", [])]
        self.peer_agents = settings.get("a2a.peer_agents", [])
        self.task_store = A2ATaskStoreConfig(settings)
        self.queue_manager = A2AQueueManagerConfig(settings)


class AuthConfig:
    """Authentication configuration."""

    mode: str  # Authentication mode (none, bearer, oidc)
    bearer: "BearerAuthConfig"  # Bearer token configuration
    oidc: "OIDCAuthConfig"  # OIDC configuration

    def __init__(self, settings: LazySettings):
        self.mode = settings.get("auth.mode", "none")
        self.bearer = BearerAuthConfig(settings)
        self.oidc = OIDCAuthConfig(settings)


class BearerAuthConfig:
    """Bearer token authentication configuration."""

    token: str | None  # Bearer token value

    def __init__(self, settings: LazySettings):
        self.token = settings.get("auth.bearer.token", None)


class OIDCAuthConfig:
    """OIDC authentication configuration."""

    configuration_url: str | None  # OIDC discovery URL
    client_id: str | None  # OIDC client ID
    client_secret: str | None  # OIDC client secret
    audiences: List[str]  # Expected token audiences

    def __init__(self, settings: LazySettings):
        self.configuration_url = settings.get("auth.oidc.configuration_url", None)
        self.client_id = settings.get("auth.oidc.client_id", None)
        self.client_secret = settings.get("auth.oidc.client_secret", None)
        self.audiences = settings.get("auth.oidc.audiences", [])


class ServerConfig:
    """Server configuration."""

    host: str  # Server bind address
    port: int  # Server port
    url: str | None  # Public server URL

    def __init__(self, settings: LazySettings):
        self.host = settings.get("server.host", "127.0.0.1")
        self.port = settings.get("server.port", 9000)
        self.url = settings.get("server.url", None)


class RedisStorageConfig:
    """Redis storage configuration."""

    url: str  # Redis connection URL
    key_prefix: str  # Key prefix for Redis keys

    def __init__(self, settings: LazySettings):
        self.url = settings.get("sessions.storage.redis.url", "redis://localhost:6379")
        self.key_prefix = settings.get("sessions.storage.redis.key_prefix", "agent")


class SessionStorageConfig:
    """Session storage configuration."""

    mode: str  # Storage mode (file, redis)
    redis: RedisStorageConfig  # Redis configuration

    def __init__(self, settings: LazySettings):
        self.mode = settings.get("sessions.storage.mode", "file")
        self.redis = RedisStorageConfig(settings)


@dataclass
class MCPServerTools:
    allowed: list[str]  # Allowed tool names
    rejected: list[str]  # Rejected tool names
    prefix: str = ""  # Tool name prefix

    def __init__(self, settings: Box):
        self.allowed = settings.get("allowed", [])
        self.rejected = settings.get("rejected", [])
        self.prefix = settings.get("prefix", None)


class MCPServer:
    name: str  # MCP server name
    url: str  # MCP server URL
    timeout: int = 30  # Request timeout in seconds
    env: Dict[str, str] = None  # Environment variables
    headers: Dict[str, str] = None  # HTTP headers
    authentication: str = "none"  # Authentication type (none, passthrough)
    authentication_header: str | None = (
        None  # Authentication header name (uses Authorization Bearer header if not specified)
    )
    tools: MCPServerTools = None  # Tool filtering and prefixing

    def __init__(self, settings: Box):
        self.name = settings.get("name")
        self.url = settings.get("url")
        self.timeout = settings.get("timeout", 30)
        self.env = settings.get("env", {})
        self.headers = settings.get("headers", {})
        self.authentication = settings.get("authentication", "none")
        self.authentication_header = settings.get("authentication_header", None)
        self.tools = MCPServerTools(settings.get("tools", Box()))


@dataclass
class AgentSkill:
    id: str  # Unique skill identifier
    name: str  # Skill name
    description: str  # Skill description
    examples: List[str]  # Example use cases


@dataclass
class AgentConfig:
    """Agent configuration abstraction using dynaconf."""

    settings: LazySettings  # Raw settings object
    name: str  # Agent name
    description: str  # Agent description
    system_prompt: str  # System prompt for LLM
    model: ModelConfig  # Model configuration
    mcp_servers: List[MCPServer]  # MCP server connections
    mcp: MCPConfig  # MCP server endpoint settings
    server: ServerConfig  # Server settings
    a2a: A2AConfig  # Agent-to-Agent settings
    auth: AuthConfig  # Authentication settings
    sessions: SessionStorageConfig  # Session storage settings

    def __init__(self, settings: LazySettings):
        self.settings = settings
        self.name = settings.get("name", "Default Agent")
        self.description = settings.get(
            "description", "This is the default agent configuration"
        )
        self.system_prompt = settings.get("system_prompt", "")
        self.model = ModelConfig(settings)
        self.mcp_servers = [
            MCPServer(server) for server in settings.get("mcp_servers", [])
        ]
        self.mcp = MCPConfig(settings)
        self.server = ServerConfig(settings)
        self.a2a = A2AConfig(settings)
        self.auth = AuthConfig(settings)
        self.sessions = SessionStorageConfig(settings)


def createConfig(config_file: str = "agent_config.yaml"):
    settings = Dynaconf(
        settings_files=[config_file],
        envvar_prefix="AGENT",
        environments=True,
        load_dotenv=True,
    )

    return AgentConfig(settings)
