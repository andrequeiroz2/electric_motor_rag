"""FastMCP entrypoint — HTTP transport by default."""

from fastmcp import FastMCP

from eletric_motor_mcp.logging_config import get_logger, setup_logging
from eletric_motor_mcp.settings import McpSettings
from eletric_motor_mcp.tools import efficiency, ip_in, line_voltage_drop, nominal_current, voltage_drop

logger = get_logger("server")

mcp = FastMCP("Motores elétricos — cálculos MCP")


def _register_tools() -> None:
    nominal_current.register(mcp)
    line_voltage_drop.register(mcp)
    voltage_drop.register(mcp)
    efficiency.register(mcp)
    ip_in.register(mcp)


_register_tools()


def run_server() -> None:
    settings = McpSettings()
    setup_logging(settings.mcp_log_level)
    logger.info(
        "event=mcp.server.start host=%s port=%s path=%s transport=%s",
        settings.mcp_host,
        settings.mcp_port,
        settings.mcp_path,
        settings.mcp_transport,
        extra={"event": "mcp.server.start"},
    )
    transport = settings.mcp_transport
    if transport == "streamable-http":
        transport = "streamable-http"
    mcp.run(
        transport=transport,
        host=settings.mcp_host,
        port=settings.mcp_port,
        path=settings.mcp_path,
        show_banner=True,
    )


if __name__ == "__main__":
    run_server()
