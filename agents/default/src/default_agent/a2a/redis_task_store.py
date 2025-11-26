"""Redis-backed task store implementation for the A2A Python SDK."""

import json
from typing import Any, Optional
import redis.asyncio as redis
from a2a.server.tasks.task_store import TaskStore
from a2a.server.context import ServerCallContext
from a2a.types import Task


class RedisTaskStore(TaskStore):
    """Redis-backed task store for persisting A2A tasks.
    
    Stores task data as JSON in Redis with configurable key prefixes.
    
    Args:
        redis_client: Async Redis client instance.
        prefix: Optional key prefix for namespacing.
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = ""):
        self.redis = redis_client
        self.prefix = prefix

    def _task_key(self, task_id: str) -> str:
        """Generate Redis key for a task ID."""
        return f"{self.prefix}task:{task_id}"

    async def save(self, task: Task, context: ServerCallContext) -> None:
        """Persist task to Redis as JSON."""
        task_data = task.model_dump() if hasattr(task, "model_dump") else task
        await self.redis.set(self._task_key(task.id), json.dumps(task_data, default=str))

    async def get(self, task_id: str, context: ServerCallContext) -> Optional[Task]:
        """Retrieve task from Redis by ID, returns None if not found."""
        data = await self.redis.get(self._task_key(task_id))
        if not data:
            return None
        task_data = json.loads(data)
        return Task(**task_data)

    async def delete(self, task_id: str, context: ServerCallContext) -> None:
        """Remove task from Redis."""
        await self.redis.delete(self._task_key(task_id))
