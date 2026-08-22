"""add analyzed status

Revision ID: bc86bcb8774a
Revises: 0ec8bc967019
Create Date: 2026-08-15 16:38:03.237109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc86bcb8774a'
down_revision: Union[str, Sequence[str], None] = '0ec8bc967019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE repository_status ADD VALUE 'ANALYZED' AFTER 'ANALYZING'")


def downgrade() -> None:
    """Downgrade schema."""
    pass