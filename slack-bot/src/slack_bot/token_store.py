"""Token storage interface and implementations."""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class StoredToken:
    access_token: str
    expires_at: datetime
    refresh_token: str | None = None

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "expires_at": self.expires_at.isoformat(),
            "refresh_token": self.refresh_token,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StoredToken":
        return cls(
            access_token=data["access_token"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            refresh_token=data.get("refresh_token"),
        )


class TokenStore(ABC):
    """Abstract token store interface."""

    @abstractmethod
    async def store_token(
        self,
        slack_user_id: str,
        access_token: str,
        expires_in: int,
        refresh_token: str | None = None,
    ):
        """Store access token for a Slack user."""
        pass

    @abstractmethod
    async def get_token(self, slack_user_id: str) -> str | None:
        """Get valid access token for a Slack user."""
        pass

    @abstractmethod
    async def has_valid_token(self, slack_user_id: str) -> bool:
        """Check if user has a valid token."""
        pass

    @abstractmethod
    async def remove_token(self, slack_user_id: str):
        """Remove token for a user."""
        pass


class InMemoryTokenStore(TokenStore):
    """In-memory token store."""

    def __init__(self):
        self._tokens: dict[str, StoredToken] = {}

    async def store_token(
        self,
        slack_user_id: str,
        access_token: str,
        expires_in: int,
        refresh_token: str | None = None,
    ):
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        self._tokens[slack_user_id] = StoredToken(
            access_token=access_token,
            expires_at=expires_at,
            refresh_token=refresh_token,
        )
        logger.info("Stored token for user %s", slack_user_id)

    async def get_token(self, slack_user_id: str) -> str | None:
        stored = self._tokens.get(slack_user_id)
        if not stored:
            return None

        if datetime.now() >= stored.expires_at:
            logger.info("Token expired for user %s", slack_user_id)
            del self._tokens[slack_user_id]
            return None

        return stored.access_token

    async def has_valid_token(self, slack_user_id: str) -> bool:
        return await self.get_token(slack_user_id) is not None

    async def remove_token(self, slack_user_id: str):
        if slack_user_id in self._tokens:
            del self._tokens[slack_user_id]
            logger.info("Removed token for user %s", slack_user_id)


class RedisTokenStore(TokenStore):
    """Redis-based token store."""

    def __init__(self, redis_client, key_prefix: str = "slack_token:"):
        self.redis = redis_client
        self.key_prefix = key_prefix

    def _make_key(self, slack_user_id: str) -> str:
        return f"{self.key_prefix}{slack_user_id}"

    async def store_token(
        self,
        slack_user_id: str,
        access_token: str,
        expires_in: int,
        refresh_token: str | None = None,
    ):
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        token = StoredToken(
            access_token=access_token,
            expires_at=expires_at,
            refresh_token=refresh_token,
        )

        key = self._make_key(slack_user_id)
        await self.redis.setex(
            key,
            expires_in,
            json.dumps(token.to_dict()),
        )
        logger.info("Stored token for user %s in Redis", slack_user_id)

    async def get_token(self, slack_user_id: str) -> str | None:
        key = self._make_key(slack_user_id)
        data = await self.redis.get(key)

        if not data:
            return None

        try:
            token = StoredToken.from_dict(json.loads(data))
            if datetime.now() >= token.expires_at:
                await self.remove_token(slack_user_id)
                return None
            return token.access_token
        except Exception as e:
            logger.error("Error deserializing token for user %s: %s", slack_user_id, e)
            return None

    async def has_valid_token(self, slack_user_id: str) -> bool:
        return await self.get_token(slack_user_id) is not None

    async def remove_token(self, slack_user_id: str):
        key = self._make_key(slack_user_id)
        await self.redis.delete(key)
        logger.info("Removed token for user %s from Redis", slack_user_id)
