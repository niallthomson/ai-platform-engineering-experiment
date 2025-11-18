"""OIDC device authorization flow implementation."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)


@dataclass
class DeviceAuthResponse:
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int
    verification_uri_complete: str | None = None


@dataclass
class TokenResponse:
    access_token: str
    id_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None = None


class OIDCDeviceFlow:
    """Handles OIDC device authorization flow with auto-discovery."""

    def __init__(
        self,
        configuration_url: str,
        client_id: str,
        client_secret: str = "",
        scope: str = "openid profile",
    ):
        self.configuration_url = configuration_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self._config: dict | None = None

    async def _get_config(self) -> dict:
        """Fetch OIDC configuration from discovery endpoint."""
        if self._config:
            return self._config

        discovery_url = self.configuration_url
        async with httpx.AsyncClient() as client:
            response = await client.get(discovery_url)
            response.raise_for_status()
            self._config = response.json()
            logger.info("Loaded OIDC config from %s", discovery_url)
            return self._config

    async def initiate_device_flow(self) -> DeviceAuthResponse:
        """Initiate device authorization flow."""
        config = await self._get_config()
        device_auth_url = config["device_authorization_endpoint"]

        data = {"client_id": self.client_id, "scope": self.scope}
        if self.client_secret:
            data["client_secret"] = self.client_secret

        async with httpx.AsyncClient() as client:
            response = await client.post(device_auth_url, data=data)
            response.raise_for_status()
            data = response.json()

            return DeviceAuthResponse(
                device_code=data["device_code"],
                user_code=data["user_code"],
                verification_uri=data["verification_uri"],
                expires_in=data["expires_in"],
                interval=data.get("interval", 5),
                verification_uri_complete=data.get("verification_uri_complete"),
            )

    async def poll_for_token(
        self, device_code: str, interval: int, expires_in: int
    ) -> TokenResponse | None:
        """Poll for tokens after user authorization."""
        config = await self._get_config()
        token_url = config["token_endpoint"]
        expiry = datetime.now() + timedelta(seconds=expires_in)

        async with httpx.AsyncClient() as client:
            while datetime.now() < expiry:
                await asyncio.sleep(interval)

                try:
                    data = {
                        "client_id": self.client_id,
                        "device_code": device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    }
                    if self.client_secret:
                        data["client_secret"] = self.client_secret
                    
                    response = await client.post(token_url, data=data)

                    if response.status_code == 200:
                        data = response.json()
                        return TokenResponse(
                            access_token=data["access_token"],
                            id_token=data["id_token"],
                            token_type=data.get("token_type", "Bearer"),
                            expires_in=data.get("expires_in", 3600),
                            refresh_token=data.get("refresh_token"),
                        )

                    error = response.json().get("error")
                    if error == "authorization_pending":
                        continue
                    elif error == "slow_down":
                        interval += 5
                        continue
                    else:
                        logger.error("Token polling error: %s", error)
                        return None

                except Exception as e:
                    logger.error("Error polling for token: %s", e)
                    return None

        logger.warning("Device flow expired before user authorized")
        return None
