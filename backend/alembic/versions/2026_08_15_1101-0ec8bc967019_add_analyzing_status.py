"""add analyzing status

Revision ID: 0ec8bc967019
Revises: e586525d4db6
Create Date: 2026-08-15 11:01:34.200550

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0ec8bc967019'
down_revision: Union[str, Sequence[str], None] = 'e586525d4db6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE repository_status ADD VALUE 'ANALYZING' AFTER 'SCANNED';")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres does NOT support removing a value from an enum type -
    # there's no "ALTER TYPE ... DROP VALUE". A true downgrade would mean
    # recreating the enum type from scratch and migrating the column over,
    # which is riskier than it's worth for a dev-only, not-yet-deployed
    # project. Leaving this as a no-op is a deliberate, flagged choice,
    # not an oversight.
    pass
