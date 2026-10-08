from fastmcp import FastMCP

from eletric_motor_mcp.logging_config import get_logger
from eletric_motor_mcp.schemas.ip_in import IpInInput
from eletric_motor_mcp.schemas.results import NumericToolResult
from eletric_motor_mcp.services import ip_in as ip_in_service

logger = get_logger("tools")


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def calcular_relacao_ip_in(
        potencia_kw: float,
        rendimento: float | None = None,
        cos_phi: float | None = None,
    ) -> NumericToolResult:
        """Estima a relação I_p/I_n pela faixa de potência (guia WEG §4.5.1).

        Use valores de placa ou catálogo quando disponíveis; esta tool aplica a tabela versionada.
        """
        logger.info(
            "event=mcp.tool_call tool=calcular_relacao_ip_in potencia_kw=%s",
            potencia_kw,
            extra={"event": "mcp.tool_call", "tool": "calcular_relacao_ip_in"},
        )
        data = IpInInput.model_validate(
            {
                "potencia_kw": potencia_kw,
                "rendimento": rendimento,
                "cos_phi": cos_phi,
            }
        )
        return ip_in_service.calcular_relacao_ip_in(data)
