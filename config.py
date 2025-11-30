# config.py
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # .../backend
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)  # 确保目录存在

DB_PATH = os.path.join(INSTANCE_DIR, "your_db.sqlite3")

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    # 注意：绝对路径 + 3 个斜杠
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        f"sqlite:///{DB_PATH.replace(os.sep, '/')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt")
    JSON_AS_ASCII = False
