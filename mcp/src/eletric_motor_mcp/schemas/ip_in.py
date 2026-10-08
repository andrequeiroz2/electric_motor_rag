from pydantic import Field

from eletric_motor_mcp.schemas.base import BaseInput


class IpInInput(BaseInput):
    potencia_kw: float = Field(gt=0, description="Potência nominal em kW para faixa da tabela §4.5.1")
    rendimento: float | None = Field(default=None, gt=0, le=1, description="Opcional, para cálculo de In associado")
    cos_phi: float | None = Field(default=None, gt=0, le=1, description="Opcional, para cálculo de In associado")
