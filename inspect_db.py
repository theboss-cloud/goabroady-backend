# backend/inspect_db.py
from app import create_app
from extensions import db
from sqlalchemy import inspect

app = create_app()

def check_schema():
    print("🔍 正在连接数据库检查表结构...\n")
    
    with app.app_context():
        # 获取数据库检查器
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        # --- 1. 检查 User 表 ---
        if "user" in tables:
            columns = [col['name'] for col in inspector.get_columns("user")]
            print(f"✅ User 表 (user) 存在，包含字段: {len(columns)} 个")
            print(f"   字段列表: {columns}")
            
            # 重点检查我们需要的字段
            missing = []
            for f in ['phone', 'email', 'avatar']:
                if f not in columns:
                    missing.append(f)
            
            if missing:
                print(f"   ❌ 严重警告：User 表缺少以下关键字段 -> {missing}")
                print("      (这就是为什么你存不进手机号/头像的原因！)")
            else:
                print("   ✨ 状态完美：User 表包含所有新字段 (phone, email, avatar)")
        else:
            print("❌ 错误：数据库中找不到 'user' 表！")

        print("-" * 30)

        # --- 2. 检查 档案表 ---
        # 你的表名定义是 "student_profiles"
        target_table = "student_profiles"
        if target_table in tables:
            columns = [col['name'] for col in inspector.get_columns(target_table)]
            print(f"✅ 档案表 ({target_table}) 存在，包含字段: {len(columns)} 个")
            print(f"   字段列表: {columns}")
            
            if 'gpa_scale' not in columns:
                print("   ❌ 警告：缺少 'gpa_scale' 字段 (导致 GPA 学制无法保存)")
            else:
                print("   ✨ 状态完美：包含 'gpa_scale' 字段")
        else:
            print(f"❌ 错误：数据库中找不到 '{target_table}' 表！")

if __name__ == '__main__':
    check_schema()