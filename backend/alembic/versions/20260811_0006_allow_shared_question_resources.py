"""Allow one stored image resource to be referenced more than once.

Revision ID: 20260811_0006
Revises: 20260811_0005
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260811_0006"
down_revision: str | None = "20260811_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_question_images_resource_id",
        "question_images",
        type_="unique",
    )
    op.create_index(
        "ix_question_images_resource_id",
        "question_images",
        ["resource_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_question_images_resource_id", table_name="question_images")
    op.create_unique_constraint(
        "uq_question_images_resource_id",
        "question_images",
        ["resource_id"],
    )
