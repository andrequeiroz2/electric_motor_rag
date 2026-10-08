from fastmcp import FastMCP

from eletric_motor_mcp.logging_config import get_logger
from eletric_motor_mcp.schemas.results import ValidationToolResult
from eletric_motor_mcp.schemas.voltage_drop import VoltageDropValidationInput
from eletric_motor_mcp.services import voltage_drop as voltage_drop_service

logger = get_logger("tools")


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def validar_queda_nbr5410(
        delta_u_percent: float,
        contexto: str,
    ) -> ValidationToolResult:
        """Valida se a queda de tensão informada (%) atende aos limites da NBR 5410.

        contexto: circuito_terminal | motor_regime_permanente | partida |
        instalacao_alimentacao | instalacao_distribuicao | instalacao_utilizacao.
        """
        logger.info(
            "event=mcp.tool_call tool=validar_queda_nbr5410 contexto=%s",
            contexto,
            extra={"event": "mcp.tool_call", "tool": "validar_queda_nbr5410"},
        )
        data = VoltageDropValidationInput.model_validate(
            {"delta_u_percent": delta_u_percent, "contexto": contexto}
        )
        return voltage_drop_service.validar_queda_nbr5410(data)
