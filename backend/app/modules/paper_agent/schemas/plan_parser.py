"""Contracts for two-stage natural-language paper plan parsing."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.modules.paper_agent.schemas.conversation import PaperPlan


class PaperPlanDraftQuota(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_type: str = Field(min_length=1, max_length=50)
    difficulty_level: int | None = Field(default=None, ge=1, le=5)
    count: int | None = Field(default=None, ge=1, le=1000)
    score_per_question: int | None = Field(default=None, ge=1, le=100)


class PaperPlanDraft(BaseModel):
    """Untrusted LLM draft; every value is normalized before use."""

    model_config = ConfigDict(extra="forbid")

    paper_name: str | None = Field(default=None, min_length=1, max_length=200)
    grade: str | None = Field(default=None, min_length=1, max_length=50)
    exam_type: str | None = Field(default=None, min_length=1, max_length=50)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    module: str | None = Field(default=None, min_length=1, max_length=128)
    knowledge_points: list[str] | None = Field(default=None, max_length=32)
    quotas: list[PaperPlanDraftQuota] | None = Field(default=None, max_length=50)
    stated_question_count: int | None = Field(default=None, ge=1, le=1000)
    stated_total_score: int | None = Field(default=None, ge=1, le=10_000)


class PaperPlanParseStatus(StrEnum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    FORM_FALLBACK = "form_fallback"


class PaperPlanParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PaperPlanParseStatus
    draft: PaperPlanDraft | None = None
    plan: PaperPlan | None = None
    previous_plan: PaperPlan | None = None
    clarification_questions: list[str] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
    form_fallback: bool = False
