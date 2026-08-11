"""Contracts for question indexing and hybrid retrieval."""

from typing import Annotated, Literal

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


Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
QueryText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class QuestionIndexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_ids: list[Identifier] = Field(default_factory=list, max_length=5000)

    @field_validator("question_ids")
    @classmethod
    def unique_question_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("question_ids must be unique")
        return values


class QuestionIndexResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection: Identifier
    indexed_count: int = Field(ge=0)
    requested_count: int | None = Field(default=None, ge=0)


class HybridQuestionSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: QueryText
    knowledge_point_codes: list[Identifier] = Field(min_length=1, max_length=32)
    question_types: list[QuestionType] = Field(min_length=1, max_length=6)
    top_k: int = Field(default=10, ge=1, le=50)
    keyword_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    vector_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    deduplicate: bool = True
    semantic_similarity_threshold: float = Field(
        default=0.94,
        ge=0.80,
        le=1.0,
    )

    @field_validator("knowledge_point_codes", "question_types")
    @classmethod
    def unique_filters(cls, values: list) -> list:
        if len(values) != len(set(values)):
            raise ValueError("retrieval filters must be unique")
        return values

    @model_validator(mode="after")
    def require_a_retrieval_branch(self) -> "HybridQuestionSearchRequest":
        if self.keyword_weight + self.vector_weight <= 0:
            raise ValueError("at least one retrieval weight must be positive")
        return self


class HybridQuestionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    question_id: Identifier
    source_id: Identifier
    question_type: QuestionType
    difficulty: QuestionDifficulty
    stem: str = Field(min_length=1)
    knowledge_point_codes: list[Identifier] = Field(min_length=1)
    keyword_score: float = Field(ge=0.0, le=1.0)
    vector_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    hybrid_score: float = Field(ge=0.0)


class DuplicateQuestionMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: Identifier
    retained_question_id: Identifier
    kind: Literal["exact", "semantic"]
    similarity: float = Field(ge=-1.0, le=1.0)


class DeduplicationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_count: int = Field(ge=0)
    exact_duplicate_count: int = Field(ge=0)
    semantic_duplicate_count: int = Field(ge=0)
    retained_count: int = Field(ge=0)
    output_count: int = Field(ge=0)
    remaining_duplicate_ratio: float = Field(ge=0.0, le=1.0)
    matches: list[DuplicateQuestionMatch] = Field(default_factory=list)


class HybridQuestionSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: QueryText
    candidates: list[HybridQuestionCandidate]
    keyword_candidate_count: int = Field(ge=0)
    vector_candidate_count: int = Field(ge=0)
    deduplication: DeduplicationReport
