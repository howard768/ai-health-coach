"""merge onboarding_complete head with ml pipeline head

Revision ID: b384bb88217f
Revises: f3a1d8c92e05, f7b3d2e1a456
Create Date: 2026-04-16 14:25:57.346578

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b384bb88217f'
down_revision: Union[str, Sequence[str], None] = ('f3a1d8c92e05', 'f7b3d2e1a456')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
