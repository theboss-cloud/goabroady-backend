# migration.py  —— 仅用于生成/应用迁移
import os
from flask import Flask
from flask_migrate import Migrate, init as mig_init, migrate as mig_migrate, upgrade as mig_upgrade
from dotenv import load_dotenv

# 你已有的配置/扩展/模型
from config import Config           # backend/config.py
from extensions import db           # backend/extensions.py

# ⚠️ 很重要：把所有模型导入进来，让 SQLAlchemy 知道表结构
# 根据你的文件实际路径调整：
from models.user import User
from models.program import Program, ProgramRequirement
from models.student_profile import StudentProfile

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

migrate = Migrate(app, db)

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")

with app.app_context():
    # 1) 初始化 migrations 目录（不存在才创建）
    if not os.path.exists(MIGRATIONS_DIR):
        print("==> 初始化 migrations 目录")
        mig_init(directory=MIGRATIONS_DIR)
    else:
        print("==> migrations 已存在，跳过 init")

    # 2) 生成迁移脚本
    print("==> 生成迁移脚本...")
    mig_migrate(message="init tables: programs, requirements, student_profiles", directory=MIGRATIONS_DIR)

    # 3) 应用迁移
    print("==> 应用迁移到数据库...")
    mig_upgrade(directory=MIGRATIONS_DIR)

    print("✅ 迁移完成")
