def efficiency_ratio(*, potencia_util_w: float, potencia_absorvida_w: float) -> float:
    """η = P_u / P_a (guia §1.2.6)."""
    return potencia_util_w / potencia_absorvida_w
