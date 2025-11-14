import logging
from fastapi import FastAPI
from a2a.types import SecurityScheme, HTTPAuthSecurityScheme
from .auth.bearer_auth import BearerAuthMiddleware
from .auth.oauth_auth import OAuth2JWTAuthMiddleware
from .config import A2ASecurityConfig


PUBLIC_PATHS = [
    "/.well-known/agent.json",
    "/.well-known/agent-card.json",
    "/health",
    "/ping",
]


def configure_security(
    app: FastAPI, config: A2ASecurityConfig
) -> dict[str, SecurityScheme] | None:
    match config.mode:
        case "none":
            logging.info("Security mode: none")
            return None

        case "bearer":
            logging.info("Security mode: bearer")

            if config.bearer.token is None:
                logging.error("Bearer token not configured")
                exit(1)

            app.add_middleware(
                BearerAuthMiddleware,  # type: ignore
                token=config.bearer.token,
                public_paths=PUBLIC_PATHS,
            )

            return {
                "bearer": SecurityScheme(
                    root=HTTPAuthSecurityScheme(
                        scheme="Bearer",
                        description="Bearer token",
                    )
                )
            }

        case "oauth":
            logging.info("Security mode: oauth")

            app.add_middleware(
                OAuth2JWTAuthMiddleware,  # type: ignore
                jwks_url=config.oauth.jwks_url,
                audience=config.oauth.audience,
                issuer=config.oauth.issuer,
                public_paths=PUBLIC_PATHS,
            )

            return None

        case _:
            logging.error(f"Unknown security mode: {config.mode}")
            exit(1)
