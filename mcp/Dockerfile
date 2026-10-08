FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY mcp ./mcp
COPY src ./src

RUN uv sync --all-packages --no-dev

ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000

CMD ["uv", "run", "--directory", "mcp", "eletric-motor-mcp"]
