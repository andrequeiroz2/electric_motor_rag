"""Domain exceptions for MCP tools."""


class MotorMcpError(Exception):
    """Base exception."""


class ToolValidationError(MotorMcpError):
    """Input failed business validation."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
