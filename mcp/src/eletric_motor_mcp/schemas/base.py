from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class BaseInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class DocumentRef(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    source_section_path: str
    formula_id: str
    formula_set_version: str
