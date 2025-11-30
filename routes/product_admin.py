# routes/product_admin.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from extensions import db
from models.product import Product

admin_product_bp = Blueprint("product_admin", __name__, url_prefix="/api/admin")


def _coerce_tags(v):
    """tags 既支持 ['A','B'] 也支持 'A,B'；None 时不更新。"""
    if v is None:
        return None
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return None


def _payload_to_model(m: Product, data: dict):
    # 仅当键存在时才更新，避免莫名其妙覆盖
    if "slug" in data:
        m.slug = (data.get("slug") or m.slug).strip()
    if "title" in data:
        m.title = (data.get("title") or m.title).strip()
    if "summary" in data:
        m.summary = data.get("summary", m.summary)
    if "category" in data:
        m.category = (data.get("category") or m.category or "").strip()
    if "delivery" in data:
        m.delivery = (data.get("delivery") or m.delivery or "").strip()
    if "price" in data:
        m.price = data.get("price", m.price)
    if "duration_weeks" in data:
        m.duration_weeks = data.get("duration_weeks", m.duration_weeks)
    if "duration_text" in data:
        m.duration_text = data.get("duration_text", m.duration_text)
    if "status" in data:
        # 你的模型里是 status（active/draft），不是 is_published
        m.status = (data.get("status") or m.status or "active").strip()
    if "tags" in data:
        t = _coerce_tags(data.get("tags"))
        if t is not None:
            m.tags = t


def _serialize(it: Product):
    # 你已有 to_dict() 就保持向后兼容；若某些字段新增也不怕。
    return it.to_dict() if hasattr(it, "to_dict") else {
        "id": it.id, "slug": it.slug, "title": it.title, "summary": it.summary,
        "category": it.category, "delivery": it.delivery, "tags": it.tags or [],
        "price": float(it.price) if it.price is not None else None,
        "duration_weeks": it.duration_weeks, "duration_text": it.duration_text,
        "status": getattr(it, "status", None)
    }


@admin_product_bp.get("/products")
@jwt_required()
def admin_list_products():
    q = Product.query

    # 搜索
    if request.args.get("q"):
        like = f"%{request.args['q']}%"
        q = q.filter(or_(Product.title.ilike(like),
                         Product.slug.ilike(like),
                         Product.summary.ilike(like)))

    # 兼容 ?status=active/draft；也兼容你历史的 ?published=1/0（映射为 active/draft）
    if request.args.get("status"):
        q = q.filter(Product.status == request.args.get("status"))
    elif request.args.get("published") in ("0", "1"):
        want_active = request.args.get("published") == "1"
        q = q.filter(Product.status == ("active" if want_active else "draft"))

    q = q.order_by(Product.created_at.desc(), Product.id.desc())

    page = max(int(request.args.get("page", 1)), 1)
    size = min(max(int(request.args.get("size", 24)), 1), 200)

    items = q.limit(size + 1).offset((page - 1) * size).all()
    has_more = len(items) > size
    items = items[:size]

    return jsonify({"items": [_serialize(it) for it in items], "has_more": has_more})


def _create_one(data: dict):
    """内部方法：创建单条（不 commit，由外层统一 commit）"""
    m = Product()
    _payload_to_model(m, data)
    if not m.slug or not m.title:
        return None, "slug/title required"
    # 预查重
    if Product.query.filter_by(slug=m.slug).first():
        return None, "slug exists"
    db.session.add(m)
    return m, None


def _create_bulk(items: list[dict]):
    """内部方法：批量创建（一次 commit）"""
    if not items:
        return {"created": 0, "items": [], "errors": [{"error": "empty payload"}]}, 400

    # 先把所有 slug 拿出来查重，避免循环中反复触发 IntegrityError
    want_slugs = [str((x.get("slug") or "")).strip() for x in items]
    exist_slugs = set(r.slug for r in Product.query.filter(Product.slug.in_(want_slugs)).all())

    created_objs = []
    errors = []
    for raw in items:
        slug = str((raw.get("slug") or "")).strip()
        title = str((raw.get("title") or "")).strip()
        if not slug or not title:
            errors.append({"item": raw, "error": "slug/title required"})
            continue
        if slug in exist_slugs:
            errors.append({"item": raw, "error": f"slug '{slug}' exists"})
            continue
        obj, err = _create_one(raw)
        if err:
            errors.append({"item": raw, "error": err})
            continue
        created_objs.append(obj)
        exist_slugs.add(slug)

    if created_objs:
        db.session.commit()
        return {"created": len(created_objs),
                "items": [_serialize(x) for x in created_objs],
                "errors": errors}, 201
    return {"created": 0, "errors": errors}, 400


@admin_product_bp.post("/products/bulk")
@jwt_required()
def admin_create_products_bulk():
    payload = request.get_json(force=True)
    if not isinstance(payload, list):
        return jsonify({"error": "expect JSON array"}), 400
    body, code = _create_bulk(payload)
    return jsonify(body), code


@admin_product_bp.post("/products")
@jwt_required()
def admin_create_product():
    payload = request.get_json(force=True)
    # 允许数组：自动走批量逻辑
    if isinstance(payload, list):
        body, code = _create_bulk(payload)
        return jsonify(body), code

    data = payload or {}
    try:
        obj, err = _create_one(data)
        if err:
            return jsonify({"error": err}), 400
        db.session.commit()
        return jsonify(_serialize(obj)), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "slug exists"}), 400


@admin_product_bp.get("/products/<int:pid>")
@jwt_required()
def admin_get_product(pid):
    m = Product.query.get_or_404(pid)
    return jsonify(_serialize(m))


@admin_product_bp.put("/products/<int:pid>")
@jwt_required()
def admin_update_product(pid):
    m = Product.query.get_or_404(pid)
    data = request.get_json(force=True) or {}
    _payload_to_model(m, data)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "slug exists"}), 400
    return jsonify(_serialize(m))


@admin_product_bp.delete("/products/<int:pid>")
@jwt_required()
def admin_delete_product(pid):
    m = Product.query.get_or_404(pid)
    db.session.delete(m)
    db.session.commit()
    return jsonify({"ok": True, "id": pid})
