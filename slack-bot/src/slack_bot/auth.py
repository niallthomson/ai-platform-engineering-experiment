"""OIDC authentication for Slack bot."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class OIDCTokenProvider:
    """Provides OIDC access tokens using client credentials flow."""

    def __init__(
        self,
        issuer: str,
        client_id: str,
        client_secret: str,
        scope: str = "openid",
        well_known_path: str = "/.well-known/openid-configuration",
    ):
        self.issuer = issuer.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.well_known_url = f"{self.issuer}{well_known_path}"
        self.token_endpoint: Optional[str] = None
        self._access_token: Optional[str] = None

    def _discover_endpoints(self) -> None:
        """Discover OIDC endpoints from well-known configuration."""
        try:
            response = httpx.get(self.well_known_url, timeout=10)
            response.raise_for_status()
            config = response.json()
            self.token_endpoint = config.get("token_endpoint")
            if not self.token_endpoint:
                raise ValueError("token_endpoint not found in well-known configuration")
            logger.info("Discovered token endpoint: %s", self.token_endpoint)
        except Exception as e:
            logger.error(
                "Failed to discover OIDC endpoints from %s: %s", self.well_known_url, e
            )
            raise

    def get_token(self) -> str:
        """Get access token using client credentials flow."""
        if not self.token_endpoint:
            self._discover_endpoints()

        try:
            response = httpx.post(
                self.token_endpoint,  # type: ignore
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": self.scope,
                },
                timeout=10,
            )
            response.raise_for_status()
            token_data = response.json()
            self._access_token = token_data.get("access_token")
            if not self._access_token:
                raise ValueError("access_token not found in token response")
            logger.debug("Successfully obtained OIDC access token")
            return self._access_token
        except Exception as e:
            logger.error("Failed to obtain OIDC access token: %s", e)
            raise
