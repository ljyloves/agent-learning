"""Durable human-review nodes for assembled papers."""

from __future__ import annotations

from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.paper_agent.graph.contracts import GraphNodeContract, validated_node
from app.modules.paper_agent.graph.state import (
    Identifier,
    PaperGraphDecision,
    PaperGraphExecution,
    PaperGraphReport,
    PaperGraphReportLevel,
    PaperGraphState,
)
from app.modules.paper_agent.schemas.checkpoint import (
    TeacherReviewAction,
    TeacherReviewCommand,
)
from app.modules.paper_agent.schemas.paper_job import PaperJobStatus


TEACHER_REVIEW_STAGE = "teacher_review"


class QueueTeacherReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reports: list[PaperGraphReport] = Field(max_length=200)
    execution: PaperGraphExecution


class QueueTeacherReviewOutput(QueueTeacherReviewInput):
    pass


class AwaitTeacherReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: Identifier
    paper_id: Identifier | None = None
    selected_question_ids: list[Identifier] = Field(max_length=1000)
    reports: list[PaperGraphReport] = Field(max_length=200)
    execution: PaperGraphExecution

    @model_validator(mode="after")
    def require_awaiting_review(self) -> AwaitTeacherReviewInput:
        if self.execution.status != PaperJobStatus.AWAITING_REVIEW:
            raise ValueError("teacher review node requires awaiting_review status")
        return self


class AwaitTeacherReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reports: list[PaperGraphReport] = Field(max_length=200)
    execution: PaperGraphExecution


QUEUE_TEACHER_REVIEW_CONTRACT = GraphNodeContract(
    name="queue_teacher_review",
    state_model=PaperGraphState,
    input_model=QueueTeacherReviewInput,
    output_model=QueueTeacherReviewOutput,
)
AWAIT_TEACHER_REVIEW_CONTRACT = GraphNodeContract(
    name="await_teacher_review",
    state_model=PaperGraphState,
    input_model=AwaitTeacherReviewInput,
    output_model=AwaitTeacherReviewOutput,
)


@validated_node(QUEUE_TEACHER_REVIEW_CONTRACT)
def queue_teacher_review(
    state: QueueTeacherReviewInput,
) -> QueueTeacherReviewOutput:
    review_round = state.execution.replacement_count + 1
    report = PaperGraphReport(
        report_id=(
            f"teacher-review-request:{state.execution.attempt}:{review_round}"
        ),
        stage=TEACHER_REVIEW_STAGE,
        summary="Assembled paper is waiting for teacher review.",
        metrics={"review_round": review_round},
    )
    execution = PaperGraphExecution(
        status=PaperJobStatus.AWAITING_REVIEW,
        current_node="await_teacher_review",
        attempt=state.execution.attempt,
        retry_count=state.execution.retry_count,
        replacement_count=state.execution.replacement_count,
    )
    return QueueTeacherReviewOutput(
        reports=[*state.reports, report],
        execution=execution,
    )


def _decision_for_action(action: TeacherReviewAction) -> PaperGraphDecision:
    return {
        TeacherReviewAction.APPROVE: PaperGraphDecision.PASS,
        TeacherReviewAction.REJECT: PaperGraphDecision.FAIL,
        TeacherReviewAction.REPLACE: PaperGraphDecision.REPLACE,
    }[action]


@validated_node(AWAIT_TEACHER_REVIEW_CONTRACT)
def await_teacher_review(
    state: AwaitTeacherReviewInput,
) -> AwaitTeacherReviewOutput:
    review_round = state.execution.replacement_count + 1
    raw_command = interrupt(
        {
            "kind": "teacher_review",
            "job_id": state.job_id,
            "paper_id": state.paper_id,
            "selected_question_ids": state.selected_question_ids,
            "review_round": review_round,
        }
    )
    command = TeacherReviewCommand.model_validate(raw_command)
    decision = _decision_for_action(command.action)
    review_metrics = {
        "action": command.action.value,
        "reviewer": command.reviewer,
        "comment": command.comment,
        "review_round": review_round,
    }
    review_report = PaperGraphReport(
        report_id=f"teacher-review-decision:{state.execution.attempt}:{review_round}",
        stage=TEACHER_REVIEW_STAGE,
        level=(
            PaperGraphReportLevel.INFO
            if command.action == TeacherReviewAction.APPROVE
            else PaperGraphReportLevel.WARNING
        ),
        summary=f"Teacher submitted the {command.action.value} action.",
        metrics=review_metrics,
    )
    quality_metrics = {"decision": decision.value}
    if command.action == TeacherReviewAction.REJECT:
        quality_metrics["error_code"] = "TEACHER_REJECTED"
    if command.action == TeacherReviewAction.REPLACE:
        quality_metrics["replace_question_id"] = command.replace_question_id
        quality_metrics["replacement_question_id"] = (
            command.replacement_question_id
        )
    quality_report = PaperGraphReport(
        report_id=f"teacher-quality-gate:{state.execution.attempt}:{review_round}",
        stage="quality_gate",
        summary=f"Teacher review requested {decision.value}.",
        metrics=quality_metrics,
    )
    execution = PaperGraphExecution(
        status=PaperJobStatus.RUNNING,
        current_node="await_teacher_review",
        attempt=state.execution.attempt,
        decision=decision,
        retry_count=state.execution.retry_count,
        replacement_count=state.execution.replacement_count,
    )
    return AwaitTeacherReviewOutput(
        reports=[*state.reports, review_report, quality_report],
        execution=execution,
    )


TEACHER_REVIEW_NODES = (
    queue_teacher_review,
    await_teacher_review,
)
