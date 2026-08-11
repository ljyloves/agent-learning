"""Add question difficulty for constrained paper assembly.

Revision ID: 20260811_0004
Revises: 20260811_0003
Create Date: 2026-08-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260811_0004"
down_revision: str | None = "20260811_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MOCK_SOURCE_ID = "bio016-molecular-cell-mock-bank"


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column(
            "difficulty",
            sa.String(length=16),
            server_default=sa.text("'medium'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_questions_difficulty",
        "questions",
        "difficulty IN ('easy', 'medium', 'hard')",
    )
    op.create_index(
        "ix_questions_difficulty",
        "questions",
        ["difficulty"],
    )
    op.execute(
        sa.text(
            """
            UPDATE questions
            SET difficulty = CASE position % 3
                WHEN 0 THEN 'easy'
                WHEN 1 THEN 'medium'
                ELSE 'hard'
            END
            WHERE source_id = :source_id
            """
        ).bindparams(source_id=MOCK_SOURCE_ID)
    )


def downgrade() -> None:
    op.drop_index("ix_questions_difficulty", table_name="questions")
    op.drop_constraint(
        "ck_questions_difficulty",
        "questions",
        type_="check",
    )
    op.drop_column("questions", "difficulty")
