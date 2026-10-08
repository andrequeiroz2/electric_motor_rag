from eletric_motor_mcp.formulas.constants import NBR_5410_DOCUMENT_ID
from eletric_motor_mcp.formulas.line_voltage_drop import (
    line_voltage_drop_percent,
    line_voltage_drop_v,
)
from eletric_motor_mcp.formulas.version import FORMULA_SET_VERSION
from eletric_motor_mcp.schemas.base import DocumentRef
from eletric_motor_mcp.schemas.line_voltage_drop import LineVoltageDropInput
from eletric_motor_mcp.schemas.results import NumericToolResult


def calcular_queda_linha(data: LineVoltageDropInput) -> NumericToolResult:
    trifasico = data.fase == "trifasico"
    delta_u_v = line_voltage_drop_v(
        corrente_a=data.corrente_a,
        resistencia_ohm=data.resistencia_ohm,
        reatancia_ohm=data.reatancia_ohm,
        cos_phi=data.cos_phi,
        trifasico=trifasico,
    )
    delta_u_pct = line_voltage_drop_percent(delta_u_v=delta_u_v, tensao_v=data.tensao_v)
    fase_note = "trifásico: ΔU = √3·I·(R cos φ + X sin φ), U_ref linha" if trifasico else (
        "monofásico: ΔU = I·(R cos φ + X sin φ), U_ref fase-neutro"
    )
    return NumericToolResult(
        value=round(delta_u_pct, 4),
        unit="%",
        reference=DocumentRef(
            source_document_id=NBR_5410_DOCUMENT_ID,
            source_section_path="§6.2.7 (verificação de queda)",
            formula_id="line_voltage_drop_pct",
            formula_set_version=FORMULA_SET_VERSION,
        ),
        source_excerpt=(
            f"{fase_note}; R/X totais do trecho; comprimento {data.comprimento_m:.2f} m informado. "
            "Método clássico documentado em docs/MCP.md — não substitui tabelas §6.2.5."
        ),
    )
