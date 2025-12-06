# backend/force_fix_db.py
from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()

def fix_version():
    print("🔧 正在强制修复数据库版本号...")
    with app.app_context():
        try:
            # 1. 强制把版本号改回 '30a42a230064' (你那个稳定的版本)
            # 这样 Alembic 再次启动时，就会以为自己在一个健康的老版本，而不会去找那个不存在的 bad file
            sql = text("UPDATE alembic_version SET version_num = '30a42a230064'")
            db.session.execute(sql)
            db.session.commit()
            print("✅ 成功！数据库版本号已重置为: 30a42a230064")
        except Exception as e:
            print(f"❌ 修复失败: {e}")
            print("如果是 'no such table: alembic_version'，说明你还没初始化过迁移，可以跳过此步。")

if __name__ == '__main__':
    fix_version()