"""baseline existing schema

Revision ID: bc5a66367a8f
Revises:
Create Date: 2026-07-01 10:33:59.419717

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bc5a66367a8f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'page_content',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('page', sa.String(length=30), nullable=False),
        sa.Column('section', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('page', 'section', name='uq_page_section'),
    )

    op.create_table(
        'specimen_category',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('image', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.UniqueConstraint('name'),
    )

    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('password_hash', sa.String(length=200), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )
    op.create_index('ix_user_role', 'user', ['role'], unique=False)

    op.create_table(
        'specimen',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('specimen_number', sa.String(length=50), nullable=False),
        sa.Column('chinese_name', sa.String(length=100), nullable=True),
        sa.Column('latin_name', sa.String(length=200), nullable=False),
        sa.Column('alias', sa.Text(), nullable=True),
        sa.Column('phylum', sa.String(length=50), nullable=True),
        sa.Column('class_name', sa.String(length=50), nullable=True),
        sa.Column('order', sa.String(length=50), nullable=True),
        sa.Column('family', sa.String(length=50), nullable=True),
        sa.Column('genus', sa.String(length=50), nullable=True),
        sa.Column('species', sa.String(length=50), nullable=True),
        sa.Column('collector', sa.String(length=50), nullable=True),
        sa.Column('collect_time', sa.DateTime(), nullable=False),
        sa.Column('collect_location', sa.String(length=255), nullable=True),
        sa.Column('longitude', sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column('appraiser', sa.String(length=50), nullable=True),
        sa.Column('appraisal_time', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('other_info', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['specimen_category.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('specimen_number'),
    )
    op.create_index('fk_specimen_category', 'specimen', ['category_id'], unique=False)
    op.create_index('ix_specimen_chinese_name', 'specimen', ['chinese_name'], unique=False)
    op.create_index('ix_specimen_collect_time', 'specimen', ['collect_time'], unique=False)
    op.create_index('ix_specimen_specimen_number', 'specimen', ['specimen_number'], unique=False)

    op.create_table(
        'specimen_image',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('specimen_id', sa.Integer(), nullable=False),
        sa.Column('image_path', sa.String(length=255), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['specimen_id'], ['specimen.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_specimen_image_specimen_id', 'specimen_image', ['specimen_id'], unique=False)


def downgrade():
    op.drop_index('ix_specimen_image_specimen_id', table_name='specimen_image')
    op.drop_table('specimen_image')

    op.drop_index('ix_specimen_specimen_number', table_name='specimen')
    op.drop_index('ix_specimen_collect_time', table_name='specimen')
    op.drop_index('ix_specimen_chinese_name', table_name='specimen')
    op.drop_index('fk_specimen_category', table_name='specimen')
    op.drop_table('specimen')

    op.drop_index('ix_user_role', table_name='user')
    op.drop_table('user')

    op.drop_table('specimen_category')
    op.drop_table('page_content')
