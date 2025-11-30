from app import create_app
from extensions import db
from models.user import User

# 可自定义
USERNAME = "admin"
PASSWORD = "superpassword123"

app = create_app()

with app.app_context():
    u = User.query.filter_by(username=USERNAME).first()
    if not u:
        u = User(username=USERNAME)
        u.set_password(PASSWORD)
        # 如果你的模型是单字段：u.role = "admin"
        # 如果是多角色数组：u.roles = ["admin"]
        u.role = "admin"
        u.status = True
        db.session.add(u)
        db.session.commit()
        print(f"✅ 管理员创建成功：{USERNAME} / {PASSWORD}")
    else:
        print(f"ℹ️ 用户已存在：{USERNAME}")
