from fastmcp import FastMCP

from eletric_motor_mcp.logging_config import get_logger
from eletric_motor_mcp.schemas.line_voltage_drop import LineVoltageDropInput
from eletric_motor_mcp.schemas.results import NumericToolResult
from eletric_motor_mcp.services import line_voltage_drop as line_voltage_drop_service

logger = get_logger("tools")


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def calcular_queda_linha(
        corrente_a: float,
        comprimento_m: float,
        tensao_v: float,
        fase: str,
        cos_phi: float,
        resistencia_ohm: float,
        reatancia_ohm: float = 0.0,
    ) -> NumericToolResult:
        """Calcula queda de tensão percentual (ΔU%) em trecho BT a partir de I, R/X totais e cos φ.

        Trifásico: √3·I·(R cos φ + X sin φ) sobre tensão de linha. Monofásico: I·(R cos φ + X sin φ)
        sobre tensão fase-neutro. Encadear com validar_queda_nbr5410. NBR 5410 exige verificação (§6.2.7).
        """
        logger.info(
            "event=mcp.tool_call tool=calcular_queda_linha fase=%s",
            fase,
            extra={"event": "mcp.tool_call", "tool": "calcular_queda_linha"},
        )
        data = LineVoltageDropInput.model_validate(
            {
                "corrente_a": corrente_a,
                "comprimento_m": comprimento_m,
                "tensao_v": tensao_v,
                "fase": fase,
                "cos_phi": cos_phi,
                "resistencia_ohm": resistencia_ohm,
                "reatancia_ohm": reatancia_ohm,
            }
        )
        return line_voltage_drop_service.calcular_queda_linha(data)
