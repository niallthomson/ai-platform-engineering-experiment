"""Slack bot main module."""

import asyncio
import logging
import signal

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from .config import createConfig
from .handlers import setup_handlers

logger = logging.getLogger(__name__)
shutdown_event = asyncio.Event()


async def handle_errors(err, request_body):
    """Global error handler for Slack events."""
    logger.error("Slack error occurred: %s - Body: %s", err, request_body)


def handle_shutdown(signum, frame):
    """Handle shutdown signals."""
    logger.info("Received signal %s, initiating shutdown...", signum)
    shutdown_event.set()


async def start_bot():
    """Initialize and start the Slack bot."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Initializing Slack bot...")

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    config = createConfig()

    if not config.slack.bot_token or not config.slack.app_token:
        raise ValueError("Slack bot_token and app_token must be configured")

    slack_app = AsyncApp(token=config.slack.bot_token)
    slack_app.error(handle_errors)
    setup_handlers(slack_app, config.a2a.url, config.a2a.security.bearer.token)

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
