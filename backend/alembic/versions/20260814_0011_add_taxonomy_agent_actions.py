"""Add audited taxonomy maintenance actions.

Revision ID: 20260814_0011
Revises: 20260814_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260814_0011"
down_revision: str | None = "20260814_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_paper_pending_actions_type",
        "paper_pending_actions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_paper_pending_actions_type",
        "paper_pending_actions",
        "action_type IN ('create_paper', 'lock_questions', 'replace_question', "
        "'reassemble_paper', 'submit_review', 'export_documents', "
        "'apply_taxonomy_change', 'deactivate_taxonomy_item')",
    )
    op.add_column(
        "paper_pending_actions",
        sa.Column("source_message_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_paper_pending_actions_source_message_id",
        "paper_pending_actions",
        "paper_conversation_messages",
        ["source_message_id"],
        ["message_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_paper_pending_actions_source_message_id",
        "paper_pending_actions",
        ["source_message_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_paper_pending_actions_source_message_id",
        table_name="paper_pending_actions",
    )
    op.drop_constraint(
        "fk_paper_pending_actions_source_message_id",
        "paper_pending_actions",
        type_="foreignkey",
    )
    op.drop_column("paper_pending_actions", "source_message_id")
    op.drop_constraint(
        "ck_paper_pending_actions_type",
        "paper_pending_actions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_paper_pending_actions_type",
        "paper_pending_actions",
        "action_type IN ('create_paper', 'lock_questions', 'replace_question', "
        "'reassemble_paper', 'submit_review', 'export_documents')",
    )
