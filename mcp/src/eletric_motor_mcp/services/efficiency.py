from eletric_motor_mcp.formulas.constants import WEG_GUIA_DOCUMENT_ID
from eletric_motor_mcp.formulas.efficiency import efficiency_ratio
from eletric_motor_mcp.formulas.version import FORMULA_SET_VERSION
from eletric_motor_mcp.schemas.base import DocumentRef
from eletric_motor_mcp.schemas.efficiency import EfficiencyInput
from eletric_motor_mcp.schemas.results import NumericToolResult


def calcular_rendimento(data: EfficiencyInput) -> NumericToolResult:
    pu = data.potencia_util_kw * 1000.0
    pa = data.potencia_absorvida_kw * 1000.0
    eta = efficiency_ratio(potencia_util_w=pu, potencia_absorvida_w=pa)
    return NumericToolResult(
        value=round(eta, 6),
        unit="1",
        reference=DocumentRef(
            source_document_id=WEG_GUIA_DOCUMENT_ID,
            source_section_path="§1.2.6",
            formula_id="efficiency_eta",
            formula_set_version=FORMULA_SET_VERSION,
        ),
        source_excerpt="η = P_u / P_a",
    )
