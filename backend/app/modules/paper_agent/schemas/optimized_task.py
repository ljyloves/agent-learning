"""Contracts for persisted optimized papers and teacher-controlled revisions."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.modules.paper_agent.schemas.optimization import (
    Identifier,
    OptimizedPaperRequest,
    OptimizedPaperResult,
)
from app.modules.paper_agent.schemas.paper_job import (
    PaperJobStatus,
    ReviewResult,
    ReviewStatus,
)


ReviewComment = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class OptimizedPaperInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_name: str | None = Field(default=None, min_length=1, max_length=200)
    grade: str | None = Field(default=None, min_length=1, max_length=50)
    exam_type: str | None = Field(default=None, min_length=1, max_length=50)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)


class OptimizedPaperTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    optimization: OptimizedPaperRequest
    paper_info: OptimizedPaperInfo | None = None


class OptimizedPaperTaskListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: Identifier
    paper_name: str
    grade: str
    exam_type: str
    duration_minutes: int = Field(ge=1, le=600)
    question_count: int = Field(ge=0)
    total_score: int = Field(ge=0)
    status: PaperJobStatus
    review_status: ReviewStatus
    awaiting_teacher: bool
    created_at: AwareDatetime
    updated_at: AwareDatetime


class OptimizedPaperTaskListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OptimizedPaperTaskListItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)


class OptimizedPaperLockUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_ids: list[Identifier] = Field(min_length=1, max_length=1000)
    locked: bool

    @field_validator("question_ids")
    @classmethod
    def require_unique_question_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("question_ids must be unique")
        return values


class OptimizedPaperReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: Identifier
    replacement_question_id: Identifier | None = None
    reviewer: Identifier
    comment: ReviewComment | None = None

    @model_validator(mode="after")
    def require_distinct_replacement(self) -> "OptimizedPaperReplace":
        if self.replacement_question_id == self.question_id:
            raise ValueError("replacement question must differ from old question")
        return self


class OptimizedPaperReassemble(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer: Identifier
    comment: ReviewComment | None = None
    random_seed: int | None = Field(default=None, ge=0, le=2_147_483_647)


class OptimizedPaperTaskReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "reject"]
    reviewer: Identifier
    comment: ReviewComment | None = None

    @model_validator(mode="after")
    def require_rejection_comment(self) -> "OptimizedPaperTaskReview":
        if self.action == "reject" and self.comment is None:
            raise ValueError("reject action requires a comment")
        return self


class OptimizedPaperTaskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: Identifier
    generation_mode: Literal["optimized"]
    status: PaperJobStatus
    review_status: ReviewStatus
    review_result: ReviewResult | None = None
    failure_reason: str | None = None
    awaiting_teacher: bool
    paper: OptimizedPaperResult
    locked_question_ids: list[Identifier]
    created_at: AwareDatetime
    updated_at: AwareDatetime
