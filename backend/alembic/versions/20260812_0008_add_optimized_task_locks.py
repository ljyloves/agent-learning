"""Add optimized task mode and persisted question locks.

Revision ID: 20260812_0008
Revises: 20260811_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260812_0008"
down_revision: str | None = "20260811_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "paper_jobs",
        sa.Column(
            "generation_mode",
            sa.String(length=16),
            server_default="basic",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_paper_jobs_generation_mode",
        "paper_jobs",
        "generation_mode IN ('basic', 'optimized')",
    )
    op.create_index(
        "ix_paper_jobs_generation_mode",
        "paper_jobs",
        ["generation_mode"],
    )
    op.add_column(
        "paper_job_questions",
        sa.Column(
            "is_locked",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("paper_job_questions", "is_locked")
    op.drop_index("ix_paper_jobs_generation_mode", table_name="paper_jobs")
    op.drop_constraint(
        "ck_paper_jobs_generation_mode",
        "paper_jobs",
        type_="check",
    )
    op.drop_column("paper_jobs", "generation_mode")
