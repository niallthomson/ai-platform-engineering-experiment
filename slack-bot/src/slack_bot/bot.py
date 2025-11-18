"""Slack bot main module."""

import asyncio
import logging
import signal
import os

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from .config import createConfig
from .handlers import setup_handlers
from .auth_manager import AuthManager
from .oidc_device_flow import OIDCDeviceFlow
from .token_store import InMemoryTokenStore, RedisTokenStore

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()

logging.basicConfig(level=LOGLEVEL)

logger = logging.getLogger(__name__)
shutdown_event = asyncio.Event()


async def handle_errors(err, request_body):
    """Global error handler for Slack events."""
    logger.error("Slack error occurred: %s - Body: %s", err, request_body)


def handle_shutdown(signum, frame):
    """Handle shutdown signals."""
    logger.info("Received signal %s, initiating shutdown...", signum)
    shutdown_event.set()


async def create_token_store(token_store_config):
    """Factory for token store based on config."""
    if token_store_config.backend == "redis":
        try:
            import redis.asyncio as redis
            client = redis.from_url(token_store_config.redis_url)
            await client.ping()
            logger.info("Using Redis token store at %s", token_store_config.redis_url)
            return RedisTokenStore(client, token_store_config.key_prefix)
        except ImportError:
            logger.error("Redis backend requested but redis package not installed")
            raise
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            raise
    else:
        logger.info("Using in-memory token store")
        return InMemoryTokenStore()


async def start_bot():
    """Initialize and start the Slack bot."""
    logger.info("Initializing Slack bot...")

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    config = createConfig()

    if not config.slack.bot_token or not config.slack.app_token:
        raise ValueError("Slack bot_token and app_token must be configured")

    logger.info("A2A agent: %s", config.a2a.url)
    logger.info("Auth mode: %s", config.auth.mode)

    slack_app = AsyncApp(token=config.slack.bot_token)
    slack_app.error(handle_errors)

    auth_manager = None
    default_token = ""

    if config.auth.mode == "bearer":
        default_token = config.auth.bearer.token
        logger.info("Using shared bearer token authentication")
    elif config.auth.mode == "oidc":
        logger.info("Using OIDC device flow with config: %s", config.auth.oidc.configuration_url)
        oidc_flow = OIDCDeviceFlow(
            configuration_url=config.auth.oidc.configuration_url,
            client_id=config.auth.oidc.client_id,
            client_secret=config.auth.oidc.client_secret,
            scope=config.auth.oidc.scope,
        )
        token_store = await create_token_store(config.auth.oidc.token_store)
        auth_manager = AuthManager(oidc_flow, token_store)

    setup_handlers(slack_app, config.a2a.url, default_token, auth_manager)

    socket_handler = AsyncSocketModeHandler(slack_app, config.slack.app_token)

    await socket_handler.connect_async()
    logger.info("Slack bot connected and running")

    await shutdown_event.wait()

    logger.info("Shutting down Slack bot...")
    await socket_handler.close_async()


def main():
    """Entry point for the Slack bot."""
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.warning("Slack bot shutdown requested (KeyboardInterrupt).")
    except Exception:
        logger.exception("Slack bot encountered exception.")
    finally:
        logger.info("Slack bot has shutdown.")


if __name__ == "__main__":
    main()
