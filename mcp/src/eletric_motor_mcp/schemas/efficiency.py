from pydantic import Field

from eletric_motor_mcp.schemas.base import BaseInput


class EfficiencyInput(BaseInput):
    potencia_util_kw: float = Field(gt=0)
    potencia_absorvida_kw: float = Field(gt=0)
