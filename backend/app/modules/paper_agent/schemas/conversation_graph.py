"""Checkpoint-safe state and commands for the conversational Agent graph."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.paper_agent.schemas.optimization import Identifier


class ConversationGraphStatus(StrEnum):
    RECEIVED = "received"
    RESPONDED = "responded"
    NEEDS_INPUT = "needs_input"
    FORM_FALLBACK = "form_fallback"
    CHECKING_FEASIBILITY = "checking_feasibility"
    INFEASIBLE = "infeasible"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    EXECUTING = "executing"
    RETRYABLE = "retryable"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ConversationGraphReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Identifier
    summary: str = Field(min_length=1, max_length=1000)
    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        max_length=20,
    )


class ConversationGraphState(BaseModel):
    """Contains IDs and bounded reports only; domain payloads stay in PostgreSQL."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: Identifier
    message_id: Identifier
    plan_version: int | None = Field(default=None, ge=1)
    pending_action_id: Identifier | None = None
    paper_job_id: Identifier | None = None
    status: ConversationGraphStatus = ConversationGraphStatus.RECEIVED
    retry_count: int = Field(default=0, ge=0, le=2)
    reports: list[ConversationGraphReport] = Field(default_factory=list, max_length=30)
    error_code: Identifier | None = None

    @model_validator(mode="after")
    def validate_references(self) -> "ConversationGraphState":
        if self.status == ConversationGraphStatus.AWAITING_CONFIRMATION:
            if self.pending_action_id is None:
                raise ValueError("confirmation state requires pending_action_id")
        if self.status == ConversationGraphStatus.COMPLETED:
            if self.pending_action_id is None:
                raise ValueError("completed state requires pending_action_id")
        if self.status == ConversationGraphStatus.FAILED and self.error_code is None:
            raise ValueError("failed state requires error_code")
        return self


class ConversationGraphCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["confirm", "cancel", "retry"]


class ConversationGraphStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ConversationGraphState
    interrupted: bool
    interrupt_payload: dict[str, Any] | None = None
