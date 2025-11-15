import asyncio
import logging
from typing import Any, Optional
from datetime import datetime
from uuid import uuid4
import httpx
from typing_extensions import override
from jinja2 import Template
from strands.types.tools import AgentTool, ToolGenerator, ToolSpec, ToolUse
from strands.types._events import ToolResultEvent
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory, Client
from a2a.client.client_task_manager import ClientTaskManager
from a2a.types import AgentCard, Message, Part, Role, TextPart, Task, AgentCapabilities
from a2a.utils.message import get_message_text

DESCRIPTION_TEMPLATE = Template(
    """
Use this tool to delegate tasks to the {{ name }} agent.

{{ description }}
{%- if skills %}

This agent can help with:
{%- for skill in skills %}
- {{ skill.name }}: {{ skill.description }}
{%- if skill.examples %}
  Examples: {{ skill.examples|join('; ') }}
{%- endif %}
{%- endfor %}
{%- endif %}

Send natural language messages to this agent. The response includes a contextId - provide this contextId in follow-up messages to maintain conversation continuity with the agent.
""".strip()
)

logger = logging.getLogger(__name__)


class DummyClient:
    async def send_message(self, msg: Message):
        raise RuntimeError("Agent is not available")


class AgentRegistryEntry:
    url: str
    card: AgentCard
    client: Client
    resolved: bool
    last_attempt: Optional[datetime]
    error: Optional[str]

    def __init__(self, url: str):
        self.url = url
        self.card = AgentCard(
            name=f"Unavailable Agent ({url})",
            description=f"Agent at {url} is currently unavailable",
            version="0.0.0",
            capabilities=AgentCapabilities(),
            default_input_modes=[],
            default_output_modes=[],
            skills=[],
            url=url,
        )
        self.client = DummyClient()  # type: ignore
        self.resolved = False
        self.last_attempt = None
        self.error = None


class A2AAgentRegistry:
    entries: dict[str, AgentRegistryEntry]
    httpx_client: httpx.AsyncClient
    refresh_interval: int
    _refresh_task: Optional[asyncio.Task]
    _running: bool

    def __init__(self, agent_urls: list[str], refresh_interval: int = 60):
        self.entries = {url: AgentRegistryEntry(url) for url in agent_urls}
        self.httpx_client = httpx.AsyncClient(timeout=120)
        self.refresh_interval = refresh_interval
        self._refresh_task = None
        self._running = False

    async def _fetch_agent_card(self, entry: AgentRegistryEntry) -> None:
        try:
            resolver = A2ACardResolver(
                httpx_client=self.httpx_client, base_url=entry.url
            )
            card = await resolver.get_agent_card()

            config = ClientConfig(httpx_client=self.httpx_client, streaming=False)
            factory = ClientFactory(config)
            client = factory.create(card)

            entry.card = card
            entry.client = client
            entry.resolved = True
            entry.error = None
            logger.debug(
                f"Successfully loaded agent card for {card.name} at {entry.url}"
            )
        except Exception as e:
            entry.error = str(e)
            logger.warning(f"Failed to load agent card from {entry.url}: {e}")
        finally:
            entry.last_attempt = datetime.now()

    async def _refresh_loop(self) -> None:
        while self._running:
            await self.refresh_all()
            await asyncio.sleep(self.refresh_interval)

    async def refresh_all(self) -> None:
        tasks = [self._fetch_agent_card(entry) for entry in self.entries.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def start(self) -> None:
        self._running = True
        await self.refresh_all()
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def stop(self) -> None:
        self._running = False
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        await self.httpx_client.aclose()

    def get_tools(self) -> list["RegistryAgentTool"]:
        return [
            RegistryAgentTool(entry.card, entry.client)
            for entry in self.entries.values()
            if entry.resolved
        ]

    def get_status(self) -> dict[str, dict]:
        return {
            url: {
                "available": entry.resolved,
                "name": entry.card.name,
                "last_attempt": entry.last_attempt.isoformat()
                if entry.last_attempt
                else None,
                "error": entry.error,
            }
            for url, entry in self.entries.items()
        }


class RegistryAgentTool(AgentTool):
    card: AgentCard
    client: Client
    tool_id: str

    def __init__(self, card: AgentCard, client: Client):
        super().__init__()
        self.card = card
        self.client = client
        self.tool_id = uuid4().hex

    @property
    def tool_name(self) -> str:
        return self.tool_id

    @property
    def tool_spec(self) -> ToolSpec:
        description = DESCRIPTION_TEMPLATE.render(
            name=self.card.name,
            description=self.card.description,
            skills=self.card.skills,
        )
        return {
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Message to send to the agent",
                        },
                        "contextId": {
                            "type": "string",
                            "description": "Context ID from previous response to continue conversation.",
                        },
                    },
                    "required": ["message"],
                }
            },
            "name": self.tool_id,
            "description": description,
        }

    @property
    def tool_type(self) -> str:
        return "python"

    @override
    async def stream(
        self, tool_use: ToolUse, invocation_state: dict[str, Any], **kwargs: Any
    ) -> ToolGenerator:
        msg = Message(
            kind="message",
            role=Role.user,
            parts=[Part(TextPart(kind="text", text=tool_use["input"]["message"]))],
            message_id=uuid4().hex,
            context_id=tool_use["input"].get("contextId"),
        )

        task_manager = ClientTaskManager()
        last_message: Message | None = None

        try:
            async for event in self.client.send_message(msg):
                if isinstance(event, tuple):
                    event = event[0]
                await task_manager.process(event)
                if isinstance(event, Message):
                    last_message = event

            task = task_manager.get_task()
            message = (
                self._extract_text(task)
                if task
                else (self._extract_text(last_message) if last_message else "")
            )
            context_id = (
                (task or last_message).context_id if (task or last_message) else ""  # type: ignore
            )

            if not message:
                raise RuntimeError("No response from agent")

            yield ToolResultEvent(
                {
                    "toolUseId": tool_use["toolUseId"],
                    "status": "success",
                    "content": [
                        {"json": {"contextId": context_id, "message": message}}
                    ],
                }
            )
        except Exception as e:
            logger.error(f"Error in tool {self.tool_id}: {e}")
            yield ToolResultEvent(
                {
                    "toolUseId": tool_use["toolUseId"],
                    "status": "error",
                    "content": [{"text": f"Error: {e}"}],
                }
            )

    def _extract_text(self, obj: Task | Message | None) -> str:
        if not obj:
            return ""
        if isinstance(obj, Message):
            return get_message_text(obj)
        if isinstance(obj, Task) and obj.artifacts:
            for artifact in reversed(obj.artifacts):
                if artifact.parts:
                    for part in reversed(artifact.parts):
                        if hasattr(part, "root") and hasattr(part.root, "text"):
                            return part.root.text  # type: ignore
        return ""
