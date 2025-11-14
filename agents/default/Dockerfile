FROM python:3.13-slim  AS uv

COPY --from=ghcr.io/astral-sh/uv:0.8.21 /uv /uvx /bin/

# Install the project into `/app`
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Prefer the system python
ENV UV_PYTHON_PREFERENCE=only-system

# Run without updating the uv.lock file like running with `--frozen`
ENV UV_FROZEN=true

# Copy the required files first
COPY pyproject.toml uv.lock ./

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev --no-editable

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-editable

FROM python:3.13-slim as app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Project got copied to here
WORKDIR /app

# Place executables in the environment at the front of the path and include other binaries
ENV PATH="/app/.venv/bin:$PATH"

# Get the project from the uv layer
COPY --from=uv --chown=appuser:appuser /app/.venv .venv

# Switch to non-root user
USER appuser

# Expose ports for MCP (8080), A2A (9000), and FastAPI (3000)
EXPOSE 8080 9000 3000

ENTRYPOINT [ "default-agent" ]