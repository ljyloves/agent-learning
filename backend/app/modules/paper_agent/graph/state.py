"""Lightweight, checkpoint-safe state for the paper-generation graph."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.modules.paper_agent.schemas.paper_job import PaperJobStatus


Identifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
ReportText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
MetricName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
MetricText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
ReportMetricValue: TypeAlias = MetricText | int | float | bool | None


class PaperGraphReportLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class PaperGraphDecision(str, Enum):
    """Supported outcomes emitted by the workflow decision node."""

    PASS = "pass"
    FAIL = "fail"
    RETRY = "retry"
    REPLACE = "replace"


class PaperGraphReport(BaseModel):
    """Bounded node output kept in graph state for audit and routing."""

    model_config = ConfigDict(extra="forbid")

    report_id: Identifier
    stage: Identifier
    level: PaperGraphReportLevel = PaperGraphReportLevel.INFO
    summary: ReportText
    metrics: dict[MetricName, ReportMetricValue] = Field(
        default_factory=dict,
        max_length=100,
    )
    issue_codes: list[Identifier] = Field(default_factory=list, max_length=100)

    @field_validator("issue_codes")
    @classmethod
    def require_unique_issue_codes(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("report issue_codes must be unique")
        return values


class PaperGraphExecution(BaseModel):
    """Execution control data; domain payloads belong in persistent storage."""

    model_config = ConfigDict(extra="forbid")

    status: PaperJobStatus = PaperJobStatus.QUEUED
    current_node: Identifier | None = None
    attempt: int = Field(default=0, ge=0)
    decision: PaperGraphDecision | None = None
    retry_count: int = Field(default=0, ge=0, le=100)
    replacement_count: int = Field(default=0, ge=0, le=1000)
    error_code: Identifier | None = None

    @model_validator(mode="after")
    def validate_error_state(self) -> PaperGraphExecution:
        if self.status == PaperJobStatus.FAILED and self.error_code is None:
            raise ValueError("failed graph execution requires error_code")
        if self.status != PaperJobStatus.FAILED and self.error_code is not None:
            raise ValueError("error_code is only valid for failed graph execution")
        return self


class PaperGraphState(BaseModel):
    """Checkpoint state containing only identifiers, reports, and execution state."""

    model_config = ConfigDict(extra="forbid")

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
    reports: list[PaperGraphReport] = Field(default_factory=list, max_length=200)
    execution: PaperGraphExecution = Field(default_factory=PaperGraphExecution)

    @field_validator("candidate_question_ids", "selected_question_ids")
    @classmethod
    def require_unique_question_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("question identifiers must be unique")
        return values

    @field_validator("reports")
    @classmethod
    def require_unique_report_ids(
        cls,
        reports: list[PaperGraphReport],
    ) -> list[PaperGraphReport]:
        report_ids = [report.report_id for report in reports]
        if len(report_ids) != len(set(report_ids)):
            raise ValueError("report identifiers must be unique")
        return reports

    @model_validator(mode="after")
    def selected_questions_must_be_candidates(self) -> PaperGraphState:
        unknown_ids = set(self.selected_question_ids) - set(
            self.candidate_question_ids
        )
        if unknown_ids:
            raise ValueError(
                "selected_question_ids must be contained in candidate_question_ids"
            )
        return self
