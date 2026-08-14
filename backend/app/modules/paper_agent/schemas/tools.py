"""Pydantic input and output contracts for the Agent tool allowlist."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.paper_agent.schemas.conversation import PaperPlan
from app.modules.paper_agent.schemas.optimization import Identifier
from app.modules.paper_agent.schemas.optimized_task import (
    OptimizedPaperLockUpdate,
    OptimizedPaperReassemble,
    OptimizedPaperReplace,
    OptimizedPaperTaskReview,
)
from app.modules.paper_agent.schemas.paper_job import PaperJobStatus, ReviewStatus
from app.modules.paper_agent.schemas.question import QuestionType
from app.modules.paper_agent.schemas.source import SourceType
from app.modules.paper_agent.schemas.taxonomy_change import (
    ApplyTaxonomyChangeToolInput,
    DeactivateTaxonomyItemToolInput,
    PreviewTaxonomyChangeToolInput,
    TaxonomyChangePreview,
    TaxonomyChangeResult,
)


class EmptyToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchQuestionsToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    keyword: str | None = Field(default=None, min_length=1, max_length=200)
    question_type: QuestionType | None = None
    source_id: Identifier | None = None


class SearchSourcesToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    keyword: str | None = Field(default=None, min_length=1, max_length=200)
    source_type: SourceType | None = None


class GetPaperStatusToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: Identifier


class CreatePaperToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: PaperPlan


class LockQuestionsToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: Identifier
    update: OptimizedPaperLockUpdate


class ReplaceQuestionToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: Identifier
    replacement: OptimizedPaperReplace


class ReassemblePaperToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: Identifier
    request: OptimizedPaperReassemble


class SubmitReviewToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: Identifier
    review: OptimizedPaperTaskReview


class PrepareExportsToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: Identifier


class ExportLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    url: str
    file_format: Literal["docx", "pdf", "zip"]


class PrepareExportsToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: Identifier
    status: PaperJobStatus
    review_status: ReviewStatus
    links: list[ExportLink] = Field(min_length=1)
