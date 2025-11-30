# models/product.py
from datetime import datetime
from extensions import db

# 说明：
# - 保留原有字段与 to_dict()，避免影响已上线的列表/旧接口。
# - 新增一组“详情页”字段 + to_public_dict()，前端 ProductDetail.vue 直接可用。
# - JSON 字段可存 list 或以换行/分号分隔的字符串；序列化时自动归一为 list/dict。

class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    summary = db.Column(db.Text, nullable=True)

    category = db.Column(db.String(50), index=True)        # 例如：咨询/文书/评估…
    delivery = db.Column(db.String(20), index=True)        # online / onsite / hybrid
    tags = db.Column(db.JSON, nullable=True)               # ["大数据","翻译",...]

    price = db.Column(db.Numeric(10, 2), nullable=True)    # 单价，可为 None=面议
    duration_weeks = db.Column(db.Integer, nullable=True)  # 时长（周）
    duration_text  = db.Column(db.String(50), nullable=True)  # 可读的时长文案

    is_published = db.Column(db.Boolean, nullable=False, default=True, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ===== 新增：详情页相关字段 =====
    original_price   = db.Column(db.Numeric(10, 2), nullable=True)  # 原价（可选）
    cover_image      = db.Column(db.String(512), nullable=True)
    hero_image_url   = db.Column(db.String(512), nullable=True)
    gallery_images   = db.Column(db.JSON, nullable=True)             # [url, url, ...]

    highlights       = db.Column(db.JSON, nullable=True)             # 要点（list 或分隔字符串）
    includes         = db.Column(db.JSON, nullable=True)             # 你将获得
    excludes         = db.Column(db.JSON, nullable=True)             # 不包含
    steps            = db.Column(db.JSON, nullable=True)             # [{title, desc}]
    faqs             = db.Column(db.JSON, nullable=True)             # [{q, a}]
    plans            = db.Column(db.JSON, nullable=True)             # [{id, name, desc, price}]
    detail_html      = db.Column(db.Text, nullable=True)             # 富文本 HTML
    service_promise  = db.Column(db.String(256), nullable=True)      # 一句话承诺

    # 可选的联合索引：按发布状态与分类查询更快
    __table_args__ = (
        db.Index('idx_products_published_category', 'is_published', 'category'),
    )

    # -------- 工具：安全 float 转换 --------
    @staticmethod
    def _f(v):
        try:
            return float(v) if v is not None else None
        except Exception:
            return None

    # -------- 工具：把 JSON/字符串 统一转 list[str] --------
    @staticmethod
    def _to_list(v):
        if not v:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            # 支持换行 / 分号中英文分隔
            parts = []
            for line in v.splitlines():
                for seg in line.replace('；', ';').split(';'):
                    seg = seg.strip()
                    if seg:
                        parts.append(seg)
            return parts
        return []

    # -------- 工具：steps / faqs 归一 --------
    @staticmethod
    def _to_steps(v):
        out = []
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict):
                    title = (x.get('title') or x.get('t') or x.get('name') or '').strip()
                    desc  = (x.get('desc')  or x.get('d') or '').strip()
                    if title:
                        out.append({'title': title, 'desc': desc})
        return out

    @staticmethod
    def _to_faqs(v):
        out = []
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict):
                    q = (x.get('q') or x.get('question') or '').strip()
                    a = (x.get('a') or x.get('answer') or '').strip()
                    if q:
                        out.append({'q': q, 'a': a})
        return out

    # -------- 工具：图集合并去重（保持顺序） --------
    @staticmethod
    def _merge_images(cover, hero, gallery):
        imgs = []
        def push(u):
            if u and u not in imgs:
                imgs.append(u)
        if isinstance(gallery, list):
            for u in gallery:
                push(str(u).strip())
        push(cover)
        push(hero)
        # 优先保证封面在第一位
        if cover and imgs and imgs[0] != cover:
            try:
                imgs.remove(cover)
            except ValueError:
                pass
            imgs.insert(0, cover)
        return [u for u in imgs if u]

    # ===== 列表/旧接口：保持不变 =====
    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "summary": self.summary,
            "category": self.category,
            "delivery": self.delivery,
            "tags": self.tags or [],
            "price": self._f(self.price),
            "duration_weeks": self.duration_weeks,
            "duration_text": self.duration_text,
            "is_published": self.is_published,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    # ===== 详情页序列化：给 /api/products/<slug> 用 =====
    def to_public_dict(self):
        imgs = self._merge_images(self.cover_image, self.hero_image_url, self.gallery_images or [])
        return {
            "slug": self.slug,
            "title": self.title,
            "summary": self.summary,
            "category": self.category,
            "delivery": self.delivery,

            "duration_text": self.duration_text,
            "duration_weeks": self.duration_weeks,

            "price": self._f(self.price),
            "original_price": self._f(self.original_price),

            "cover_image": self.cover_image,
            "hero_image_url": self.hero_image_url,
            "gallery_images": imgs,

            "tags": self._to_list(self.tags),

            "highlights": self._to_list(self.highlights),
            "includes": self._to_list(self.includes),
            "excludes": self._to_list(self.excludes),

            "steps": self._to_steps(self.steps),
            "faqs": self._to_faqs(self.faqs),
            "plans": self.plans or [],

            "detail_html": self.detail_html,
            "service_promise": self.service_promise,

            "is_published": self.is_published,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
