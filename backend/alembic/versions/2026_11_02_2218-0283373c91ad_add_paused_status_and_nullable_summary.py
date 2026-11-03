"""add paused status and nullable summary

Revision ID: 0283373c91ad
Revises: 6ea7d559d674
Create Date: 2026-11-02 22:18:33.233693

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0283373c91ad'
down_revision: Union[str, Sequence[str], None] = '6ea7d559d674'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # New repo status for "daily LLM quota hit, resume later".
    op.execute("ALTER TYPE repository_status ADD VALUE 'PAUSED' AFTER 'ANALYZED'")

    # The structure pass now saves a file's knowledge before any LLM call,
    # so summary is empty until the summary pass fills it in.
    op.alter_column(
        "file_knowledge",
        "summary",
        existing_type=sa.Text(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Rows without a summary would block NOT NULL - give them an empty one first.
    op.execute("UPDATE file_knowledge SET summary = '' WHERE summary IS NULL")
    op.alter_column(
        "file_knowledge",
        "summary",
        existing_type=sa.Text(),
        nullable=False,
    )

    # Postgres does NOT support removing a value from an enum type, so
    # 'PAUSED' stays - same deliberate no-op as the ANALYZING/ANALYZED
    # migrations.
