"""Authentication manager for Slack users."""

import asyncio
import logging

from slack_sdk import WebClient

from .oidc_device_flow import OIDCDeviceFlow
from .token_store import TokenStore

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages OIDC authentication for Slack users."""

    def __init__(self, oidc_flow: OIDCDeviceFlow, token_store: TokenStore):
        self.oidc_flow = oidc_flow
        self.token_store = token_store
        self._pending_auth: dict[str, asyncio.Task] = {}

    async def ensure_authenticated(
        self, slack_user_id: str, slack_client: WebClient
    ) -> str | None:
        """Ensure user is authenticated, initiate flow if not."""
        token = await self.token_store.get_token(slack_user_id)
        if token:
            return token

        if slack_user_id in self._pending_auth:
            task = self._pending_auth[slack_user_id]
            if not task.done():
                return None
            del self._pending_auth[slack_user_id]
            return await self.token_store.get_token(slack_user_id)

        task = asyncio.create_task(
            self._initiate_auth_flow(slack_user_id, slack_client)
        )
        self._pending_auth[slack_user_id] = task

        return None

    async def _initiate_auth_flow(self, slack_user_id: str, slack_client: WebClient):
        """Initiate device authorization flow and DM user."""
        try:
            device_auth = await self.oidc_flow.initiate_device_flow()

            if device_auth.verification_uri_complete:
                auth_text = (
                    f"Hey there! 👋\n\n"
                    f"Before I can help you out, I need to confirm your identity.\n\n"
                    f"Click here: {device_auth.verification_uri_complete}\n\n"
                    f"Or head over to {device_auth.verification_uri} and enter this code:\n\n"
                    f"`{device_auth.user_code}`\n\n"
                    f"_(This code expires in {device_auth.expires_in // 60} minutes)_"
                )
            else:
                auth_text = (
                    f"Hey there! 👋\n\n"
                    f"Before I can help you out, I need to confirm your identity.\n\n"
                    f"Just head over to {device_auth.verification_uri} and enter this code:\n\n"
                    f"`{device_auth.user_code}`\n\n"
                    f"_(This code expires in {device_auth.expires_in // 60} minutes)_"
                )

            await slack_client.chat_postMessage(
                channel=slack_user_id,
                text=auth_text,
            )

            token_response = await self.oidc_flow.poll_for_token(
                device_auth.device_code,
                device_auth.interval,
                device_auth.expires_in,
            )

            if token_response:
                await self.token_store.store_token(
                    slack_user_id,
                    token_response.id_token,
                    token_response.expires_in,
                    token_response.refresh_token,
                )

                await slack_client.chat_postMessage(
                    channel=slack_user_id,
                    text="✅ All set! You're good to go. How can I help?",
                )
            else:
                await slack_client.chat_postMessage(
                    channel=slack_user_id,
                    text="Hmm, something went wrong or the code expired. Mind giving it another shot?",
                )

        except Exception as e:
            logger.error("Error in auth flow for user %s: %s", slack_user_id, e)
            await slack_client.chat_postMessage(
                channel=slack_user_id,
                text="Oops, ran into an issue. You might want to reach out to your admin about this.",
            )
        finally:
            self._pending_auth.pop(slack_user_id, None)
