"""Add append-only question analysis results.

Revision ID: 20260811_0007
Revises: 20260811_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260811_0007"
down_revision: str | None = "20260811_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_analyses",
        sa.Column("analysis_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("analysis_type", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "analysis_type IN ('difficulty_estimation', 'quality_review')",
            name="ck_question_analyses_type",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("analysis_id"),
    )
    op.create_index(
        "ix_question_analyses_question_type_created",
        "question_analyses",
        ["question_id", "analysis_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_question_analyses_question_type_created",
        table_name="question_analyses",
    )
    op.drop_table("question_analyses")
