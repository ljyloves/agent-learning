"""Question schemas shared by ingestion, assembly, and export."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.modules.paper_agent.schemas.source import (
    QuestionResource,
    QuestionSource,
    ResourceType,
)


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
AnswerList = Annotated[list[NonEmptyText], Field(min_length=1)]


class QuestionType(str, Enum):
    """Question forms supported by the biology-paper MVP."""

    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    SHORT_ANSWER = "short_answer"
    COMPOSITE = "composite"


class QuestionImage(QuestionResource):
    """A traceable image referenced by a URL, object key, or local path."""

    resource_type: Literal[ResourceType.IMAGE] = ResourceType.IMAGE
    alt_text: NonEmptyText | None = None
    caption: NonEmptyText | None = None


class QuestionOption(BaseModel):
    """A selectable option that may contain text, images, or both."""

    model_config = ConfigDict(extra="forbid")

    label: NonEmptyText
    content: NonEmptyText | None = None
    images: list[QuestionImage] = Field(default_factory=list)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def require_content(self) -> QuestionOption:
        if self.content is None and not self.images:
            raise ValueError("an option must contain text or at least one image")
        return self


class Question(BaseModel):
    """Canonical question structure used throughout the paper pipeline."""

    model_config = ConfigDict(extra="forbid")

    id: NonEmptyText | None = None
    question_type: QuestionType
    stem: NonEmptyText
    source: QuestionSource
    options: list[QuestionOption] = Field(default_factory=list)
    subquestions: list[Question] = Field(default_factory=list)
    answer: NonEmptyText | AnswerList | None = None
    explanation: NonEmptyText | None = None
    images: list[QuestionImage] = Field(default_factory=list)

    @field_validator("options")
    @classmethod
    def require_unique_option_labels(
        cls, options: list[QuestionOption]
    ) -> list[QuestionOption]:
        labels = [option.label.casefold() for option in options]
        if len(labels) != len(set(labels)):
            raise ValueError("option labels must be unique within a question")
        return options


Question.model_rebuild()
