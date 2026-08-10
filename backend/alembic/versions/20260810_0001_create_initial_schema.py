"""Create FlowGate initial schema.

Revision ID: 20260810_0001
Revises:
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260810_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "paper_jobs",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=32),
            server_default=sa.text("'not_started'"),
            nullable=False,
        ),
        sa.Column("review_result", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'awaiting_review', "
            "'completed', 'failed', 'cancelled')",
            name="ck_paper_jobs_status",
        ),
        sa.CheckConstraint(
            "(status = 'failed' AND failure_reason IS NOT NULL) OR "
            "(status <> 'failed' AND failure_reason IS NULL)",
            name="ck_paper_jobs_failure_reason",
        ),
        sa.CheckConstraint(
            "review_status IN ('not_started', 'pending', 'approved', "
            "'rejected', 'revision_required')",
            name="ck_paper_jobs_review_status",
        ),
        sa.CheckConstraint(
            "(review_status IN ('approved', 'rejected', 'revision_required') "
            "AND review_result IS NOT NULL) OR "
            "(review_status IN ('not_started', 'pending') "
            "AND review_result IS NULL)",
            name="ck_paper_jobs_review_result",
        ),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index("ix_paper_jobs_status", "paper_jobs", ["status"])
    op.create_index(
        "ix_paper_jobs_review_status",
        "paper_jobs",
        ["review_status"],
    )

    op.create_table(
        "question_sources",
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("uri", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column(
            "retrieved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("license", sa.String(length=255), nullable=True),
        sa.CheckConstraint(
            "source_type IN ('website', 'api', 'file', 'book', 'manual')",
            name="ck_question_sources_type",
        ),
        sa.CheckConstraint(
            "uri IS NOT NULL OR external_id IS NOT NULL",
            name="ck_question_sources_locator",
        ),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index(
        "ix_question_sources_source_type",
        "question_sources",
        ["source_type"],
    )

    op.create_table(
        "question_resources",
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "resource_type IN ('image', 'document', 'webpage', 'attachment')",
            name="ck_question_resources_type",
        ),
        sa.CheckConstraint(
            "sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_question_resources_sha256",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["question_sources.source_id"],
        ),
        sa.PrimaryKeyConstraint("resource_id"),
    )
    op.create_index(
        "ix_question_resources_source_id",
        "question_resources",
        ["source_id"],
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("parent_question_id", sa.String(length=36), nullable=True),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("question_type", sa.String(length=32), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("answer", postgresql.JSONB(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "position",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "question_type IN ('single_choice', 'multiple_choice', "
            "'true_false', 'fill_blank', 'short_answer', 'composite')",
            name="ck_questions_type",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_questions_position",
        ),
        sa.ForeignKeyConstraint(
            ["parent_question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["question_sources.source_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_questions_parent_question_id",
        "questions",
        ["parent_question_id"],
    )
    op.create_index("ix_questions_source_id", "questions", ["source_id"])
    op.create_index(
        "ix_questions_question_type",
        "questions",
        ["question_type"],
    )

    op.create_table(
        "question_options",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "position",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_question_options_position",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "question_id",
            "label",
            name="uq_question_options_question_label",
        ),
    )
    op.create_index(
        "ix_question_options_question_id",
        "question_options",
        ["question_id"],
    )

    op.create_table(
        "question_images",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=True),
        sa.Column("option_id", sa.String(length=36), nullable=True),
        sa.Column("alt_text", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column(
            "position",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(question_id IS NOT NULL AND option_id IS NULL) OR "
            "(question_id IS NULL AND option_id IS NOT NULL)",
            name="ck_question_images_one_owner",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_question_images_position",
        ),
        sa.ForeignKeyConstraint(
            ["option_id"],
            ["question_options.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["question_resources.resource_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resource_id",
            name="uq_question_images_resource_id",
        ),
    )
    op.create_index(
        "ix_question_images_option_id",
        "question_images",
        ["option_id"],
    )
    op.create_index(
        "ix_question_images_question_id",
        "question_images",
        ["question_id"],
    )


def downgrade() -> None:
    op.drop_table("question_images")
    op.drop_table("question_options")
    op.drop_table("questions")
    op.drop_table("question_resources")
    op.drop_table("question_sources")
    op.drop_table("paper_jobs")
    op.drop_table("knowledge_documents")
