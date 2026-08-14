"""Strict contracts for conversational paper planning and execution."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.modules.paper_agent.schemas.optimization import (
    Identifier,
    OptimizedPaperRequest,
)
from app.modules.paper_agent.schemas.optimized_task import (
    OptimizedPaperInfo,
    OptimizedPaperTaskCreate,
)


DatabaseIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=36),
]


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MessageRole(StrEnum):
    TEACHER = "teacher"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class PendingActionType(StrEnum):
    CREATE_PAPER = "create_paper"
    LOCK_QUESTIONS = "lock_questions"
    REPLACE_QUESTION = "replace_question"
    REASSEMBLE_PAPER = "reassemble_paper"
    SUBMIT_REVIEW = "submit_review"
    EXPORT_DOCUMENTS = "export_documents"
    APPLY_TAXONOMY_CHANGE = "apply_taxonomy_change"
    DEACTIVATE_TAXONOMY_ITEM = "deactivate_taxonomy_item"


class PendingActionStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXECUTING = "executing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ToolAccessMode(StrEnum):
    READ = "read"
    WRITE = "write"


class ToolExecutionStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class PaperPlan(BaseModel):
    """Canonical teacher-confirmed input for one paper generation run."""

    model_config = ConfigDict(extra="forbid")

    paper_info: OptimizedPaperInfo
    optimization: OptimizedPaperRequest

    def to_task_create(self) -> OptimizedPaperTaskCreate:
        return OptimizedPaperTaskCreate(
            paper_info=self.paper_info,
            optimization=self.optimization,
        )


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: DatabaseIdentifier | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)


class ConversationMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: DatabaseIdentifier
    content: str = Field(min_length=1, max_length=20_000)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    conversation_id: DatabaseIdentifier
    title: str | None = None
    status: ConversationStatus
    active_plan_version: int = Field(ge=0)
    paper_job_id: Identifier | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ConversationMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    message_id: DatabaseIdentifier
    conversation_id: DatabaseIdentifier
    sequence_no: int = Field(ge=1)
    role: MessageRole
    content: str = Field(min_length=1, max_length=20_000)
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: AwareDatetime


class ConversationHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation: ConversationRead
    messages: list[ConversationMessage]


class PaperPlanVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_version_id: DatabaseIdentifier
    conversation_id: DatabaseIdentifier
    version: int = Field(ge=1)
    source_message_id: DatabaseIdentifier | None = None
    plan: PaperPlan
    created_at: AwareDatetime


class ConversationPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: DatabaseIdentifier
    active_plan_version: int = Field(ge=0)
    plan: PaperPlan | None = None


class ConversationPlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: DatabaseIdentifier
    plan: PaperPlan


class AgentApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Identifier
    message: str = Field(min_length=1, max_length=1000)
    retryable: bool = False


class PendingAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: Identifier
    conversation_id: DatabaseIdentifier
    action_type: PendingActionType
    status: PendingActionStatus
    source_message_id: DatabaseIdentifier | None = None
    plan_version: int | None = Field(default=None, ge=1)
    request_payload: dict[str, Any]
    result_payload: dict[str, Any] | None = None
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = None
    paper_job_id: Identifier | None = None


class ToolExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: DatabaseIdentifier
    conversation_id: DatabaseIdentifier
    action_id: Identifier | None = None
    tool_name: Identifier
    access_mode: ToolAccessMode
    status: ToolExecutionStatus
    attempt_count: int = Field(ge=1)
    request_payload: dict[str, Any]
    result_payload: dict[str, Any] | None = None
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = None
