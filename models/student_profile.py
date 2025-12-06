from datetime import datetime
from extensions import db

class StudentProfile(db.Model):
    __tablename__ = "student_profiles"
    id = db.Column(db.Integer, primary_key=True)
    # 确认你的用户表名是 'user' 还是 'users'，根据你之前的 models/user.py 这里应该是 'user.id'
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)

    # === 学术与语言 (合并版) ===
    gpa = db.Column(db.Float)
    # 🔥 新增字段: GPA学制 (4.0/5.0/100)
    gpa_scale = db.Column(db.String(10), default='4.0') 
    
    # ⬇️ 旧字段 (加回来，防止报错)
    ielts = db.Column(db.Float)
    toefl = db.Column(db.Float)
    gre = db.Column(db.Integer)
    
    # ⬇️ 新字段 (新版下拉菜单用这两个)
    english_test = db.Column(db.String(32))        # 'IELTS' | 'TOEFL' | 'OTHER'
    english_score = db.Column(db.Float)            # 统一的分数入口

    # === 学业/背景 ===
    major = db.Column(db.String(120))
    grad_year = db.Column(db.Integer)
    work_years = db.Column(db.Float)

    # === 意向与预算 ===
    country_pref = db.Column(db.String(80))        # 旧字段
    target_country = db.Column(db.String(80))      # 新字段
    
    budget = db.Column(db.Integer)                 # 通用
    budget_min = db.Column(db.Integer)             # 旧字段
    budget_max = db.Column(db.Integer)             # 旧字段

    # === 服务类型 ===
    # 之前被删了，现在加回来。注意：如果有存量数据，nullable=False 可能会在迁移时报警，建议暂时设为 True 或给 server_default
    service_type = db.Column(db.String(8), default="full", nullable=False, server_default="full")

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 保留索引
    __table_args__ = (
        db.Index("idx_student_target_country", "target_country"),
        db.Index("idx_student_service_type", "service_type"),
    )