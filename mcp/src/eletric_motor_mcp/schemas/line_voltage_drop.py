from typing import Literal

from pydantic import Field

from eletric_motor_mcp.schemas.base import BaseInput


class LineVoltageDropInput(BaseInput):
    corrente_a: float = Field(gt=0, description="Corrente de projeto no trecho (A)")
    comprimento_m: float = Field(gt=0, description="Comprimento do trecho (m); metadado de projeto")
    tensao_v: float = Field(
        gt=0,
        description="Tensão nominal de referência: linha (trifásico) ou fase-neutro (monofásico), em V",
    )
    fase: Literal["monofasico", "trifasico"]
    cos_phi: float = Field(gt=0, le=1, description="Fator de potência (ex.: 0,3 na partida §6.5.1.3.3)")
    resistencia_ohm: float = Field(gt=0, description="Resistência total do trecho (Ω)")
    reatancia_ohm: float = Field(default=0.0, ge=0, description="Reatância total do trecho (Ω)")
