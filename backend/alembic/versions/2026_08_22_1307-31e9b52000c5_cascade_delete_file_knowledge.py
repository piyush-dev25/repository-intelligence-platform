"""cascade delete file knowledge

Revision ID: 31e9b52000c5
Revises: bc86bcb8774a
Create Date: 2026-08-22 13:07:36.433231

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31e9b52000c5'
down_revision: Union[str, Sequence[str], None] = 'bc86bcb8774a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('file_knowledge_repository_file_id_fkey', 'file_knowledge', type_='foreignkey')
    op.create_foreign_key(
        'file_knowledge_repository_file_id_fkey',
        'file_knowledge', 'repository_files',
        ['repository_file_id'], ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('file_knowledge_repository_file_id_fkey', 'file_knowledge', type_='foreignkey')
    op.create_foreign_key(
        'file_knowledge_repository_file_id_fkey',
        'file_knowledge', 'repository_files',
        ['repository_file_id'], ['id'],
    )
