import logging
from fnmatch import fnmatch
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.authentication import SimpleUser

logger = logging.getLogger(__name__)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that authenticates A2A access using a bearer key."""

    def __init__(
        self,
        app: Starlette,
        token: str,
        public_paths: list[str] = None,  # type: ignore
    ):
        super().__init__(app)
        self.public_paths = public_paths or []
        self.token = token

    def _is_public_path(self, path: str) -> bool:
        """Check if path matches any public path pattern."""
        return any(fnmatch(path, pattern) for pattern in self.public_paths)

    async def dispatch(self, request: Request, call_next):
        """
        Middleware to authenticate requests using a shared key.
        :param request:
        :param call_next:
        :return:
        """
        path = request.url.path

        # Allow public paths and anonymous access
        if self._is_public_path(path):
            return await call_next(request)

        # Authenticate the request
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return self._unauthorized(
                "Missing or malformed Authorization header.", request
            )

        access_token = auth_header.split("Bearer ")[1]

        try:
            if access_token != self.token:
                return self._unauthorized("Invalid shared key.", request)
        except Exception as e:
            logging.error("Dispatch error: %s", e, exc_info=True)
            return self._forbidden(f"Authentication failed: {e}", request)

        request.scope["user"] = SimpleUser("authenticated")

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
