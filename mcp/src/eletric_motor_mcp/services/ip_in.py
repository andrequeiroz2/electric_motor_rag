from eletric_motor_mcp.formulas.constants import WEG_GUIA_DOCUMENT_ID
from eletric_motor_mcp.formulas.ip_in_table import ip_in_ratio
from eletric_motor_mcp.formulas.version import FORMULA_SET_VERSION
from eletric_motor_mcp.schemas.base import DocumentRef
from eletric_motor_mcp.schemas.ip_in import IpInInput
from eletric_motor_mcp.schemas.results import NumericToolResult


def calcular_relacao_ip_in(data: IpInInput) -> NumericToolResult:
    ratio = ip_in_ratio(potencia_kw=data.potencia_kw)
    return NumericToolResult(
        value=round(ratio, 4),
        unit="1",
        reference=DocumentRef(
            source_document_id=WEG_GUIA_DOCUMENT_ID,
            source_section_path="§4.5.1",
            formula_id="ip_in_table_kw",
            formula_set_version=FORMULA_SET_VERSION,
        ),
        source_excerpt="Relação I_p/I_n estimada pela faixa de potência (tabela §4.5.1).",
    )
