"""Resource manager for handling application lifecycle cleanup."""

import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class ResourceManager:
    """Manages cleanup of resources during application shutdown."""

    def __init__(self):
        self._resources: list[tuple[str, Callable[[], Awaitable[None]]]] = []

    def register(self, name: str, cleanup: Callable[[], Awaitable[None]]):
        """Register a resource for cleanup during shutdown."""
        self._resources.append((name, cleanup))
        logger.debug(f"Registered resource for cleanup: {name}")

    async def cleanup_all(self):
        """Clean up all registered resources in reverse order."""
        for name, cleanup in reversed(self._resources):
            try:
                await cleanup()
                logger.info(f"Cleaned up: {name}")
            except Exception as e:
                logger.error(f"Failed to cleanup {name}: {e}")
