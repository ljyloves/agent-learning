"""Decision and terminal branch nodes for the paper-generation workflow."""

from __future__ import annotations

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
from app.modules.paper_agent.schemas.paper_job import PaperJobStatus


QUALITY_GATE_STAGE = "quality_gate"
MAX_RETRY_ATTEMPTS = 3


def latest_quality_gate_report(
    reports: list[PaperGraphReport],
) -> PaperGraphReport | None:
    return next(
        (report for report in reversed(reports) if report.stage == QUALITY_GATE_STAGE),
        None,
    )


def decision_from_reports(reports: list[PaperGraphReport]) -> PaperGraphDecision:
    report = latest_quality_gate_report(reports)
    if report is None:
        return PaperGraphDecision.PASS
    value = report.metrics.get("decision")
    if not isinstance(value, str):
        raise ValueError("quality_gate report requires a string decision metric")
    return PaperGraphDecision(value)


def _require_decision(
    execution: PaperGraphExecution,
    expected: PaperGraphDecision,
) -> None:
    if execution.decision != expected:
        raise ValueError(f"node requires the {expected.value} decision")


def _report_metric(report: PaperGraphReport, name: str) -> str | None:
    value = report.metrics.get(name)
    return value if isinstance(value, str) and value else None


class _BranchNodeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reports: list[PaperGraphReport] = Field(max_length=200)
    execution: PaperGraphExecution


class _BranchNodeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reports: list[PaperGraphReport] = Field(max_length=200)
    execution: PaperGraphExecution


class DecideNodeInput(_BranchNodeInput):
    @model_validator(mode="after")
    def validate_quality_gate_decision(self) -> DecideNodeInput:
        decision_from_reports(self.reports)
        return self


class DecideNodeOutput(_BranchNodeOutput):
    pass


class CompleteNodeInput(_BranchNodeInput):
    @model_validator(mode="after")
    def require_pass_decision(self) -> CompleteNodeInput:
        _require_decision(self.execution, PaperGraphDecision.PASS)
        return self


class CompleteNodeOutput(_BranchNodeOutput):
    pass


class FailNodeInput(_BranchNodeInput):
    @model_validator(mode="after")
    def require_failure_decision(self) -> FailNodeInput:
        if self.execution.decision == PaperGraphDecision.FAIL:
            return self
        if (
            self.execution.decision == PaperGraphDecision.RETRY
            and self.execution.retry_count >= MAX_RETRY_ATTEMPTS
        ):
            return self
        raise ValueError("fail node requires fail or exhausted retry decision")


class FailNodeOutput(_BranchNodeOutput):
    pass


class RetryNodeInput(_BranchNodeInput):
    @model_validator(mode="after")
    def require_retry_decision(self) -> RetryNodeInput:
        _require_decision(self.execution, PaperGraphDecision.RETRY)
        if self.execution.retry_count >= MAX_RETRY_ATTEMPTS:
            raise ValueError("retry limit has been reached")
        return self


class RetryNodeOutput(_BranchNodeOutput):
    pass


class ReplaceQuestionNodeInput(_BranchNodeInput):
    candidate_question_ids: list[Identifier] = Field(max_length=1000)
    selected_question_ids: list[Identifier] = Field(max_length=1000)

    @model_validator(mode="after")
    def validate_replacement_instruction(self) -> ReplaceQuestionNodeInput:
        _require_decision(self.execution, PaperGraphDecision.REPLACE)
        report = latest_quality_gate_report(self.reports)
        if report is None:
            raise ValueError("replace decision requires a quality_gate report")
        old_id = _report_metric(report, "replace_question_id")
        new_id = _report_metric(report, "replacement_question_id")
        if old_id is None or new_id is None:
            raise ValueError("replace decision requires old and new question IDs")
        if old_id not in self.selected_question_ids:
            raise ValueError("question to replace must be selected")
        if new_id not in self.candidate_question_ids:
            raise ValueError("replacement question must be a candidate")
        if new_id == old_id or new_id in self.selected_question_ids:
            raise ValueError("replacement question must be a new selection")
        return self


class ReplaceQuestionNodeOutput(_BranchNodeOutput):
    selected_question_ids: list[Identifier] = Field(max_length=1000)


DECIDE_NODE_CONTRACT = GraphNodeContract(
    name="decide",
    state_model=PaperGraphState,
    input_model=DecideNodeInput,
    output_model=DecideNodeOutput,
)
COMPLETE_NODE_CONTRACT = GraphNodeContract(
    name="complete",
    state_model=PaperGraphState,
    input_model=CompleteNodeInput,
    output_model=CompleteNodeOutput,
)
FAIL_NODE_CONTRACT = GraphNodeContract(
    name="fail",
    state_model=PaperGraphState,
    input_model=FailNodeInput,
    output_model=FailNodeOutput,
)
RETRY_NODE_CONTRACT = GraphNodeContract(
    name="retry",
    state_model=PaperGraphState,
    input_model=RetryNodeInput,
    output_model=RetryNodeOutput,
)
REPLACE_QUESTION_NODE_CONTRACT = GraphNodeContract(
    name="replace_question",
    state_model=PaperGraphState,
    input_model=ReplaceQuestionNodeInput,
    output_model=ReplaceQuestionNodeOutput,
)


