"""Slack event handlers."""

import logging
from uuid import uuid4

import httpx
from slack_bolt.async_app import AsyncApp
from slack_sdk import WebClient
from slack_sdk.web.chat_stream import ChatStream

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.client.client_task_manager import ClientTaskManager
from a2a.types import Message, Part, Role, Task, TextPart
from a2a.utils.message import get_message_text

logger = logging.getLogger(__name__)

# Store context_id per DM channel
context_store: dict[str, str] = {}


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


async def call_agent(
    streamer: ChatStream, endpoint: str, user_input: str, api_key: str = "", context_id: str | None = None
) -> str | None:
    """Execute A2A agent call and return response text and context_id."""
    http_client = httpx.AsyncClient(
        timeout=600,
        headers={"Authorization": f"Bearer {api_key}"},
    )

    card_resolver = A2ACardResolver(httpx_client=http_client, base_url=endpoint)
    agent_card = await card_resolver.get_agent_card()

    client_config = ClientConfig(httpx_client=http_client, streaming=True)
    client = ClientFactory(client_config).create(agent_card)

    #formatted_input = f"{user_input}\n\nNote: Format your response using Slack mrkdwn syntax, not standard Markdown. Use *bold* for bold text, _italic_ for italic text, and `code` for inline code. If a downstream agent responds with Markdown then reformat it. Alter Markdown links to use the format: <http://www.example.com|This message *is* a link>"

    user_message = Message(
        kind="message",
        role=Role.user,
        parts=[Part(TextPart(kind="text", text=user_input))],
        message_id=uuid4().hex,
        context_id=context_id,
    )

    logger.debug("Calling A2A agent at: %s with context_id: %s", endpoint, context_id)

    final_message: Message | None = None
    last_message_id = ""
    last_artifact_id = ""

    async for evt in client.send_message(user_message):
        if isinstance(evt, tuple):
            evt = evt[0]

        if isinstance(evt, Task):
            if evt.history is not None and len(evt.history) > 1:
                final_message = evt.history[-1]
                
                if final_message.message_id != last_message_id:
                    last_message_id = final_message.message_id
                    message_text = get_message_text(final_message)
                    
                    await streamer.append(markdown_text=f"{message_text}") # type: ignore
                    
            if evt.artifacts is not None and len(evt.artifacts) > 0:
                last_artifact = evt.artifacts[-1]

                if last_artifact.artifact_id != last_artifact_id:
                    last_artifact_id = last_artifact.artifact_id

                    if last_artifact.name == "tool_invocation_update":
                        await streamer.append(markdown_text="\n\n") # type: ignore
                        await streamer._flush_buffer() # type: ignore

    response_context_id = ""
    
    if final_message is not None:
        response_context_id = final_message.context_id
    else:
        raise RuntimeError("No response from agent")

    await http_client.aclose()
    return response_context_id if context_id is None else None


async def send_agent_response(
    client: WebClient,
    cid: str,
    query: str,
    user: str,
    agent_url: str,
    thread_ts: str,
    api_key: str = "",
    auth_manager=None,
):
    """Send query to agent and post response to channel."""
    if not agent_url:
        await client.chat_postMessage(
            channel=cid,
            text="A2A agent URL must be configured to use this command.",
            thread_ts=thread_ts,
        )  # pyright: ignore[reportGeneralTypeIssues]
        return

    # Check authentication if auth_manager is provided
    if auth_manager:
        token = await auth_manager.ensure_authenticated(user, client)
        if not token:
            return
        api_key = token

    # Retrieve existing context_id for this channel/thread
    context_key = f"{cid}:{thread_ts}" if thread_ts else cid
    context_id = context_store.get(context_key)
    
    streamer = await client.chat_stream(
        channel=cid,
        thread_ts=thread_ts,
    ) # type: ignore

    try:
        new_context_id = await call_agent(
            streamer, agent_url, query, api_key, context_id
        )

        # Store the new context_id for this channel/thread
        if new_context_id:
            context_store[context_key] = new_context_id
            logger.debug("Stored context_id %s for key %s", new_context_id, context_key)
        else:
            logger.debug("Re-used context_id %s for key %s", context_id, context_key)
    except Exception as err:
        logger.error("Agent invocation failed: %s", err)
        await client.chat_postMessage(
            channel=cid,
            text="❌ Error: There was an issue processing your request, please contact your administrator",
            thread_ts=thread_ts,
        )  # pyright: ignore[reportGeneralTypeIssues]
    finally:
        await streamer.stop()


def setup_handlers(
    slack_app: AsyncApp, agent_url: str, api_key: str = "", auth_manager=None
):
    """Configure Slack event handlers."""

    async def handle_direct_message(event, client: WebClient):
        """Process direct messages sent to the bot."""
        if event.get("channel_type") == "im" and not event.get("bot_id"):
            # Check for reset command
            if event["text"].strip().lower() in ["reset", "/reset"]:
                cid = event["channel"]
                if cid in context_store:
                    del context_store[cid]
                    await client.chat_postMessage(
                        channel=cid, text="Conversation context has been reset."
                    )  # pyright: ignore[reportGeneralTypeIssues]
                else:
                    await client.chat_postMessage(
                        channel=cid, text="No active conversation context to reset."
                    )  # pyright: ignore[reportGeneralTypeIssues]
                return
            
            thread_ts = event.get("thread_ts") or event.get("ts")

            await send_agent_response(
                client,
                event["channel"],
                event["text"],
                event["user"],
                agent_url,
                thread_ts,
                api_key,
                auth_manager=auth_manager,
            )

    async def handle_app_mention(event, client: WebClient):
        """Process mentions of the bot in channels."""
        # Extract the message text and remove the bot mention
        text = event.get("text", "")
        # Remove the bot mention from the text
        query = text.split(">", 1)[1].strip() if ">" in text else text.strip()

        if not query:
            return

        # Get thread_ts - if already in a thread, use it; otherwise use the message ts to create a thread
        thread_ts = event.get("thread_ts") or event.get("ts")

        await send_agent_response(
            client,
            event["channel"],
            query,
            event["user"],
            agent_url,
            thread_ts,
            api_key,
            auth_manager=auth_manager,
        )

    slack_app.event("message")(handle_direct_message)
    slack_app.event("app_mention")(handle_app_mention)
