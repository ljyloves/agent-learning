"""Strict request and result contracts for basic paper assembly."""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.modules.paper_agent.schemas.question import (
    QuestionDifficulty,
    QuestionType,
)


Code = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class PaperSectionConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_type: QuestionType
    difficulty: QuestionDifficulty
    count: int = Field(ge=1, le=1000)
    score_per_question: int = Field(ge=1, le=100)

    @property
    def total_score(self) -> int:
        return self.count * self.score_per_question


class PaperAssemblyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_code: Code = "BIO-M1"
    question_count: int = Field(ge=1, le=1000)
    total_score: int = Field(ge=1, le=10000)
    sections: list[PaperSectionConstraint] = Field(min_length=1, max_length=50)
    exclude_question_ids: list[Code] = Field(default_factory=list, max_length=1000)
    random_seed: int = Field(default=0, ge=0, le=2_147_483_647)

    @field_validator("exclude_question_ids")
    @classmethod
    def require_unique_exclusions(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("exclude_question_ids must be unique")
        return values

    @model_validator(mode="after")
    def validate_blueprint_totals(self) -> PaperAssemblyRequest:
        section_keys = [
            (section.question_type, section.difficulty)
            for section in self.sections
        ]
        if len(section_keys) != len(set(section_keys)):
            raise ValueError("question type and difficulty sections must be unique")

        expected_count = sum(section.count for section in self.sections)
        if expected_count != self.question_count:
            raise ValueError(
                "question_count must equal the sum of section counts"
            )
        expected_score = sum(section.total_score for section in self.sections)
        if expected_score != self.total_score:
            raise ValueError(
                "total_score must equal the sum of section scores"
            )
        return self


class AssembledQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: Code
    question_type: QuestionType
    difficulty: QuestionDifficulty
    score: int = Field(ge=1, le=100)


class AssembledSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_index: int = Field(ge=0)
    question_type: QuestionType
    difficulty: QuestionDifficulty
    count: int = Field(ge=1, le=1000)
    score_per_question: int = Field(ge=1, le=100)
    questions: list[AssembledQuestion] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_section(self) -> AssembledSection:
        if len(self.questions) != self.count:
            raise ValueError("assembled section count does not match questions")
        question_ids = [question.question_id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("assembled section question IDs must be unique")
        for question in self.questions:
            if question.question_type != self.question_type:
                raise ValueError("assembled question type does not match section")
            if question.difficulty != self.difficulty:
                raise ValueError("assembled question difficulty does not match section")
            if question.score != self.score_per_question:
                raise ValueError("assembled question score does not match section")
        return self


class PaperAssemblyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_code: Code
    question_count: int = Field(ge=1, le=1000)
    total_score: int = Field(ge=1, le=10000)
    sections: list[AssembledSection] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_paper_totals(self) -> PaperAssemblyResult:
        questions = [
            question
            for section in self.sections
            for question in section.questions
        ]
        if len(questions) != self.question_count:
            raise ValueError("assembled paper question count does not match")
        question_ids = [question.question_id for question in questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("assembled paper question IDs must be unique")
        if sum(question.score for question in questions) != self.total_score:
            raise ValueError("assembled paper total score does not match")
        return self
