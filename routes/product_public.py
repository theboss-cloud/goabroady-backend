# routes/product_public.py
from flask import Blueprint, request, jsonify
from sqlalchemy import or_, and_, func
from extensions import db
from models.product import Product

public_product_bp = Blueprint("product_public", __name__, url_prefix="/api")

def _qstr_list(param: str) -> list[str]:
    v = request.args.getlist(param)
    if not v:
        raw = request.args.get(param)
        if raw:
            v = [s.strip() for s in raw.split(",") if s.strip()]
    return v

@public_product_bp.get("/products")
def list_products():
    # 分页
    page = max(int(request.args.get("page", 1)), 1)
    size = min(max(int(request.args.get("size", 24)), 1), 100)

    q = Product.query.filter(Product.is_published.is_(True))

    # 关键词（标题/摘要）
    kw = (request.args.get("q") or "").strip()
    if kw:
        like = f"%{kw}%"
        q = q.filter(or_(Product.title.ilike(like),
                         Product.summary.ilike(like)))

    # 分类/交付方式
    categories = _qstr_list("category")
    deliveries = _qstr_list("delivery")
    if categories:
        q = q.filter(Product.category.in_(categories))
    if deliveries:
        q = q.filter(Product.delivery.in_(deliveries))

    # 价格/时长
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    if min_price:
        q = q.filter(Product.price.isnot(None), Product.price >= min_price)
    if max_price:
        q = q.filter(Product.price.isnot(None), Product.price <= max_price)

    min_weeks = request.args.get("min_weeks")
    max_weeks = request.args.get("max_weeks")
    if min_weeks:
        q = q.filter(Product.duration_weeks.isnot(None), Product.duration_weeks >= min_weeks)
    if max_weeks:
        q = q.filter(Product.duration_weeks.isnot(None), Product.duration_weeks <= max_weeks)

    # 排序（最新优先）
    q = q.order_by(Product.created_at.desc(), Product.id.desc())

    # 分页查询
    items = q.limit(size + 1).offset((page - 1) * size).all()
    has_more = len(items) > size
    items = items[:size]

    # 列表项：沿用 to_dict()，并补充封面与原价（不影响旧前端）
    def _f(v):
        try:
            return float(v) if v is not None else None
        except Exception:
            return None

    data = []
    for it in items:
        d = it.to_dict()
        d.update({
            "cover_image": it.cover_image,
            "hero_image_url": it.hero_image_url,
            "original_price": _f(it.original_price),
        })
        data.append(d)

    return jsonify({"items": data, "has_more": has_more, "page": page, "size": size})

@public_product_bp.get("/products/facets")
def product_facets():
    base = Product.query.filter(Product.is_published.is_(True))

    # 与列表一致的过滤
    kw = (request.args.get("q") or "").strip()
    if kw:
        like = f"%{kw}%"
        base = base.filter(or_(Product.title.ilike(like),
                               Product.summary.ilike(like)))
    categories = _qstr_list("category")
    deliveries = _qstr_list("delivery")
    if categories:
        base = base.filter(Product.category.in_(categories))
    if deliveries:
        base = base.filter(Product.delivery.in_(deliveries))
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    if min_price:
        base = base.filter(Product.price.isnot(None), Product.price >= min_price)
    if max_price:
        base = base.filter(Product.price.isnot(None), Product.price <= max_price)
    min_weeks = request.args.get("min_weeks")
    max_weeks = request.args.get("max_weeks")
    if min_weeks:
        base = base.filter(Product.duration_weeks.isnot(None), Product.duration_weeks >= min_weeks)
    if max_weeks:
        base = base.filter(Product.duration_weeks.isnot(None), Product.duration_weeks <= max_weeks)

    # category / delivery 计数
    subq = base.subquery()
    cat_rows = (
        db.session.query(Product.category, func.count(Product.id))
        .select_from(subq)
        .group_by(Product.category)
        .all()
    )
    del_rows = (
        db.session.query(Product.delivery, func.count(Product.id))
        .select_from(subq)
        .group_by(Product.delivery)
        .all()
    )

    # tags 聚合
    tag_counts = {}
    for (tags,) in db.session.query(Product.tags).select_from(subq).all():
        if not tags:
            continue
        for t in tags:
            if not t:
                continue
            tag_counts[t] = tag_counts.get(t, 0) + 1

    return jsonify({
        "category": [{"value": c or "—", "count": int(n)} for c, n in cat_rows],
        "delivery": [{"value": d or "—", "count": int(n)} for d, n in del_rows],
        "tags": [{"value": k, "count": v} for k, v in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))],
    })

@public_product_bp.get("/products/<slug_or_id>")
def product_detail(slug_or_id):
    """
    详情接口：返回 to_public_dict()（包含图集、卖点、包含/不含、流程、FAQ、plans 等）
    - 支持数字ID或 slug
    - 仅返回已发布 is_published=True
    """
    item = None
    if slug_or_id.isdigit():
        item = Product.query.get(int(slug_or_id))
    if not item:
        item = Product.query.filter_by(slug=slug_or_id, is_published=True).first()
    if not item or not item.is_published:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"success": True, "data": item.to_public_dict()})
