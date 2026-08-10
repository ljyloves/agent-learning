"""Paper-generation job and review state schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PaperJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReviewStatus(str, Enum):
    NOT_STARTED = "not_started"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUIRED = "revision_required"


FINAL_REVIEW_STATUSES = {
    ReviewStatus.APPROVED,
    ReviewStatus.REJECTED,
    ReviewStatus.REVISION_REQUIRED,
}


class ReviewResult(BaseModel):
    """A final human or automated review decision."""

    model_config = ConfigDict(extra="forbid")

    status: ReviewStatus
    reviewer: NonEmptyText
    comments: NonEmptyText | None = None
    issues: list[NonEmptyText] = Field(default_factory=list)
    reviewed_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def require_final_decision(self) -> ReviewResult:
        if self.status not in FINAL_REVIEW_STATUSES:
            raise ValueError("a review result must contain a final review status")
        if (
            self.status in {ReviewStatus.REJECTED, ReviewStatus.REVISION_REQUIRED}
            and self.comments is None
            and not self.issues
        ):
            raise ValueError("a rejected or revision-required review needs details")
        return self


class PaperJob(BaseModel):
    """Current execution and review snapshot for one paper-generation job."""

    model_config = ConfigDict(extra="forbid")

    job_id: NonEmptyText
    status: PaperJobStatus = PaperJobStatus.QUEUED
    failure_reason: NonEmptyText | None = None
    review_status: ReviewStatus = ReviewStatus.NOT_STARTED
    review_result: ReviewResult | None = None
    created_at: AwareDatetime = Field(default_factory=utc_now)
    updated_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_state(self) -> PaperJob:
        if self.status == PaperJobStatus.FAILED and self.failure_reason is None:
            raise ValueError("a failed job must record failure_reason")
        if self.status != PaperJobStatus.FAILED and self.failure_reason is not None:
            raise ValueError("failure_reason is only valid for a failed job")

        is_final_review = self.review_status in FINAL_REVIEW_STATUSES
        if is_final_review and self.review_result is None:
            raise ValueError("a final review status requires review_result")
        if not is_final_review and self.review_result is not None:
            raise ValueError("review_result is only valid for a final review status")
        if (
            self.review_result is not None
            and self.review_result.status != self.review_status
        ):
            raise ValueError("review_result status must match review_status")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self
