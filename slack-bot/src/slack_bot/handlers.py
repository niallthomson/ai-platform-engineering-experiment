"""Slack event handlers."""

import logging
from uuid import uuid4

import httpx
from slack_bolt.async_app import AsyncApp
from slack_sdk import WebClient

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.client.client_task_manager import ClientTaskManager
from a2a.types import Message, Part, Role, Task, TextPart
from a2a.utils.message import get_message_text

logger = logging.getLogger(__name__)


def _parse_response_text(response_obj: Task | Message | None) -> str:
    """Extract text content from A2A response object."""
    if not response_obj:
        return ""
    if isinstance(response_obj, Message):
        return get_message_text(response_obj)
    if isinstance(response_obj, Task) and response_obj.artifacts:
        for artifact in reversed(response_obj.artifacts):
            if artifact.parts:
                for part in reversed(artifact.parts):
                    if hasattr(part, "root") and hasattr(part.root, "text"):
                        return part.root.text  # type: ignore
    return ""


async def call_agent(endpoint: str, user_input: str, api_key: str = ""):
    """Execute A2A agent call and return response text."""
    http_client = httpx.AsyncClient(
        timeout=600,
        headers={"Authorization": f"Bearer {api_key}"},
    )

    card_resolver = A2ACardResolver(httpx_client=http_client, base_url=endpoint)
    agent_card = await card_resolver.get_agent_card()

    client_config = ClientConfig(httpx_client=http_client, streaming=False)
    client = ClientFactory(client_config).create(agent_card)

    formatted_input = f"{user_input}\n\nNote: Format your response using Slack mrkdwn syntax, not standard Markdown. Use *bold* for bold text, _italic_ for italic text, and `code` for inline code. If a downstream agent responds with Markdown then reformat it."

    user_message = Message(
        kind="message",
        role=Role.user,
        parts=[Part(TextPart(kind="text", text=formatted_input))],
        message_id=uuid4().hex,
    )

    logger.debug("Calling A2A agent at: %s", endpoint)

    task_mgr = ClientTaskManager()
    final_message: Message | None = None

    async for evt in client.send_message(user_message):
        if isinstance(evt, tuple):
            evt = evt[0]
        await task_mgr.process(evt)
        if isinstance(evt, Message):
            final_message = evt

    result_task = task_mgr.get_task()
    response_text = (
        _parse_response_text(result_task)
        if result_task
        else (
            _parse_response_text(final_message)
            if final_message
            else "No response from the agent"
        )
    )

    await http_client.aclose()
    return response_text


async def send_agent_response(
    client: WebClient, cid: str, query: str, agent_url: str, api_key: str = ""
):
    """Send query to agent and post response to channel."""
    if not agent_url:
        await client.chat_postMessage(
            channel=cid,
            text="A2A agent URL must be configured to use this command.",
        )  # pyright: ignore[reportGeneralTypeIssues]
        return

    await client.chat_postMessage(
        channel=cid,
        text="Thinking...",
    )  # pyright: ignore[reportGeneralTypeIssues]

    try:
        agent_response = await call_agent(agent_url, query, api_key)
        if agent_response and agent_response.strip():
            blocks = [
                {"type": "mrkdwn", "text": f"*Query:* {query}"},
                {"type": "divider"},
                {"type": "section", "text": {"type": "mrkdwn", "text": agent_response}},
            ]

            await client.chat_postMessage(
                channel=cid,
                blocks=blocks,
                text=f"AI Agent Response: {agent_response[:100]}..."
                if len(agent_response) > 100
                else f"AI Agent Response: {agent_response}",
            )  # pyright: ignore[reportGeneralTypeIssues]
        else:
            await client.chat_postMessage(
                channel=cid, text="Agent returned no response."
            )  # pyright: ignore[reportGeneralTypeIssues]
    except Exception as err:
        logger.error("Agent invocation failed: %s", err)
        err_blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "❌ Error", "emoji": True},
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"*Query:* {query}"}],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "An error occurred, please report this to your administrator```",
                },
            },
        ]
        await client.chat_postMessage(
            channel=cid, blocks=err_blocks, text=f"AI Agent Error: {str(err)}"
        )  # pyright: ignore[reportGeneralTypeIssues]


def setup_handlers(slack_app: AsyncApp, agent_url: str, api_key: str = ""):
    """Configure Slack event handlers."""

    async def handle_direct_message(event, client: WebClient):
        """Process direct messages sent to the bot."""
        if event.get("channel_type") == "im" and not event.get("bot_id"):
            await send_agent_response(
                client, event["channel"], event["text"], agent_url, api_key
            )

    slack_app.event("message")(handle_direct_message)
