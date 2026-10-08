from fastmcp import FastMCP

from eletric_motor_mcp.logging_config import get_logger
from eletric_motor_mcp.schemas.efficiency import EfficiencyInput
from eletric_motor_mcp.schemas.results import NumericToolResult
from eletric_motor_mcp.services import efficiency as efficiency_service

logger = get_logger("tools")


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def calcular_rendimento(
        potencia_util_kw: float,
        potencia_absorvida_kw: float,
    ) -> NumericToolResult:
        """Calcula o rendimento η = P_u / P_a (adimensional, valor entre 0 e 1).

        Fonte: guia WEG §1.2.6.
        """
        logger.info(
            "event=mcp.tool_call tool=calcular_rendimento",
            extra={"event": "mcp.tool_call", "tool": "calcular_rendimento"},
        )
        data = EfficiencyInput.model_validate(
            {
                "potencia_util_kw": potencia_util_kw,
                "potencia_absorvida_kw": potencia_absorvida_kw,
            }
        )
        return efficiency_service.calcular_rendimento(data)
