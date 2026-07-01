"""standardize schema fields

Revision ID: 5a5921108376
Revises: bc5a66367a8f
Create Date: 2026-07-01 10:33:59.474837

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5a5921108376'
down_revision = 'bc5a66367a8f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('page_content', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.execute(
        """
        UPDATE page_content
        SET created_at = COALESCE(updated_at, NOW())
        WHERE created_at IS NULL
        """
    )
    op.alter_column(
        'page_content',
        'created_at',
        existing_type=sa.DateTime(),
        nullable=False,
    )

    op.execute(
        """
        UPDATE specimen_category
        SET code = CONCAT('CAT', id)
        WHERE code IS NULL OR TRIM(code) = ''
        """
    )
    op.alter_column(
        'specimen_category',
        'code',
        existing_type=sa.String(length=10),
        nullable=False,
    )

    op.create_index('ix_specimen_latin_name', 'specimen', ['latin_name'], unique=False)
    op.alter_column(
        'specimen',
        'longitude',
        existing_type=sa.Numeric(precision=10, scale=7),
        type_=sa.Numeric(precision=10, scale=6),
        existing_nullable=True,
    )
    op.alter_column(
        'specimen',
        'latitude',
        existing_type=sa.Numeric(precision=9, scale=6),
        type_=sa.Numeric(precision=10, scale=6),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        'specimen',
        'latitude',
        existing_type=sa.Numeric(precision=10, scale=6),
        type_=sa.Numeric(precision=9, scale=6),
        existing_nullable=True,
    )
    op.alter_column(
        'specimen',
        'longitude',
        existing_type=sa.Numeric(precision=10, scale=6),
        type_=sa.Numeric(precision=10, scale=7),
        existing_nullable=True,
    )
    op.drop_index('ix_specimen_latin_name', table_name='specimen')

    op.alter_column(
        'specimen_category',
        'code',
        existing_type=sa.String(length=10),
        nullable=True,
    )

    op.drop_column('page_content', 'created_at')
