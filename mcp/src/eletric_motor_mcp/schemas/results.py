from pydantic import BaseModel, ConfigDict, Field

from eletric_motor_mcp.schemas.base import DocumentRef


class NumericToolResult(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    value: float
    unit: str
    reference: DocumentRef
    source_excerpt: str | None = None


class ValidationToolResult(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    delta_u_percent: float
    limit_percent: float
    contexto: str
    reference: DocumentRef
    message: str = Field(description="Human-readable pass/fail summary in Portuguese")
