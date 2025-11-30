# routes/program_public.py
from flask import Blueprint, jsonify, request
from sqlalchemy import or_
from models.program import Program
import json

public_program_bp = Blueprint("public_program", __name__, url_prefix="/api")

# ------- helpers -------

def _as_list_gallery(g):
    if g is None:
        return []
    if isinstance(g, list):
        return g
    if isinstance(g, str):
        s2 = g.strip()
        if not s2:
            return []
        try:
            val = json.loads(s2)
            if isinstance(val, list):
                return val
            return []
        except Exception:
            return [x.strip() for x in s2.split(",") if x.strip()]
    return []

def _nz(v, default=""):
    if v is None:
        return default
    if isinstance(v, str) and v.strip().lower() == "null":
        return default
    return v

def _media_url(slug: str, kind: str) -> str:
    """统一返回后端图片代理路径（由 routes/image_cache.py 处理并缓存）"""
    return f"/media/programs/{slug}/{kind}.jpg"

def _cover_of(p: Program) -> str:
    """
    列表卡片的封面图：
    - 若任一图片字段有值，则返回 /media/programs/<slug>/cover.jpg（后端会按数据库里的原始 URL 取回 & 缓存）
    - 若都为空，返回空字符串（前端会用 onError 兜底到 /images/placeholder.jpg）
    """
    has_any = any([
        _nz(p.cover_image),
        _nz(p.hero_image_url),
        _nz(p.intro_image_url),
        _nz(p.overview_image),
    ])
    return _media_url(p.slug, "cover") if has_any else ""

def _img_or_media(p: Program, kind: str, source: str) -> str:
    """
    详情用的各类图片字段：
    - 如果数据库里该类图片有值 -> 返回 /media/programs/<slug>/<kind>.jpg
    - 如果没有 -> 返回空字符串
    """
    return _media_url(p.slug, kind) if _nz(source) else ""

# ------- serializers -------

def _preview_card(p: Program) -> dict:
    return {
        "slug": p.slug,
        "title": _nz(p.title),
        "country": _nz(p.country),
        "discipline": _nz(p.discipline),
        "tuition": _nz(p.tuition),
        "start_terms": _nz(p.start_terms),
        # ✅ 统一走本地媒体代理，避免 https 混合内容/CORS
        "cover_image": _cover_of(p),
        "summary": _nz(p.summary),
        # （前端还有 hero_image_url 兜底时会用到，这里可一并提供）
        "hero_image_url": _img_or_media(p, "hero", p.hero_image_url),
    }

def _detail(p: Program) -> dict:
    return {
        "id": p.id,
        "slug": p.slug,
        "title": _nz(p.title),

        # 英文/默认
        "country": _nz(p.country),
        "city": _nz(p.city),
        "university": _nz(p.university),
        # 中文显示用
        "country_cn": _nz(p.country_cn),
        "city_cn": _nz(p.city_cn),
        "university_cn": _nz(p.university_cn),

        "degree_level": _nz(p.degree_level),
        "discipline": _nz(p.discipline),
        "duration": _nz(p.duration),
        "start_terms": _nz(p.start_terms),
        "tuition": _nz(p.tuition),
        "credits": _nz(p.credits),

        # ✅ 统一映射到本地代理路径（若源字段为空则给空字符串，前端有占位兜底）
        "cover_image": _cover_of(p),
        "hero_image_url": _img_or_media(p, "hero", p.hero_image_url),
        "intro_image_url": _img_or_media(p, "intro", p.intro_image_url),
        "overview_image": _img_or_media(p, "overview", p.overview_image),

        # 画廊保持原样（如果以后也要代理，可以新增 /media/programs/<slug>/gallery/.. 路由再统一映射）
        "gallery_images": _as_list_gallery(p.gallery_images),

        "summary": _nz(p.summary),
        "overview_brief": _nz(p.overview_brief),
        "overview_md": _nz(p.overview_md),
        "intro_md": _nz(p.intro_md),
        "advantages_md": _nz(p.advantages_md),
        "highlights_md": _nz(p.highlights_md),
        "key_dates_md": _nz(p.key_dates_md),
        "timeline_md": _nz(p.timeline_md),
        "costs_md": _nz(p.costs_md),
        "scholarships_md": _nz(p.scholarships_md),
        "savings_md": _nz(p.savings_md),
        "destination_md": _nz(p.destination_md),
        "faq_md": _nz(p.faq_md),

        "status": _nz(p.status, "draft"),
        "created_at": p.created_at.isoformat() if p.created_at else "",
        "updated_at": p.updated_at.isoformat() if p.updated_at else "",
        "requirements": [r.to_dict() for r in (p.requirements or [])],
    }

# ------- routes -------

@public_program_bp.get("/programs")
def get_public_programs():
    page = int(request.args.get("page", 1) or 1)
    size = int(request.args.get("size", 24) or 24)
    size = max(1, min(size, 60))

    q = (request.args.get("q") or "").strip()
    query = Program.query
    # 如需只展示发布的，打开下一行：
    # query = query.filter(Program.status == "published")

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Program.title.ilike(like),
                Program.country.ilike(like),
                Program.city.ilike(like),
                Program.university.ilike(like),
                Program.discipline.ilike(like),
            )
        )

    total = query.count()
    items = (
        query.order_by(Program.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return jsonify({
        "page": page,
        "size": size,
        "total": total,
        "items": [_preview_card(p) for p in items]
    })

@public_program_bp.get("/programs/<string:slug>")
def get_public_program_detail(slug: str):
    p = Program.query.filter_by(slug=slug).first()
    if not p:
        return jsonify({"msg": "Not Found"}), 404
    # 如需仅对外展示 published：
    # if p.status != "published": return jsonify({"msg":"Not Found"}), 404
    return jsonify(_detail(p)), 200
