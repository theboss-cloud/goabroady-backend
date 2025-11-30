# models/assessment_result.py
from extensions import db
from datetime import datetime

class AssessmentResult(db.Model):
    __tablename__ = "assessment_results"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    # 👇 新增：匿名会话ID，用于归档幂等
    anon_session_id = db.Column(db.String(64), nullable=False, index=True)

    # 原始入参/结果
    input_payload = db.Column(db.JSON)
    results = db.Column(db.JSON)

    # Top 项目摘要
    top_program_id = db.Column(db.Integer)
    top_program_title = db.Column(db.String(255))
    top_university = db.Column(db.String(255))
    top_country = db.Column(db.String(64))
    top_city = db.Column(db.String(64))

    # 概率与解释
    prob = db.Column(db.Float)
    prob_low = db.Column(db.Float)
    prob_high = db.Column(db.Float)
    risks = db.Column(db.JSON)
    improvements = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        # user_id + anon_session_id 保证同一匿名会话只归档一次
        db.UniqueConstraint('user_id', 'anon_session_id', name='uq_user_anon'),
    )
