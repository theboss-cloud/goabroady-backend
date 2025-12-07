# backend/fix_orders_db.py
from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()

def fix_orders_structure():
    print("🔧 正在升级 Orders 表结构...")
    with app.app_context():
        # 1. 检查表是否存在
        inspector = db.inspect(db.engine)
        if 'orders' not in inspector.get_table_names():
            print("❌ orders 表不存在，请先运行原来的建表逻辑。")
            return

        # 2. 获取现有列名
        columns = [col['name'] for col in inspector.get_columns('orders')]
        print(f"当前字段: {columns}")

        # 3. 逐个检查并添加缺失字段
        with db.engine.connect() as conn:
            # 添加 out_trade_no
            if 'out_trade_no' not in columns:
                print("➕ 添加 out_trade_no 字段...")
                conn.execute(text("ALTER TABLE orders ADD COLUMN out_trade_no VARCHAR(64)"))
            
            # 添加 trade_no
            if 'trade_no' not in columns:
                print("➕ 添加 trade_no 字段...")
                conn.execute(text("ALTER TABLE orders ADD COLUMN trade_no VARCHAR(64)"))

            # 添加 product_name
            if 'product_name' not in columns:
                print("➕ 添加 product_name 字段...")
                conn.execute(text("ALTER TABLE orders ADD COLUMN product_name VARCHAR(128)"))

            # 添加 amount (Float)
            if 'amount' not in columns:
                print("➕ 添加 amount 字段...")
                conn.execute(text("ALTER TABLE orders ADD COLUMN amount FLOAT"))

            # 添加 pay_time
            if 'pay_time' not in columns:
                print("➕ 添加 pay_time 字段...")
                conn.execute(text("ALTER TABLE orders ADD COLUMN pay_time DATETIME"))

            conn.commit()
            print("✅ 数据库结构升级完成！")

if __name__ == '__main__':
    fix_orders_structure()