"""Redis-based session repository for Strands."""

import json
import logging
from typing import Any, Optional
import redis

from strands.session import SessionRepository
from strands.types.exceptions import SessionException
from strands.types.session import Session, SessionAgent, SessionMessage

logger = logging.getLogger(__name__)


class RedisSessionRepository(SessionRepository):
    """Redis session repository with configurable key prefix.
    
    Key structure:
    {prefix}session:{session_id}
    {prefix}session:{session_id}:agent:{agent_id}
    {prefix}session:{session_id}:agent:{agent_id}:message:{message_id}
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = ""):
        self.redis = redis_client
        self.prefix = prefix

    def _session_key(self, session_id: str) -> str:
        if ":" in session_id:
            raise ValueError(f"session_id cannot contain ':': {session_id}")
        return f"{self.prefix}session:{session_id}"

    def _agent_key(self, session_id: str, agent_id: str) -> str:
        if ":" in agent_id:
            raise ValueError(f"agent_id cannot contain ':': {agent_id}")
        return f"{self.prefix}session:{session_id}:agent:{agent_id}"

    def _message_key(self, session_id: str, agent_id: str, message_id: int) -> str:
        if not isinstance(message_id, int):
            raise TypeError(f"message_id must be integer, got {type(message_id)}")
        return f"{self.prefix}session:{session_id}:agent:{agent_id}:message:{message_id}"

    def _get_json(self, key: str) -> dict[str, Any] | None:
        try:
            data = self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            raise SessionException(f"Redis read error for {key}: {e}") from e

    def _set_json(self, key: str, data: dict[str, Any]) -> None:
        try:
            self.redis.set(key, json.dumps(data, default=str))
        except Exception as e:
            raise SessionException(f"Redis write error for {key}: {e}") from e

    def create_session(self, session: Session, **kwargs: Any) -> Session:
        key = self._session_key(session.session_id)
        if self.redis.exists(key):
            raise SessionException(f"Session {session.session_id} already exists")
        self._set_json(key, session.to_dict())
        return session

    def read_session(self, session_id: str, **kwargs: Any) -> Optional[Session]:
        data = self._get_json(self._session_key(session_id))
        return Session.from_dict(data) if data else None

    def create_agent(self, session_id: str, session_agent: SessionAgent, **kwargs: Any) -> None:
        key = self._agent_key(session_id, session_agent.agent_id)
        self._set_json(key, session_agent.to_dict())

    def read_agent(self, session_id: str, agent_id: str, **kwargs: Any) -> Optional[SessionAgent]:
        data = self._get_json(self._agent_key(session_id, agent_id))
        return SessionAgent.from_dict(data) if data else None

    def update_agent(self, session_id: str, session_agent: SessionAgent, **kwargs: Any) -> None:
        existing = self.read_agent(session_id, session_agent.agent_id)
        if not existing:
            raise SessionException(f"Agent {session_agent.agent_id} not found in session {session_id}")
        
        session_agent.created_at = existing.created_at
        key = self._agent_key(session_id, session_agent.agent_id)
        self._set_json(key, session_agent.to_dict())

    def create_message(self, session_id: str, agent_id: str, session_message: SessionMessage, **kwargs: Any) -> None:
        key = self._message_key(session_id, agent_id, session_message.message_id)
        self._set_json(key, session_message.to_dict())

    def read_message(self, session_id: str, agent_id: str, message_id: int, **kwargs: Any) -> Optional[SessionMessage]:
        data = self._get_json(self._message_key(session_id, agent_id, message_id))
        return SessionMessage.from_dict(data) if data else None

    def update_message(self, session_id: str, agent_id: str, session_message: SessionMessage, **kwargs: Any) -> None:
        existing = self.read_message(session_id, agent_id, session_message.message_id)
        if not existing:
            raise SessionException(f"Message {session_message.message_id} not found")
        
        session_message.created_at = existing.created_at
        key = self._message_key(session_id, agent_id, session_message.message_id)
        self._set_json(key, session_message.to_dict())

    def list_messages(
        self, session_id: str, agent_id: str, limit: Optional[int] = None, offset: int = 0, **kwargs: Any
    ) -> list[SessionMessage]:
        pattern = f"{self._agent_key(session_id, agent_id)}:message:*"
        
        try:
            keys = []
            cursor = 0
            while True:
                cursor, batch = self.redis.scan(cursor=cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break

            indexed_keys = []
            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                msg_id = int(key_str.split(":")[-1])
                indexed_keys.append((msg_id, key_str))

            sorted_keys = [k for _, k in sorted(indexed_keys)]
            paginated_keys = sorted_keys[offset:offset + limit] if limit else sorted_keys[offset:]

            messages = []
            for key in paginated_keys:
                data = self._get_json(key)
                if data:
                    messages.append(SessionMessage.from_dict(data))

            return messages

        except Exception as e:
            raise SessionException(f"Error listing messages: {e}") from e
