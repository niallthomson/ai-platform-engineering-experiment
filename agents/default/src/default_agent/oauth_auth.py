import logging
from typing import Optional
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
import jwt
from jwt import PyJWKClient

class OAuth2JWTAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that authenticates A2A access using OAuth2 JWT tokens."""

    def __init__(
        self,
        app: Starlette,
        jwks_url: str,
        audience: Optional[str] = None,
        issuer: Optional[str] = None,
        public_paths: list[str] = None,  # type: ignore
    ):
        super().__init__(app)
        self.public_paths = set(public_paths or [])
        self.jwks_client = PyJWKClient(jwks_url)
        self.audience = audience
        self.issuer = issuer

    async def dispatch(self, request: Request, call_next):
        """
        Middleware to authenticate requests using OAuth2 JWT.
        :param request:
        :param call_next:
        :return:
        """
        path = request.url.path

        # Allow public paths
        if path in self.public_paths:
            return await call_next(request)

        # Authenticate the request
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            logging.warning('Missing or malformed Authorization header')
            return self._unauthorized(
                'Missing or malformed Authorization header.', request
            )

        token = auth_header.split('Bearer ')[1]

        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=['RS256'],
                issuer=self.issuer,
                audience=self.audience,
                options={
                    "require": ["exp", "iss", "aud"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
            
            request.state.jwt_payload = payload
            
        except jwt.ExpiredSignatureError:
            logging.warning('JWT token has expired')
            return self._unauthorized('Token has expired.', request)
        except jwt.InvalidAudienceError:
            logging.warning('Invalid JWT audience')
            return self._unauthorized('Invalid token audience.', request)
        except jwt.InvalidIssuerError:
            logging.warning('Invalid JWT issuer')
            return self._unauthorized('Invalid token issuer.', request)
        except jwt.InvalidTokenError as e:
            logging.warning('Invalid JWT token: %s', e)
            return self._unauthorized('Invalid token.', request)
        except Exception as e:
            logging.error('JWT validation error: %s', e, exc_info=True)
            return self._forbidden(f'Authentication failed: {e}', request)

        return await call_next(request)

    def _forbidden(self, reason: str, request: Request):
        """
        Returns a 403 Forbidden response with a reason.
        :param reason:
        :param request:
        :return:
        """
        accept_header = request.headers.get('accept', '')
        if 'text/event-stream' in accept_header:
            return PlainTextResponse(
                f'error forbidden: {reason}',
                status_code=403,
                media_type='text/event-stream',
            )
        return JSONResponse(
            {'error': 'forbidden', 'reason': reason}, status_code=403
        )

    def _unauthorized(self, reason: str, request: Request):
        """
        Returns a 401 Unauthorized response with a reason.
        :param reason:
        :param request:
        :return:
        """
        accept_header = request.headers.get('accept', '')
        if 'text/event-stream' in accept_header:
            return PlainTextResponse(
                f'error unauthorized: {reason}',
                status_code=401,
                media_type='text/event-stream',
            )
        return JSONResponse(
            {'error': 'unauthorized', 'reason': reason}, status_code=401
        )
