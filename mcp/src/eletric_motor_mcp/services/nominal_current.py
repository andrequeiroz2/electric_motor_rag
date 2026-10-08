from eletric_motor_mcp.formulas.constants import WEG_GUIA_DOCUMENT_ID
from eletric_motor_mcp.formulas.nominal_current import nominal_current_a
from eletric_motor_mcp.formulas.version import FORMULA_SET_VERSION
from eletric_motor_mcp.schemas.base import DocumentRef
from eletric_motor_mcp.schemas.nominal_current import NominalCurrentInput
from eletric_motor_mcp.schemas.results import NumericToolResult


def calcular_corrente_nominal(data: NominalCurrentInput) -> NumericToolResult:
    potencia_w = data.potencia_kw * 1000.0 * data.fator_servico
    trifasico = data.fase == "trifasico"
    in_a = nominal_current_a(
        potencia_util_w=potencia_w,
        tensao_v=data.tensao_v,
        trifasico=trifasico,
        rendimento=data.rendimento,
        cos_phi=data.cos_phi,
    )
    section = "§1.2.3–1.2.4" if data.fator_servico == 1.0 else "§1.2.3–1.2.4; §7.4"
    return NumericToolResult(
        value=round(in_a, 4),
        unit="A",
        reference=DocumentRef(
            source_document_id=WEG_GUIA_DOCUMENT_ID,
            source_section_path=section,
            formula_id="nominal_current_ln",
            formula_set_version=FORMULA_SET_VERSION,
        ),
        source_excerpt="I_n a partir de P_u, U, η e cos φ (trifásico: divisor √3·U·η·cos φ).",
    )
