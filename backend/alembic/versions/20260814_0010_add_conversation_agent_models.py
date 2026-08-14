"""Add conversational paper agent persistence models.

Revision ID: 20260814_0010
Revises: 20260813_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260814_0010"
down_revision: str | None = "20260813_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_conversations",
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("active_plan_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("paper_job_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_paper_conversations_status"),
        sa.CheckConstraint("active_plan_version >= 0", name="ck_paper_conversations_active_plan_version"),
        sa.ForeignKeyConstraint(["paper_job_id"], ["paper_jobs.job_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("conversation_id"),
        sa.UniqueConstraint("paper_job_id", name="uq_paper_conversations_paper_job_id"),
    )
    op.create_index("ix_paper_conversations_status", "paper_conversations", ["status"])
    op.create_index("ix_paper_conversations_paper_job_id", "paper_conversations", ["paper_job_id"])

    op.create_table(
        "paper_conversation_messages",
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('teacher', 'assistant', 'system', 'tool')", name="ck_paper_conversation_messages_role"),
        sa.CheckConstraint("sequence_no >= 1", name="ck_paper_conversation_messages_sequence"),
        sa.ForeignKeyConstraint(["conversation_id"], ["paper_conversations.conversation_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_id"),
        sa.UniqueConstraint("conversation_id", "sequence_no", name="uq_paper_conversation_messages_sequence"),
    )
    op.create_index("ix_paper_conversation_messages_conversation_id", "paper_conversation_messages", ["conversation_id"])

    op.create_table(
        "paper_plan_versions",
        sa.Column("plan_version_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_message_id", sa.String(length=36), nullable=True),
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_paper_plan_versions_version"),
        sa.ForeignKeyConstraint(["conversation_id"], ["paper_conversations.conversation_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_message_id"], ["paper_conversation_messages.message_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("plan_version_id"),
        sa.UniqueConstraint("conversation_id", "version", name="uq_paper_plan_versions_conversation_version"),
        sa.UniqueConstraint("conversation_id", "source_message_id", name="uq_paper_plan_versions_source_message"),
    )
    op.create_index("ix_paper_plan_versions_conversation_id", "paper_plan_versions", ["conversation_id"])

    op.create_table(
        "paper_pending_actions",
        sa.Column("action_id", sa.String(length=128), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text(), none_as_null=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("paper_job_id", sa.String(length=36), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("action_type IN ('create_paper', 'lock_questions', 'replace_question', 'reassemble_paper', 'submit_review', 'export_documents')", name="ck_paper_pending_actions_type"),
        sa.CheckConstraint("status IN ('pending', 'confirmed', 'executing', 'completed', 'cancelled', 'failed')", name="ck_paper_pending_actions_status"),
        sa.CheckConstraint("plan_version IS NULL OR plan_version >= 1", name="ck_paper_pending_actions_plan_version"),
        sa.ForeignKeyConstraint(["conversation_id"], ["paper_conversations.conversation_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paper_job_id"], ["paper_jobs.job_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("action_id"),
    )
    op.create_index("ix_paper_pending_actions_conversation_id", "paper_pending_actions", ["conversation_id"])
    op.create_index("ix_paper_pending_actions_action_type", "paper_pending_actions", ["action_type"])
    op.create_index("ix_paper_pending_actions_status", "paper_pending_actions", ["status"])
    op.create_index("ix_paper_pending_actions_paper_job_id", "paper_pending_actions", ["paper_job_id"])
    op.create_index(
        "uq_paper_pending_actions_active_conversation",
        "paper_pending_actions",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'confirmed', 'executing')"),
    )

    op.create_table(
        "paper_tool_executions",
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("action_id", sa.String(length=128), nullable=True),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("access_mode", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text(), none_as_null=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("access_mode IN ('read', 'write')", name="ck_paper_tool_executions_access_mode"),
        sa.CheckConstraint("status IN ('started', 'succeeded', 'failed', 'timed_out')", name="ck_paper_tool_executions_status"),
        sa.CheckConstraint("attempt_count >= 1", name="ck_paper_tool_executions_attempt_count"),
        sa.ForeignKeyConstraint(["action_id"], ["paper_pending_actions.action_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["paper_conversations.conversation_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("execution_id"),
        sa.UniqueConstraint("action_id", name="uq_paper_tool_executions_action_id"),
    )
    op.create_index("ix_paper_tool_executions_conversation_id", "paper_tool_executions", ["conversation_id"])
    op.create_index("ix_paper_tool_executions_action_id", "paper_tool_executions", ["action_id"])
    op.create_index("ix_paper_tool_executions_tool_name", "paper_tool_executions", ["tool_name"])


def downgrade() -> None:
    op.drop_table("paper_tool_executions")
    op.drop_table("paper_pending_actions")
    op.drop_table("paper_plan_versions")
    op.drop_table("paper_conversation_messages")
    op.drop_table("paper_conversations")
