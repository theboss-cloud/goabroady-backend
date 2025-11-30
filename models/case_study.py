from datetime import datetime
from extensions import db

class CaseStudy(db.Model):
    __tablename__ = "case_studies"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    student_alias = db.Column(db.String(80))     # 匿名名，如 “A同学”
    target_university = db.Column(db.String(160))
    target_program = db.Column(db.String(160))
    outcome = db.Column(db.String(80))           # Offer / Scholarship 等
    highlights = db.Column(db.Text)              # 富文本/要点
    cover_image = db.Column(db.String(200))
    tags = db.Column(db.String(200))             # 逗号分隔
    status = db.Column(db.String(20), default="draft")  # draft/published
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "student_alias": self.student_alias,
            "target_university": self.target_university, "target_program": self.target_program,
            "outcome": self.outcome, "highlights": self.highlights, "cover_image": self.cover_image,
            "tags": self.tags, "status": self.status, "order": self.order
        }
