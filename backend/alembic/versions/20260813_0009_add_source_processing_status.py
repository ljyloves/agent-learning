"""Persist source parsing status for the teacher resource library.

Revision ID: 20260813_0009
Revises: 20260812_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260813_0009"
down_revision: str | None = "20260812_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "question_sources",
        sa.Column(
            "processing_status",
            sa.String(length=24),
            server_default="completed",
            nullable=False,
        ),
    )
    op.add_column(
        "question_sources",
        sa.Column("parse_failure_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "question_sources",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_question_sources_processing_status",
        "question_sources",
        "processing_status IN ('uploaded', 'processing', 'completed', 'failed')",
    )
    op.create_check_constraint(
        "ck_question_sources_parse_failure_reason",
        "question_sources",
        "(processing_status = 'failed' AND parse_failure_reason IS NOT NULL) OR "
        "(processing_status <> 'failed' AND parse_failure_reason IS NULL)",
    )
    op.create_index(
        "ix_question_sources_processing_status",
        "question_sources",
        ["processing_status"],
    )
    op.execute(
        """
        UPDATE question_sources AS source
        SET processing_status = 'uploaded'
        WHERE source.source_type IN ('file', 'website')
          AND NOT EXISTS (
              SELECT 1 FROM questions
              WHERE questions.source_id = source.source_id
          )
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_question_sources_processing_status",
        table_name="question_sources",
    )
    op.drop_constraint(
        "ck_question_sources_parse_failure_reason",
        "question_sources",
        type_="check",
    )
    op.drop_constraint(
        "ck_question_sources_processing_status",
        "question_sources",
        type_="check",
    )
    op.drop_column("question_sources", "processed_at")
    op.drop_column("question_sources", "parse_failure_reason")
    op.drop_column("question_sources", "processing_status")
