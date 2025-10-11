import asyncio
import logging
from typing import Any
from typing_extensions import override
from uuid import uuid4
import httpx
from strands.types.tools import AgentTool, ToolGenerator, ToolSpec, ToolUse
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory, Client
from a2a.client.client_task_manager import ClientTaskManager
from strands.types._events import ToolResultEvent
from a2a.types import Message, Part, Role, TextPart, AgentCard, Task
from a2a.utils.message import get_message_text
import json

class A2AAgentTool(AgentTool):
    
    agent_url: str
    agent_card: AgentCard
    client : Client
    tool_id: str

    def __init__(self, agent_url: str, agent_card: AgentCard, client: Client) -> None:
        super().__init__()
        self.agent_url = agent_url
        self.agent_card = agent_card
        self.client = client
        self.tool_id = uuid4().hex

    @property
    def tool_name(self) -> str:
        """Get the name of the tool.

        Returns:
            str: The name of the MCP tool
        """
        return self.tool_id

    @property
    def tool_spec(self) -> ToolSpec:
        description: str = self.agent_card.description

        spec: ToolSpec = {
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Message to send to the agent"
                        },
                        "contextId": {
                            "type": "string",
                            "description": "Context ID from a previous response from this agent. Provide this to continue the same thread of conversation."
                        }
                    },
                    "required": ["message"]
                }
            },
            "name": self.tool_id,
            "description": description,
        }

        return spec

    @property
    def tool_type(self) -> str:
        return "python"

    @override
    async def stream(self, tool_use: ToolUse, invocation_state: dict[str, Any], **kwargs: Any) -> ToolGenerator:
        previous_context_id = None
        
        if "contextId" in tool_use["input"]:
            previous_context_id = tool_use["input"]["contextId"]
            
        msg = Message(
            kind="message",
            role=Role.user,
            parts=[Part(TextPart(kind="text", text=tool_use["input"]["message"]))],
            message_id=uuid4().hex,
            context_id=previous_context_id
        )
        
        task_manager = ClientTaskManager()
        last_message: Message | None = None

        try:
            async for event in self.client.send_message(msg):
                # Unwrap tuple from transport implementations
                if isinstance(event, tuple):
                    event = event[0]
                # Let the SDK task manager handle state aggregation
                await task_manager.process(event)
                if isinstance(event, Message):
                    last_message = event
                    
            task = task_manager.get_task()
            
            message = ""
            context_id = ""
            
            if task:
                message = extract_text(task)
                context_id = task.context_id
            elif last_message is not None:
                message = extract_text(last_message)
                context_id = last_message.context_id
            else:
                raise RuntimeError('No response from agent')
            
            yield ToolResultEvent({"toolUseId": tool_use["toolUseId"], "status": "success", "content": [{"json": {"contextId": context_id, "message": message}}]})
        except Exception as e:
            logging.error(f"Error in tool {self.tool_id}: {e}")
            yield ToolResultEvent({"toolUseId": tool_use["toolUseId"], "status": "error", "content": [{"text": f"Error in tool {self.tool_id}: {e}"}]})
            
def extract_text(obj: Task | Message):
    """Return plain text from a Task or Message, using SDK helpers when possible."""
    if isinstance(obj, Message):
        return get_message_text(obj)

    if isinstance(obj, Task) and obj.artifacts:
        # Prefer the newest artifact/part (at the end) but fall back gracefully.
        for artifact in reversed(obj.artifacts):
            if artifact.parts:
                for part in reversed(artifact.parts):
                    if hasattr(part, 'root') and hasattr(part.root, 'text'):
                        return part.root.text  # type: ignore[attr-defined]
    return ''
        
async def createAgentTool(agent_url: str):
    httpx_client = httpx.AsyncClient(timeout=300)
    resolver = A2ACardResolver(httpx_client=httpx_client, base_url=agent_url)
    agent_card = await resolver.get_agent_card()

    config = ClientConfig(httpx_client=httpx_client, streaming=False)
    factory = ClientFactory(config)
    client = factory.create(agent_card)
    
    logging.info(f"Creating agent tool for {agent_card.name}")
    
    return A2AAgentTool(agent_url, agent_card, client)

def createAgentToolSync(agent_url: str) -> A2AAgentTool:
    """Synchronous wrapper for createAgentTool."""
    return asyncio.run(createAgentTool(agent_url))