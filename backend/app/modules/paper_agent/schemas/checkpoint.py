"""API contracts for durable Paper Agent graph tasks."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.modules.paper_agent.graph.state import (
    Identifier,
    PaperGraphDecision,
    PaperGraphState,
)


class PaperGraphDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: PaperGraphDecision
    error_code: Identifier | None = None
    replace_question_id: Identifier | None = None
    replacement_question_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_decision_fields(self) -> PaperGraphDecisionRequest:
        replacement_ids = (
            self.replace_question_id,
            self.replacement_question_id,
        )
        if self.decision == PaperGraphDecision.REPLACE:
            if any(value is None for value in replacement_ids):
                raise ValueError("replace decision requires old and new question IDs")
        elif any(value is not None for value in replacement_ids):
            raise ValueError("replacement IDs are only valid for replace decision")

        if self.error_code is not None and self.decision != PaperGraphDecision.FAIL:
            raise ValueError("error_code is only valid for fail decision")
        return self


class PaperGraphTaskStart(PaperGraphDecisionRequest):
    job_id: Identifier
    paper_id: Identifier | None = None
    candidate_question_ids: list[Identifier] = Field(
        default_factory=list,
        max_length=1000,
    )
    selected_question_ids: list[Identifier] = Field(
        default_factory=list,
        max_length=1000,
    )

    @model_validator(mode="after")
    def validate_initial_state(self) -> PaperGraphTaskStart:
        PaperGraphState(
            job_id=self.job_id,
            paper_id=self.paper_id,
            candidate_question_ids=self.candidate_question_ids,
            selected_question_ids=self.selected_question_ids,
        )
        return self


class PaperGraphTaskResume(PaperGraphDecisionRequest):
    pass


class PaperGraphTaskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: Identifier
    state: PaperGraphState


ReviewComment = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class TeacherReviewAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REPLACE = "replace"


class TeacherReviewTaskStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: Identifier
    paper_id: Identifier
    candidate_question_ids: list[Identifier] = Field(
        min_length=1,
        max_length=1000,
    )
    selected_question_ids: list[Identifier] = Field(
        min_length=1,
        max_length=1000,
    )

    @model_validator(mode="after")
    def validate_initial_state(self) -> TeacherReviewTaskStart:
        PaperGraphState(
            job_id=self.job_id,
            paper_id=self.paper_id,
            candidate_question_ids=self.candidate_question_ids,
            selected_question_ids=self.selected_question_ids,
        )
        return self


class TeacherReviewCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: TeacherReviewAction
    reviewer: Identifier
    comment: ReviewComment | None = None
    replace_question_id: Identifier | None = None
    replacement_question_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> TeacherReviewCommand:
        replacement_ids = (
            self.replace_question_id,
            self.replacement_question_id,
        )
        if self.action == TeacherReviewAction.REPLACE:
            if any(value is None for value in replacement_ids):
                raise ValueError("replace action requires old and new question IDs")
            if self.replace_question_id == self.replacement_question_id:
                raise ValueError("replacement question must differ from old question")
        elif any(value is not None for value in replacement_ids):
            raise ValueError("replacement IDs are only valid for replace action")

        if self.action == TeacherReviewAction.REJECT and self.comment is None:
            raise ValueError("reject action requires a comment")
        return self


class TeacherReviewTaskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: Identifier
    awaiting_teacher: bool
    state: PaperGraphState
