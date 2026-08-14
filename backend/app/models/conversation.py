"""Persistence models for conversational paper generation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConversationModel(Base):
    __tablename__ = "paper_conversations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_paper_conversations_status",
        ),
        CheckConstraint(
            "active_plan_version >= 0",
            name="ck_paper_conversations_active_plan_version",
        ),
        UniqueConstraint(
            "paper_job_id",
            name="uq_paper_conversations_paper_job_id",
        ),
    )

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    title: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default=text("'active'"),
        index=True,
    )
    active_plan_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    paper_job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("paper_jobs.job_id", ondelete="SET NULL"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class ConversationMessageModel(Base):
    __tablename__ = "paper_conversation_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('teacher', 'assistant', 'system', 'tool')",
            name="ck_paper_conversation_messages_role",
        ),
        CheckConstraint(
            "sequence_no >= 1",
            name="ck_paper_conversation_messages_sequence",
        ),
        UniqueConstraint(
            "conversation_id",
            "sequence_no",
            name="uq_paper_conversation_messages_sequence",
        ),
    )

    message_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("paper_conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class PaperPlanVersionModel(Base):
    __tablename__ = "paper_plan_versions"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_paper_plan_versions_version"),
        UniqueConstraint(
            "conversation_id",
            "version",
            name="uq_paper_plan_versions_conversation_version",
        ),
        UniqueConstraint(
            "conversation_id",
            "source_message_id",
            name="uq_paper_plan_versions_source_message",
        ),
    )

    plan_version_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("paper_conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("paper_conversation_messages.message_id", ondelete="SET NULL"),
    )
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class PendingActionModel(Base):
    __tablename__ = "paper_pending_actions"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('create_paper', 'lock_questions', "
            "'replace_question', 'reassemble_paper', 'submit_review', "
            "'export_documents', 'apply_taxonomy_change', "
            "'deactivate_taxonomy_item')",
            name="ck_paper_pending_actions_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'executing', 'completed', "
            "'cancelled', 'failed')",
            name="ck_paper_pending_actions_status",
        ),
        CheckConstraint(
            "plan_version IS NULL OR plan_version >= 1",
            name="ck_paper_pending_actions_plan_version",
        ),
        Index(
            "uq_paper_pending_actions_active_conversation",
            "conversation_id",
            unique=True,
            postgresql_where=text(
                "status IN ('pending', 'confirmed', 'executing')"
            ),
        ),
    )

    action_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("paper_conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        index=True,
    )
    source_message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("paper_conversation_messages.message_id", ondelete="SET NULL"),
        index=True,
    )
    plan_version: Mapped[int | None] = mapped_column(Integer)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True)
    )
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    paper_job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("paper_jobs.job_id", ondelete="SET NULL"),
        index=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class ToolExecutionModel(Base):
    __tablename__ = "paper_tool_executions"
    __table_args__ = (
        CheckConstraint(
            "access_mode IN ('read', 'write')",
            name="ck_paper_tool_executions_access_mode",
        ),
        CheckConstraint(
            "status IN ('started', 'succeeded', 'failed', 'timed_out')",
            name="ck_paper_tool_executions_status",
        ),
        CheckConstraint(
            "attempt_count >= 1",
            name="ck_paper_tool_executions_attempt_count",
        ),
        UniqueConstraint("action_id", name="uq_paper_tool_executions_action_id"),
    )

    execution_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("paper_conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("paper_pending_actions.action_id", ondelete="CASCADE"),
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    access_mode: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True)
    )
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
