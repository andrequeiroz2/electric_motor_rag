import math

import pytest

from eletric_motor_mcp.formulas.ip_in_table import lookup_ip_in_base
from eletric_motor_mcp.formulas.line_voltage_drop import line_voltage_drop_percent, line_voltage_drop_v
from eletric_motor_mcp.formulas.nominal_current import nominal_current_a
from eletric_motor_mcp.schemas.nominal_current import NominalCurrentInput
from eletric_motor_mcp.schemas.line_voltage_drop import LineVoltageDropInput
from eletric_motor_mcp.services.line_voltage_drop import calcular_queda_linha
from eletric_motor_mcp.services.nominal_current import calcular_corrente_nominal
from eletric_motor_mcp.services.voltage_drop import validar_queda_nbr5410
from eletric_motor_mcp.schemas.voltage_drop import VoltageDropValidationInput


def test_nominal_current_trifasico_10kw() -> None:
    # 10 kW, 380 V, η=0.9, cos φ=0.85 → I_n ≈ 19.97 A
    pu = 10_000.0
    in_a = nominal_current_a(
        potencia_util_w=pu,
        tensao_v=380.0,
        trifasico=True,
        rendimento=0.9,
        cos_phi=0.85,
    )
    expected = 10_000 / (math.sqrt(3) * 380 * 0.9 * 0.85)
    assert in_a == pytest.approx(expected, rel=1e-4)


def test_service_corrente_com_fs() -> None:
    result = calcular_corrente_nominal(
        NominalCurrentInput.model_validate(
            {
                "potencia_kw": 10.0,
                "tensao_v": 380.0,
                "fase": "trifasico",
                "rendimento": 0.9,
                "cos_phi": 0.85,
                "fator_servico": 1.15,
            }
        )
    )
    assert result.unit == "A"
    assert result.value > 19.97


def test_validar_queda_partida() -> None:
    ok = validar_queda_nbr5410(
        VoltageDropValidationInput.model_validate(
            {"delta_u_percent": 9.0, "contexto": "partida"}
        )
    )
    assert ok.ok is True
    fail = validar_queda_nbr5410(
        VoltageDropValidationInput.model_validate(
            {"delta_u_percent": 11.0, "contexto": "partida"}
        )
    )
    assert fail.ok is False


def test_ip_in_bands() -> None:
    assert lookup_ip_in_base(3.0) == 6.5
    assert lookup_ip_in_base(10.0) == 7.5


def test_line_voltage_drop_trifasico() -> None:
    cos_phi = 0.85
    sin_phi = math.sqrt(1.0 - cos_phi * cos_phi)
    r_ohm = 0.1
    x_ohm = 0.05
    i_a = 20.0
    u_linha = 380.0
    delta_v = math.sqrt(3) * i_a * (r_ohm * cos_phi + x_ohm * sin_phi)
    expected_pct = 100.0 * delta_v / u_linha
    got_v = line_voltage_drop_v(
        corrente_a=i_a,
        resistencia_ohm=r_ohm,
        reatancia_ohm=x_ohm,
        cos_phi=cos_phi,
        trifasico=True,
    )
    assert got_v == pytest.approx(delta_v, rel=1e-6)
    assert line_voltage_drop_percent(delta_u_v=got_v, tensao_v=u_linha) == pytest.approx(
        expected_pct, rel=1e-6
    )


def test_line_voltage_drop_monofasico() -> None:
    cos_phi = 0.85
    sin_phi = math.sqrt(1.0 - cos_phi * cos_phi)
    delta_v = 20.0 * (0.1 * cos_phi + 0.05 * sin_phi)
    got = line_voltage_drop_v(
        corrente_a=20.0,
        resistencia_ohm=0.1,
        reatancia_ohm=0.05,
        cos_phi=cos_phi,
        trifasico=False,
    )
    assert got == pytest.approx(delta_v, rel=1e-6)
    assert line_voltage_drop_percent(delta_u_v=got, tensao_v=220.0) == pytest.approx(
        100.0 * delta_v / 220.0, rel=1e-6
    )


def test_queda_linha_encadeamento_10kw() -> None:
    in_result = calcular_corrente_nominal(
        NominalCurrentInput.model_validate(
            {
                "potencia_kw": 10.0,
                "tensao_v": 380.0,
                "fase": "trifasico",
                "rendimento": 0.9,
                "cos_phi": 0.85,
            }
        )
    )
    queda = calcular_queda_linha(
        LineVoltageDropInput.model_validate(
            {
                "corrente_a": in_result.value,
                "comprimento_m": 50.0,
                "tensao_v": 380.0,
                "fase": "trifasico",
                "cos_phi": 0.85,
                "resistencia_ohm": 0.15,
                "reatancia_ohm": 0.02,
            }
        )
    )
    validacao = validar_queda_nbr5410(
        VoltageDropValidationInput.model_validate(
            {"delta_u_percent": queda.value, "contexto": "motor_regime_permanente"}
        )
    )
    assert queda.unit == "%"
    assert validacao.ok is True
    assert validacao.delta_u_percent == queda.value
