"""Contracts for deterministic question parsing and resource recovery."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.modules.paper_agent.schemas.question import Question, QuestionDifficulty


Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]


class QuestionParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM
    knowledge_point_codes: list[Identifier] = Field(default_factory=list, max_length=32)

    @field_validator("knowledge_point_codes")
    @classmethod
    def unique_knowledge_points(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("knowledge_point_codes must be unique")
        return values


class ParsedQuestionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_resource_id: Identifier
    question_ids: list[Identifier] = Field(min_length=1)
    questions: list[Question] = Field(min_length=1)
    asset_resource_ids: list[Identifier] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
