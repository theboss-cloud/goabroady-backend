# models/program.py
from datetime import datetime
from extensions import db

class Program(db.Model):
    __tablename__ = "programs"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)

    # 英文/默认
    country = db.Column(db.String(80))
    city = db.Column(db.String(80))
    university = db.Column(db.String(160))

    # 中文显示用（可空）
    country_cn = db.Column(db.String(80))
    city_cn = db.Column(db.String(80))
    university_cn = db.Column(db.String(160))

    degree_level = db.Column(db.String(80))
    discipline = db.Column(db.String(120))
    duration = db.Column(db.String(80))
    start_terms = db.Column(db.String(120))
    tuition = db.Column(db.String(80))
    credits = db.Column(db.String(40))

    # 图片
    cover_image = db.Column(db.String(500))
    hero_image_url = db.Column(db.String(500))
    intro_image_url = db.Column(db.String(500))
    overview_image = db.Column(db.String(500))  # 新增：概览右侧图

    # 内容
    summary = db.Column(db.Text)
    overview_brief = db.Column(db.Text)   # 新增：概览单段文本（中文）
    overview_md = db.Column(db.Text)
    intro_md = db.Column(db.Text)
    advantages_md = db.Column(db.Text)    # 兼容老字段
    highlights_md = db.Column(db.Text)    # 新增：项目亮点
    key_dates_md = db.Column(db.Text)
    timeline_md = db.Column(db.Text)
    costs_md = db.Column(db.Text)
    scholarships_md = db.Column(db.Text)
    savings_md = db.Column(db.Text)
    destination_md = db.Column(db.Text)
    faq_md = db.Column(db.Text)

    # 画廊（JSON 文本）
    gallery_images = db.Column(db.JSON)

    status = db.Column(db.String(20), default="draft")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requirements = db.relationship("ProgramRequirement", backref="program", cascade="all, delete-orphan")

    def to_dict(self, with_requirements=True):
        data = {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,

            "country": self.country, "city": self.city, "university": self.university,
            "country_cn": self.country_cn, "city_cn": self.city_cn, "university_cn": self.university_cn,

            "degree_level": self.degree_level,
            "discipline": self.discipline,
            "duration": self.duration,
            "start_terms": self.start_terms,
            "tuition": self.tuition,
            "credits": self.credits,

            "cover_image": self.cover_image,
            "hero_image_url": self.hero_image_url,
            "intro_image_url": self.intro_image_url,
            "overview_image": self.overview_image,

            "summary": self.summary,
            "overview_brief": self.overview_brief,
            "overview_md": self.overview_md,
            "intro_md": self.intro_md,
            "advantages_md": self.advantages_md,
            "highlights_md": self.highlights_md,
            "key_dates_md": self.key_dates_md,
            "timeline_md": self.timeline_md,
            "costs_md": self.costs_md,
            "scholarships_md": self.scholarships_md,
            "savings_md": self.savings_md,
            "destination_md": self.destination_md,
            "faq_md": self.faq_md,

            "gallery_images": self.gallery_images,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if with_requirements:
            data["requirements"] = [r.to_dict() for r in self.requirements]
        return data


class ProgramRequirement(db.Model):
    __tablename__ = "program_requirements"
    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey("programs.id"), nullable=False)
    req_type = db.Column(db.String(40))
    min_value = db.Column(db.String(40))
    note = db.Column(db.String(200))

    def to_dict(self):
        return {
            "id": self.id,
            "req_type": self.req_type,
            "min_value": self.min_value,
            "note": self.note
        }
