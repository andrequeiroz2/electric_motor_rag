from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpSettings(BaseSettings, frozen=True):
    model_config = SettingsConfigDict(extra="ignore", env_file=".env")

    mcp_host: str = "127.0.0.1"
    mcp_port: int = Field(default=8000, ge=1, le=65535)
    mcp_path: str = "/mcp"
    mcp_log_level: str = "INFO"
    mcp_transport: str = Field(
        default="streamable-http",
        description="FastMCP transport: streamable-http or http",
    )
