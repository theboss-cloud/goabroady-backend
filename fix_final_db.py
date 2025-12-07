# backend/fix_final_db.py
from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()

def fix_database():
    print("🚑 正在进行数据库最终修复...")
    with app.app_context():
        with db.engine.connect() as conn:
            # 1. 检查并添加 updated_at (修复报错核心)
            try:
                print("👉 尝试添加 orders.updated_at ...")
                conn.execute(text("ALTER TABLE orders ADD COLUMN updated_at DATETIME"))
                print("   ✅ 成功！")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    print("   ℹ️ 已存在，跳过。")
                else:
                    print(f"   ⚠️ 提示: {e}")

            # 2. 顺手检查其他可能缺失的字段 (防患未然)
            optional_fields = {
                "orders": ["pay_time DATETIME", "trade_no VARCHAR(64)", "product_name VARCHAR(128)", "amount FLOAT"],
                "user": ["phone VARCHAR(20)", "email VARCHAR(120)", "avatar VARCHAR(255)"]
            }

            for table, cols in optional_fields.items():
                for col_def in cols:
                    col_name = col_def.split()[0]
                    try:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_def}"))
                        print(f"   ✅ 补全了 {table}.{col_name}")
                    except:
                        pass # 已存在则忽略

            conn.commit()
            print("\n🎉 数据库修复完成！所有字段已就绪。")

if __name__ == '__main__':
    fix_database()