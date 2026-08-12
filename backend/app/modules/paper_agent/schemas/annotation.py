"""Contracts for LLM-assisted biology taxonomy annotation."""

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)


Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
Rationale = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]


class TaxonomyAnnotationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replace_existing: bool = True


class TaxonomyAnnotationLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_point_codes: list[Identifier] = Field(min_length=1, max_length=5)
    core_competency_codes: list[Identifier] = Field(min_length=1, max_length=4)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: Rationale

    @field_validator("knowledge_point_codes", "core_competency_codes")
    @classmethod
    def require_unique_codes(cls, codes: list[str]) -> list[str]:
        if len(codes) != len(set(codes)):
            raise ValueError("taxonomy annotation codes must be unique")
        return codes


class TaxonomyAnnotationResponse(TaxonomyAnnotationLLMOutput):
    question_id: Identifier
    model: str = Field(min_length=1, max_length=255)
    replaced_existing: bool
