from datetime import datetime
from extensions import db

class StudentProfile(db.Model):
    __tablename__ = "student_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)

    # 学术与语言
    gpa = db.Column(db.Float)
    # 🔥 关键修复：把这行加回来！
    gpa_scale = db.Column(db.String(10), default='4.0') 
    
    ielts = db.Column(db.Float)
    toefl = db.Column(db.Float)
    gre = db.Column(db.Integer)
    english_test = db.Column(db.String(32))
    english_score = db.Column(db.Float)

    # 学业/背景
    major = db.Column(db.String(120))
    grad_year = db.Column(db.Integer)
    work_years = db.Column(db.Float)

    # 意向与预算
    country_pref = db.Column(db.String(80))
    target_country = db.Column(db.String(80))
    budget = db.Column(db.Integer)
    budget_min = db.Column(db.Integer)
    budget_max = db.Column(db.Integer)

    # 服务类型
    service_type = db.Column(db.String(8), default="full", nullable=False, server_default="full")

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.Index("idx_student_target_country", "target_country"),
        db.Index("idx_student_service_type", "service_type"),
    )