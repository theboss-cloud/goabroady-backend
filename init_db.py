# init_db.py
from app import app, db
# 确保把所有模型都导入进来（非常重要，否则不会创建对应表）
from models.user import User
from models.student_profile import StudentProfile
from models.program import Program
from models.application import Application, ApplicationStage, Material

# 如果还有其它模型，也一并 import

if __name__ == "__main__":
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        print("Done.")