@validated_node(DECIDE_NODE_CONTRACT)
def decide_workflow(state: DecideNodeInput) -> DecideNodeOutput:
    decision = decision_from_reports(state.reports)
    report = PaperGraphReport(
        report_id=f"workflow-decision:{state.execution.attempt}",
        stage="workflow_decision",
        summary=f"Workflow selected the {decision.value} branch.",
        metrics={"decision": decision.value},
    )
    execution = PaperGraphExecution(
        status=PaperJobStatus.RUNNING,
        current_node="decide",
        attempt=state.execution.attempt,
        decision=decision,
        retry_count=state.execution.retry_count,
        replacement_count=state.execution.replacement_count,
    )
    return DecideNodeOutput(reports=[*state.reports, report], execution=execution)


@validated_node(COMPLETE_NODE_CONTRACT)
def complete_workflow(state: CompleteNodeInput) -> CompleteNodeOutput:
    report = PaperGraphReport(
        report_id=f"complete:{state.execution.attempt}",
        stage="complete",
        summary="Paper workflow completed successfully.",
        metrics={"attempt": state.execution.attempt},
    )
    execution = PaperGraphExecution(
        status=PaperJobStatus.COMPLETED,
        current_node="complete",
        attempt=state.execution.attempt,
        decision=PaperGraphDecision.PASS,
        retry_count=state.execution.retry_count,
        replacement_count=state.execution.replacement_count,
    )
    return CompleteNodeOutput(reports=[*state.reports, report], execution=execution)


@validated_node(FAIL_NODE_CONTRACT)
def fail_workflow(state: FailNodeInput) -> FailNodeOutput:
    exhausted = state.execution.decision == PaperGraphDecision.RETRY
    quality_report = latest_quality_gate_report(state.reports)
    quality_error = (
        _report_metric(quality_report, "error_code")
        if quality_report is not None
        else None
    )
    error_code = (
        "RETRY_LIMIT_EXCEEDED"
        if exhausted
        else quality_error or "QUALITY_GATE_FAILED"
    )
    report = PaperGraphReport(
        report_id=f"fail:{state.execution.attempt}",
        stage="fail",
        level=PaperGraphReportLevel.ERROR,
        summary=f"Paper workflow failed with {error_code}.",
        metrics={"error_code": error_code},
        issue_codes=[error_code],
    )
    execution = PaperGraphExecution(
        status=PaperJobStatus.FAILED,
        current_node="fail",
        attempt=state.execution.attempt,
        decision=state.execution.decision,
        retry_count=state.execution.retry_count,
        replacement_count=state.execution.replacement_count,
        error_code=error_code,
    )
    return FailNodeOutput(reports=[*state.reports, report], execution=execution)


@validated_node(RETRY_NODE_CONTRACT)
def queue_workflow_retry(state: RetryNodeInput) -> RetryNodeOutput:
    retry_count = state.execution.retry_count + 1
    report = PaperGraphReport(
        report_id=f"retry:{state.execution.attempt}",
        stage="retry",
        level=PaperGraphReportLevel.WARNING,
        summary="Paper workflow queued for another attempt.",
        metrics={"retry_count": retry_count},
    )
    execution = PaperGraphExecution(
        status=PaperJobStatus.QUEUED,
        current_node="retry",
        attempt=state.execution.attempt,
        decision=PaperGraphDecision.RETRY,
        retry_count=retry_count,
        replacement_count=state.execution.replacement_count,
    )
    return RetryNodeOutput(reports=[*state.reports, report], execution=execution)


@validated_node(REPLACE_QUESTION_NODE_CONTRACT)
def replace_question(
    state: ReplaceQuestionNodeInput,
) -> ReplaceQuestionNodeOutput:
    quality_report = latest_quality_gate_report(state.reports)
    if quality_report is None:
        raise ValueError("replace decision requires a quality_gate report")
    old_id = _report_metric(quality_report, "replace_question_id")
    new_id = _report_metric(quality_report, "replacement_question_id")
    if old_id is None or new_id is None:
        raise ValueError("replace decision requires old and new question IDs")
    selected_ids = [
        new_id if question_id == old_id else question_id
        for question_id in state.selected_question_ids
    ]
    replacement_count = state.execution.replacement_count + 1
    report = PaperGraphReport(
        report_id=f"replace-question:{state.execution.attempt}",
        stage="replace_question",
        level=PaperGraphReportLevel.WARNING,
        summary="Selected question was replaced and queued for review.",
        metrics={
            "replace_question_id": old_id,
            "replacement_question_id": new_id,
            "replacement_count": replacement_count,
        },
    )
    execution = PaperGraphExecution(
        status=PaperJobStatus.QUEUED,
        current_node="replace_question",
        attempt=state.execution.attempt,
        decision=PaperGraphDecision.REPLACE,
        retry_count=state.execution.retry_count,
        replacement_count=replacement_count,
    )
    return ReplaceQuestionNodeOutput(
        selected_question_ids=selected_ids,
        reports=[*state.reports, report],
        execution=execution,
    )


MAIN_WORKFLOW_NODES = (
    decide_workflow,
    complete_workflow,
    fail_workflow,
    queue_workflow_retry,
    replace_question,
)
