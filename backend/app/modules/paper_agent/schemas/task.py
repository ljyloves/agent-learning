"""Unified API contracts for persisted paper-generation tasks."""

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.modules.paper_agent.graph.state import Identifier
from app.modules.paper_agent.schemas.assembly import (
    PaperAssemblyRequest,
    PaperAssemblyResult,
)
from app.modules.paper_agent.schemas.checkpoint import TeacherReviewCommand
from app.modules.paper_agent.schemas.paper_job import (
    PaperJobStatus,
    ReviewResult,
    ReviewStatus,
)


class PaperTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assembly: PaperAssemblyRequest


class PaperTaskReview(TeacherReviewCommand):
    pass


class PaperTaskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: Identifier
    status: PaperJobStatus
    review_status: ReviewStatus
    review_result: ReviewResult | None = None
    failure_reason: str | None = None
    awaiting_teacher: bool
    assembly: PaperAssemblyResult
    created_at: AwareDatetime
    updated_at: AwareDatetime
