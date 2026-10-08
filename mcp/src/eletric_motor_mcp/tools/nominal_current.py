from fastmcp import FastMCP

from eletric_motor_mcp.logging_config import get_logger
from eletric_motor_mcp.schemas.nominal_current import NominalCurrentInput
from eletric_motor_mcp.schemas.results import NumericToolResult
from eletric_motor_mcp.services import nominal_current as nominal_current_service

logger = get_logger("tools")


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def calcular_corrente_nominal(
        potencia_kw: float,
        tensao_v: float,
        fase: str,
        rendimento: float,
        cos_phi: float,
        fator_servico: float = 1.0,
    ) -> NumericToolResult:
        """Calcula a corrente nominal I_n (A) a partir de potência, tensão, η e cos φ.

        Fonte: guia WEG §1.2.3–1.2.4 (FS opcional §7.4). Trifásico usa √3·U·η·cos φ no denominador.
        """
        logger.info(
            "event=mcp.tool_call tool=calcular_corrente_nominal potencia_kw=%s fase=%s",
            potencia_kw,
            fase,
            extra={"event": "mcp.tool_call", "tool": "calcular_corrente_nominal"},
        )
        data = NominalCurrentInput.model_validate(
            {
                "potencia_kw": potencia_kw,
                "tensao_v": tensao_v,
                "fase": fase,
                "rendimento": rendimento,
                "cos_phi": cos_phi,
                "fator_servico": fator_servico,
            }
        )
        return nominal_current_service.calcular_corrente_nominal(data)
