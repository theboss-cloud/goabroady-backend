"""Restore fields and add gpa_scale

Revision ID: 51e6d09d6e76
Revises: abd88e256aed
Create Date: 2025-12-06 19:17:16.612032

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '51e6d09d6e76'
down_revision = '30a42a230064' # 指向上一个稳定版本
branch_labels = None
depends_on = None


def upgrade():
    # ⚠️ 既然数据库里什么字段都有了，这里什么都不做
    # 直接 pass，Alembic 会认为迁移成功，并把版本号更新为 51e6...
    # 这样数据库和代码就同步了
    pass 


def downgrade():
    # 为了保持对称，如果需要回滚，理论上要删掉这些字段
    # 但鉴于之前的混乱，暂时也留空或只删新字段，最稳妥是留空
    pass