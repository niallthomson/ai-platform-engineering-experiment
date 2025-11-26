# type: ignore

from dynaconf import Dynaconf, LazySettings
from dataclasses import dataclass

## IMPORTANT: Whenever changes are made to this file then
## Also update the documentation in 'slack-bot/README.md'
## Also update Helm chart values and ConfigMaps it generates in 'helm/'


class SlackConfig:
    """Slack integration configuration."""
    
    bot_token: str  # Slack bot OAuth token
    app_token: str  # Slack app-level token for socket mode
    
    def __init__(self, settings: LazySettings):
        self.bot_token = settings.get("slack.bot_token", "")
        self.app_token = settings.get("slack.app_token", "")


class BearerAuthConfig:
    """Bearer token authentication configuration."""
    
    token: str  # Bearer token for A2A authentication
    
    def __init__(self, settings: LazySettings):
        self.token = settings.get("auth.bearer.token", "")


class RedisConfig:
    """Redis configuration."""
    
    url: str  # Redis connection URL
    key_prefix: str  # Redis key prefix for tokens
    
    def __init__(self, settings: LazySettings):
        self.url = settings.get(
            "auth.oidc.token_store.redis.url", "redis://localhost:6379"
        )
        self.key_prefix = settings.get(
            "auth.oidc.token_store.redis.key_prefix", ""
        )


class TokenStoreConfig:
    """Token storage configuration."""
    
    backend: str  # Token storage backend (memory, redis)
    redis: RedisConfig  # Redis configuration
    encryption_key: str  # Encryption key for token storage
    
    def __init__(self, settings: LazySettings):
        self.backend = settings.get("auth.oidc.token_store.backend", "memory")
        self.redis = RedisConfig(settings)
        self.encryption_key = settings.get("auth.oidc.token_store.encryption_key", "")


class OIDCAuthConfig:
    """OIDC authentication configuration."""
    
    configuration_url: str  # OIDC discovery URL
    client_id: str  # OIDC client ID
    client_secret: str  # OIDC client secret
    scope: str  # OIDC scopes
    token_store: TokenStoreConfig  # Token storage configuration
    
    def __init__(self, settings: LazySettings):
        self.configuration_url = settings.get("auth.oidc.configuration_url", "")
        self.client_id = settings.get("auth.oidc.client_id", "")
        self.client_secret = settings.get("auth.oidc.client_secret", "")
        self.scope = settings.get("auth.oidc.scope", "openid profile")
        self.token_store = TokenStoreConfig(settings)


class AuthConfig:
    """Authentication configuration."""
    
    mode: str  # Authentication mode (bearer, oidc)
    bearer: BearerAuthConfig  # Bearer token configuration
    oidc: OIDCAuthConfig  # OIDC configuration
    
    def __init__(self, settings: LazySettings):
        self.mode = settings.get("auth.mode", "bearer")
        self.bearer = BearerAuthConfig(settings)
        self.oidc = OIDCAuthConfig(settings)


class A2AConfig:
    """Agent-to-Agent configuration."""
    
    url: str  # Agent-to-Agent endpoint URL
    
    def __init__(self, settings: LazySettings):
        self.url = settings.get("a2a.url", "")


@dataclass
class BotConfig:
    """Slack bot configuration abstraction using dynaconf."""
    
    settings: LazySettings  # Raw settings object
    slack: SlackConfig  # Slack configuration
    a2a: A2AConfig  # Agent-to-Agent settings
    auth: AuthConfig  # Authentication settings

    def __init__(self, settings: LazySettings):
        self.settings = settings
        self.slack = SlackConfig(settings)
        self.a2a = A2AConfig(settings)
        self.auth = AuthConfig(settings)

    def validate(self):
        """Validate configuration consistency."""
        if self.auth.mode == "bearer":
            if not self.auth.bearer.token:
                raise ValueError("auth.mode=bearer requires auth.bearer.token")
        elif self.auth.mode == "oidc":
            if not self.auth.oidc.configuration_url or not self.auth.oidc.client_id:
                raise ValueError(
                    "auth.mode=oidc requires auth.oidc.configuration_url and auth.oidc.client_id"
                )
            if self.auth.oidc.token_store.backend == "redis" and not self.auth.oidc.token_store.encryption_key:
                raise ValueError(
                    "auth.oidc.token_store.backend=redis requires auth.oidc.token_store.encryption_key"
                )
        else:
            raise ValueError(
                f"Invalid auth.mode: {self.auth.mode}. Must be 'bearer' or 'oidc'"
            )


def createConfig(config_file: str = "bot_config.yaml"):
    settings = Dynaconf(
        settings_files=[config_file],
        envvar_prefix="SLACKBOT",
        environments=True,
        load_dotenv=True,
    )

    config = BotConfig(settings)
    config.validate()
    return config
