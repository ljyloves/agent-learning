"""Contracts for one tool-aware conversational Agent turn."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.paper_agent.schemas.conversation import PaperPlan


class ConversationAgentOutcomeKind(StrEnum):
    REPLY = "reply"
    NEEDS_INPUT = "needs_input"
    PLAN = "plan"
    WRITE_ACTION = "write_action"
    FORM_FALLBACK = "form_fallback"


class ConversationAgentOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ConversationAgentOutcomeKind
    reply: str | None = Field(default=None, min_length=1, max_length=20_000)
    plan: PaperPlan | None = None
    tool_name: str | None = Field(default=None, min_length=1, max_length=100)
    tool_payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "ConversationAgentOutcome":
        if self.kind in {
            ConversationAgentOutcomeKind.REPLY,
            ConversationAgentOutcomeKind.NEEDS_INPUT,
            ConversationAgentOutcomeKind.FORM_FALLBACK,
        }:
            if self.reply is None:
                raise ValueError("reply outcome requires reply")
        elif self.kind == ConversationAgentOutcomeKind.PLAN:
            if self.plan is None:
                raise ValueError("plan outcome requires plan")
        elif self.kind == ConversationAgentOutcomeKind.WRITE_ACTION:
            if self.tool_name is None or self.tool_payload is None:
                raise ValueError("write action requires tool name and payload")
        return self


__all__ = ["ConversationAgentOutcome", "ConversationAgentOutcomeKind"]
