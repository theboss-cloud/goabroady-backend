"""add products table"""

from alembic import op
import sqlalchemy as sa

# 你的日志里显示的是这个链条：
revision = 'ad70c87d2fcb'
down_revision = 'add_anon_session_id_uc'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('slug', sa.String(120), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('delivery', sa.String(20), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),  # ✅ 通用 JSON
        sa.Column('price', sa.Numeric(10, 2), nullable=True),
        sa.Column('duration_weeks', sa.Integer(), nullable=True),
        sa.Column('duration_text', sa.String(50), nullable=True),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    # 索引（slug 唯一；delivery、is_published 常用过滤）
    op.create_index('ix_products_slug', 'products', ['slug'], unique=True)
    op.create_index('ix_products_delivery', 'products', ['delivery'], unique=False)
    op.create_index('ix_products_is_published', 'products', ['is_published'], unique=False)


def downgrade():
    op.drop_index('ix_products_is_published', table_name='products')
    op.drop_index('ix_products_delivery', table_name='products')
    op.drop_index('ix_products_slug', table_name='products')
    op.drop_table('products')
