from typing import Literal

from pydantic import Field

from eletric_motor_mcp.schemas.base import BaseInput

QuedaContextoLiteral = Literal[
    "circuito_terminal",
    "motor_regime_permanente",
    "partida",
    "instalacao_alimentacao",
    "instalacao_distribuicao",
    "instalacao_utilizacao",
]


class VoltageDropValidationInput(BaseInput):
    delta_u_percent: float = Field(ge=0, description="Queda de tensão em percentual, já calculada")
    contexto: QuedaContextoLiteral
