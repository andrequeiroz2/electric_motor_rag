from typing import Literal

from pydantic import Field

from eletric_motor_mcp.schemas.base import BaseInput


class NominalCurrentInput(BaseInput):
    potencia_kw: float = Field(gt=0, description="Potência útil nominal em kW")
    tensao_v: float = Field(gt=0, description="Tensão de linha (trifásico) ou fase (monofásico), em V")
    fase: Literal["monofasico", "trifasico"]
    rendimento: float = Field(gt=0, le=1, description="Rendimento η (0–1)")
    cos_phi: float = Field(gt=0, le=1, description="Fator de potência")
    fator_servico: float = Field(default=1.0, gt=0, description="Fator de serviço (FS), padrão 1.0")
