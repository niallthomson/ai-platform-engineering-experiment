import logging
from fastapi import FastAPI
from a2a.types import SecurityScheme, HTTPAuthSecurityScheme
from .auth.bearer_auth import BearerAuthMiddleware
from .auth.oidc_auth import OIDCJWTAuthMiddleware
from .config import AuthConfig

logger = logging.getLogger(__name__)

BASE_PUBLIC_PATHS = [
    "/.well-known/*",
    "/health",
    "/ping",
]

OIDC_PUBLIC_PATHS = BASE_PUBLIC_PATHS + [
    "/mcp",
    "/mcp/*",
    "/register",
    "/authorize",
    "/consent",
    "/consent/submit",
    "/auth/callback",
    "/token",
]


def configure_security(
    app: FastAPI, config: AuthConfig
) -> dict[str, SecurityScheme] | None:
    match config.mode:
        case "none":
            logger.info("Auth mode: none")
            return None

        case "bearer":
            logger.info("Auth mode: bearer")

            if config.bearer.token is None:
                logger.error("Bearer token not configured")
                exit(1)

            app.add_middleware(
                BearerAuthMiddleware,  # type: ignore
                token=config.bearer.token,
                public_paths=BASE_PUBLIC_PATHS,
            )

            return {
                "bearer": SecurityScheme(
                    root=HTTPAuthSecurityScheme(
                        scheme="Bearer",
                        description="Bearer token",
                    )
                )
            }

        case "oidc":
            logger.info("Auth mode: oidc")

            if not config.oidc.configuration_url:
                logger.error("OIDC configuration_url not configured")
                exit(1)

            app.add_middleware(
                OIDCJWTAuthMiddleware,  # type: ignore
                configuration_url=config.oidc.configuration_url,
                audiences=config.oidc.audiences,
                public_paths=OIDC_PUBLIC_PATHS,
            )

            return None

        case _:
            logger.error(f"Unknown auth mode: {config.mode}")
            exit(1)
