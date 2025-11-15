# type: ignore

from dynaconf import Dynaconf, LazySettings
from dataclasses import dataclass


class SlackConfig:
    def __init__(self, settings: LazySettings):
        self.bot_token = settings.get("slack.bot_token", "")
        self.app_token = settings.get("slack.app_token", "")


class A2ASecurityConfig:
    def __init__(self, settings: LazySettings):
        self.mode = settings.get("a2a.security.mode", "bearer")
        self.bearer = SecurityBearerAuth(settings)


class SecurityBearerAuth:
    def __init__(self, settings: LazySettings):
        self.token = settings.get("a2a.security.bearer.token", "")


class A2AConfig:
    def __init__(self, settings: LazySettings):
        self.url = settings.get("a2a.url", "")
        self.security = A2ASecurityConfig(settings)


@dataclass
class BotConfig:
    """Slack bot configuration abstraction using dynaconf"""

    def __init__(self, settings: LazySettings):
        self.settings = settings
        self.slack = SlackConfig(settings)
        self.a2a = A2AConfig(settings)


def createConfig(config_file: str = "bot_config.yaml"):
    settings = Dynaconf(
        settings_files=[config_file],
        envvar_prefix="SLACKBOT",
        environments=True,
        load_dotenv=True,
    )

    return BotConfig(settings)
