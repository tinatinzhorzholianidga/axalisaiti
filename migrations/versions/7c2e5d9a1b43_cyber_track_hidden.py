"""cyber_tracks.is_hidden: hide a track from visitors without deleting it

Revision ID: 7c2e5d9a1b43
Revises: 0100128f7b56
Create Date: 2026-09-23 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c2e5d9a1b43'
down_revision = '0100128f7b56'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'cyber_tracks',
        sa.Column('is_hidden', sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade():
    op.drop_column('cyber_tracks', 'is_hidden')
