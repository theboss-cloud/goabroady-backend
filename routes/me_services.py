# routes/me_services.py
"""
与当前用户“已开通服务/权益”相关的接口：
GET /api/me/services

依赖：
- ServiceEntitlement：记录用户已开通的单项服务或套餐
- Product：补充展示 title、slug 等信息
"""

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models.order import ServiceEntitlement
from models.product import Product
from models.student_profile import StudentProfile

me_services_bp = Blueprint("me_services_bp", __name__, url_prefix="/api/me")


def _current_user_id():
    ident = get_jwt_identity()
    if isinstance(ident, dict) and "id" in ident:
        return int(ident["id"])
    if isinstance(ident, (str, int)):
        try:
            return int(ident)
        except Exception:
            return None
    return None


@me_services_bp.get("/services")
@jwt_required()
def my_services():
    """
    返回当前用户的服务权益列表（不包含当前套餐名称，套餐仍由 /api/billing/plan 提供）：

    返回示例：
    {
      "items": [
        {
          "id": 1,
          "kind": "product",
          "code": "ps-edit",
          "product_id": 5,
          "title": "PS 文书修改（3 次）",
          "status": "active",
          "remaining_uses": null,
          "valid_from": "2025-01-01T...",
          "valid_to": null
        },
        ...
      ]
    }
    """
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"items": []})

    # 关联产品，拿到显示用名称
    rows = (
        db.session.query(ServiceEntitlement, Product)
        .outerjoin(Product, ServiceEntitlement.product_id == Product.id)
        .filter(ServiceEntitlement.user_id == user_id)
        .order_by(ServiceEntitlement.created_at.desc())
        .all()
    )

    items = []
    for ent, prod in rows:
        # 只展示 active/有效 的权益（如果你想展示历史记录，也可以去掉这个判断）
        if ent.status not in ("active", None):
            continue

        title = None
        if prod is not None and prod.title:
            title = prod.title
        elif ent.code:
            title = ent.code
        else:
            title = "已开通服务"

        items.append(
            {
                "id": ent.id,
                "kind": ent.kind,
                "code": ent.code,
                "product_id": ent.product_id,
                "title": title,
                "status": ent.status or "active",
                "remaining_uses": ent.remaining_uses,
                "valid_from": ent.valid_from.isoformat() if ent.valid_from else None,
                "valid_to": ent.valid_to.isoformat() if ent.valid_to else None,
            }
        )

    return jsonify({"items": items})
