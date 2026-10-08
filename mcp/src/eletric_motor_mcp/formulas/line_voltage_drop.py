import math

from eletric_motor_mcp.formulas.constants import SQRT3


def line_voltage_drop_v(
    *,
    corrente_a: float,
    resistencia_ohm: float,
    reatancia_ohm: float,
    cos_phi: float,
    trifasico: bool,
) -> float:
    """Queda de tensão absoluta (V) no trecho; R e X já totais do percurso."""
    sin_phi = math.sqrt(max(0.0, 1.0 - cos_phi * cos_phi))
    z_term = resistencia_ohm * cos_phi + reatancia_ohm * sin_phi
    if trifasico:
        return SQRT3 * corrente_a * z_term
    return corrente_a * z_term


def line_voltage_drop_percent(
    *,
    delta_u_v: float,
    tensao_v: float,
) -> float:
    return 100.0 * delta_u_v / tensao_v
