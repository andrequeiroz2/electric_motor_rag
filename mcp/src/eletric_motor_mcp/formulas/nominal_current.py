from eletric_motor_mcp.formulas.constants import SQRT3


def nominal_current_a(
    *,
    potencia_util_w: float,
    tensao_v: float,
    trifasico: bool,
    rendimento: float,
    cos_phi: float,
) -> float:
    """I_n from useful mechanical/electrical power at the shaft (WEG guia §1.2.3–1.2.4)."""
    denominator = tensao_v * rendimento * cos_phi
    if trifasico:
        return potencia_util_w / (SQRT3 * denominator)
    return potencia_util_w / denominator
