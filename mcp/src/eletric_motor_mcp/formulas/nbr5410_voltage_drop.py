from enum import StrEnum


class QuedaContexto(StrEnum):
    CIRCUITO_TERMINAL = "circuito_terminal"
    MOTOR_REGIME_PERMANENTE = "motor_regime_permanente"
    PARTIDA = "partida"
    INSTALACAO_ALIMENTACAO = "instalacao_alimentacao"
    INSTALACAO_DISTRIBUICAO = "instalacao_distribuicao"
    INSTALACAO_UTILIZACAO = "instalacao_utilizacao"


_LIMITS: dict[QuedaContexto, tuple[float, str]] = {
    QuedaContexto.CIRCUITO_TERMINAL: (4.0, "NBR-5410 §6.2.7.2"),
    QuedaContexto.MOTOR_REGIME_PERMANENTE: (4.0, "NBR-5410 §6.5.1.3.2"),
    QuedaContexto.PARTIDA: (10.0, "NBR-5410 §6.5.1.3.3"),
    QuedaContexto.INSTALACAO_ALIMENTACAO: (7.0, "NBR-5410 §6.2.7.1"),
    QuedaContexto.INSTALACAO_DISTRIBUICAO: (5.0, "NBR-5410 §6.2.7.1"),
    QuedaContexto.INSTALACAO_UTILIZACAO: (7.0, "NBR-5410 §6.2.7.1"),
}


def voltage_drop_limit(contexto: QuedaContexto) -> tuple[float, str]:
    return _LIMITS[contexto]
