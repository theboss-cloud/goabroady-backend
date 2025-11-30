# models/application.py
from datetime import datetime
from extensions import db

STAGES = [
    "ai_intent",        # AI意向沟通
    "service_confirm",  # 确认全程/自助
    "docs",             # 材料准备
    "submit",           # 递交申请
    "admission_wait",   # 等待录取
    "visa",             # 签证
    "pre_departure"     # 出国前指导
]

class Application(db.Model):
    __tablename__ = "applications"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    program_id = db.Column(db.Integer, db.ForeignKey("programs.id"), nullable=False, index=True)
    current_stage = db.Column(db.String(32), default="ai_intent", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ApplicationStage(db.Model):
    __tablename__ = "application_stages"
    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, index=True)
    stage = db.Column(db.String(32), nullable=False, index=True)
    status = db.Column(db.String(16), default="active")  # active | done
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class Material(db.Model):
    __tablename__ = "materials"
    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, index=True)
    type = db.Column(db.String(40), nullable=False)  # transcript/cv/ps/...
    file_url = db.Column(db.String(500))
    status = db.Column(db.String(16), default="missing")  # missing | pending | approved
    due_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
