"""add anon_session_id + unique constraint

Revision ID: add_anon_session_id_uc
Revises: 246be9af194f
Create Date: 2025-09-17 05:xx:xx.xxx
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_anon_session_id_uc'     # ← 可保留自动生成的 ID，这里占位
down_revision = '246be9af194f'
branch_labels = None
depends_on = None


def upgrade():
    # --- 1) 添加列（先允许为空，避免老数据报错）
    op.add_column('assessment_results', sa.Column('anon_session_id', sa.String(length=64), nullable=True))
    op.create_index('ix_assessment_results_anon_session_id', 'assessment_results', ['anon_session_id'], unique=False)

    # --- 2) 回填历史数据（把空值填成 'legacy-<id>'，保证不为空、且不与新 UUID 冲突）
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE assessment_results
        SET anon_session_id = COALESCE(anon_session_id, 'legacy-' || id)
    """))

    # --- 3) 将列改为非空 + 增加 (user_id, anon_session_id) 唯一约束
    # 使用 batch_alter_table 兼容 SQLite
    with op.batch_alter_table('assessment_results') as batch_op:
        batch_op.alter_column('anon_session_id', existing_type=sa.String(length=64), nullable=False)
        batch_op.create_unique_constraint('uq_user_anon', ['user_id', 'anon_session_id'])


def downgrade():
    # 逆向：先删唯一约束与索引，再删列
    with op.batch_alter_table('assessment_results') as batch_op:
        batch_op.drop_constraint('uq_user_anon', type_='unique')

    op.drop_index('ix_assessment_results_anon_session_id', table_name='assessment_results')
    op.drop_column('assessment_results', 'anon_session_id')
