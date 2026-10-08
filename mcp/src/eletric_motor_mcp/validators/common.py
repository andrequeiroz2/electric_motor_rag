from eletric_motor_mcp.exceptions import ToolValidationError


def ensure_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ToolValidationError(f"{name} deve ser maior que zero.")
