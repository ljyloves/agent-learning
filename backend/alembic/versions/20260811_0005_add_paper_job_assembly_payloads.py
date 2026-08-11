"""Persist assembly requests and results on paper jobs.

Revision ID: 20260811_0005
Revises: 20260811_0004
Create Date: 2026-08-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260811_0005"
down_revision: str | None = "20260811_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "paper_jobs",
        sa.Column(
            "assembly_request",
            postgresql.JSONB(none_as_null=True),
            nullable=True,
        ),
    )
    op.add_column(
        "paper_jobs",
        sa.Column(
            "assembly_result",
            postgresql.JSONB(none_as_null=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("paper_jobs", "assembly_result")
    op.drop_column("paper_jobs", "assembly_request")
