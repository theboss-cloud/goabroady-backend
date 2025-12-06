# backend/fix_missing_columns.py
from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()

def fix_db():
    print("🔧 正在检查并修复数据库字段...")
    
    with app.app_context():
        # 获取数据库连接
        with db.engine.connect() as conn:
            transaction = conn.begin()
            try:
                # --- 1. 修复 User 表 ---
                # 尝试添加 email
                try:
                    print("👉 尝试添加 user.email...")
                    conn.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(120)"))
                    print("   ✅ 成功添加 email")
                except Exception as e:
                    if "duplicate column" in str(e).lower():
                        print("   ℹ️ email 已存在 (跳过)")
                    else:
                        print(f"   ⚠️ 提示: {e}")

                # 尝试添加 avatar
                try:
                    print("👉 尝试添加 user.avatar...")
                    conn.execute(text("ALTER TABLE user ADD COLUMN avatar VARCHAR(255)"))
                    print("   ✅ 成功添加 avatar")
                except Exception as e:
                    if "duplicate column" in str(e).lower():
                        print("   ℹ️ avatar 已存在 (跳过)")
                    else:
                        print(f"   ⚠️ 提示: {e}")

                # 尝试添加 phone (以此类推，防止之前没加上)
                try:
                    print("👉 尝试添加 user.phone...")
                    conn.execute(text("ALTER TABLE user ADD COLUMN phone VARCHAR(20)"))
                    print("   ✅ 成功添加 phone")
                except Exception as e:
                    if "duplicate column" in str(e).lower():
                        print("   ℹ️ phone 已存在 (跳过)")
                    else:
                        print(f"   ⚠️ 提示: {e}")

                # --- 2. 修复 StudentProfile 表 (顺手检查一下) ---
                try:
                    print("👉 尝试添加 student_profiles.gpa_scale...")
                    conn.execute(text("ALTER TABLE student_profiles ADD COLUMN gpa_scale VARCHAR(10)"))
                    print("   ✅ 成功添加 gpa_scale")
                except Exception:
                    print("   ℹ️ gpa_scale 已存在 (跳过)")

                # 提交更改
                transaction.commit()
                print("\n🎉 数据库结构修复完成！现在代码和数据库一致了。")
                
            except Exception as e:
                transaction.rollback()
                print(f"\n❌ 发生严重错误，已回滚: {e}")

if __name__ == '__main__':
    fix_db()