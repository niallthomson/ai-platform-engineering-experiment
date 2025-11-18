import logging
from fnmatch import fnmatch
from typing import Optional
from starlette.applications import Starlette
from starlette.authentication import SimpleUser
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
import jwt
from jwt import PyJWKClient
import httpx

logger = logging.getLogger(__name__)


class OIDCJWTAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that authenticates A2A access using OIDC JWT tokens."""

    def __init__(
        self,
        app: Starlette,
        configuration_url: str,
        audiences: Optional[list[str]] = None,
        public_paths: list[str] = None,  # type: ignore
    ):
        super().__init__(app)
        self.public_paths = public_paths or []
        self.configuration_url = configuration_url
        oidc_config = self._discover_oidc_config()
        self.jwks_client = PyJWKClient(oidc_config["jwks_uri"])
        self.audiences = audiences
        self.issuer = oidc_config.get("issuer")

    def _is_public_path(self, path: str) -> bool:
        """Check if path matches any public path pattern."""
        return any(fnmatch(path, pattern) for pattern in self.public_paths)

    def _discover_oidc_config(self) -> dict:
        """Discover OIDC configuration from well-known endpoint."""
        try:
            response = httpx.get(self.configuration_url, timeout=10)
            response.raise_for_status()
            config = response.json()
            if not config.get("jwks_uri"):
                raise ValueError("jwks_uri not found in OIDC configuration")
            logger.info("Discovered JWKS URL: %s", config["jwks_uri"])
            if config.get("issuer"):
                logger.info("Discovered issuer: %s", config["issuer"])
            return config
        except Exception as e:
            logger.error(
                "Failed to discover OIDC configuration from %s: %s",
                self.configuration_url,
                e,
            )
            raise

    async def dispatch(self, request: Request, call_next):
        """Middleware to authenticate requests using OIDC JWT."""
        path = request.url.path

        # Allow public paths
        if self._is_public_path(path):
            return await call_next(request)

        # Authenticate the request
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("Missing or malformed Authorization header")
            return self._unauthorized(
                "Missing or malformed Authorization header.", request
            )

        token = auth_header.split("Bearer ")[1]

        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                options={
                    "require": ["exp", "iss", "aud"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "verify_aud": False,
                },
            )

            # Verify at least one audience matches
            if self.audiences:
                token_audiences = payload.get("aud", [])
                if isinstance(token_audiences, str):
                    token_audiences = [token_audiences]
                if not any(aud in self.audiences for aud in token_audiences):
                    raise jwt.InvalidAudienceError("Token audience not allowed")

            user_id = (
                payload.get("preferred_username")
                or payload.get("sub")
                or payload.get("email")
                or payload.get("client_id")
            )

            request.state.token = token

            request.scope["user"] = SimpleUser(user_id)
            request.scope["token"] = token

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return self._unauthorized("Token has expired.", request)
        except jwt.InvalidAudienceError:
            logger.warning("Invalid JWT audience")
            return self._unauthorized("Invalid token audience.", request)
        except jwt.InvalidIssuerError:
            logger.warning("Invalid JWT issuer")
            return self._unauthorized("Invalid token issuer.", request)
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid JWT token: %s", e)
            return self._unauthorized("Invalid token.", request)
        except Exception as e:
            logger.error("JWT validation error: %s", e, exc_info=True)
            return self._forbidden(f"Authentication failed: {e}", request)

        return await call_next(request)

    def _forbidden(self, reason: str, request: Request):
        """
        Returns a 403 Forbidden response with a reason.
        :param reason:
        :param request:
        :return:
        """
        accept_header = request.headers.get("accept", "")
        if "text/event-stream" in accept_header:
            return PlainTextResponse(
                f"error forbidden: {reason}",
                status_code=403,
                media_type="text/event-stream",
            )
        return JSONResponse({"error": "forbidden", "reason": reason}, status_code=403)

    def _unauthorized(self, reason: str, request: Request):
        """
        Returns a 401 Unauthorized response with a reason.
        :param reason:
        :param request:
        :return:
        """
        accept_header = request.headers.get("accept", "")
        if "text/event-stream" in accept_header:
            return PlainTextResponse(
                f"error unauthorized: {reason}",
                status_code=401,
                media_type="text/event-stream",
            )
        return JSONResponse(
            {"error": "unauthorized", "reason": reason}, status_code=401
        )
