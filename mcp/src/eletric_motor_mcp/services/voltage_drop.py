from eletric_motor_mcp.formulas.constants import NBR_5410_DOCUMENT_ID
from eletric_motor_mcp.formulas.nbr5410_voltage_drop import QuedaContexto, voltage_drop_limit
from eletric_motor_mcp.formulas.version import FORMULA_SET_VERSION
from eletric_motor_mcp.schemas.base import DocumentRef
from eletric_motor_mcp.schemas.results import ValidationToolResult
from eletric_motor_mcp.schemas.voltage_drop import VoltageDropValidationInput


def validar_queda_nbr5410(data: VoltageDropValidationInput) -> ValidationToolResult:
    contexto = QuedaContexto(data.contexto)
    limit, section = voltage_drop_limit(contexto)
    ok = data.delta_u_percent <= limit
    if ok:
        message = (
            f"Queda {data.delta_u_percent:.2f} % atende ao limite de {limit:.0f} % "
            f"({contexto.value})."
        )
    else:
        message = (
            f"Queda {data.delta_u_percent:.2f} % excede o limite de {limit:.0f} % "
            f"({contexto.value})."
        )
    return ValidationToolResult(
        ok=ok,
        delta_u_percent=data.delta_u_percent,
        limit_percent=limit,
        contexto=data.contexto,
        reference=DocumentRef(
            source_document_id=NBR_5410_DOCUMENT_ID,
            source_section_path=section,
            formula_id="nbr5410_voltage_drop_limit",
            formula_set_version=FORMULA_SET_VERSION,
        ),
        message=message,
    )
