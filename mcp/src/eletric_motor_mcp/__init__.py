"""MCP server package for deterministic motor calculations."""


def main() -> None:
    """Start the MCP server (HTTP by default)."""
    from eletric_motor_mcp.server import run_server

    run_server()
