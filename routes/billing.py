# routes/billing.py
"""
订阅与付款相关接口：

当前版本特点：
- /billing/plan     ：根据 StudentProfile.service_type & ServiceEntitlement 计算当前套餐
- /billing/invoices ：根据订单表 Order 列出当前用户的付费记录
- /billing/checkout ：创建一个“全程服务 Pro 套餐”的订单，并立即视为已支付（开发阶段）

将来接入真实支付时：
- /billing/checkout 可以改为创建支付会话（微信/支付宝/Stripe），返回真实的支付链接或二维码内容；
- 支付平台回调中，将订单置为 paid，并创建 ServiceEntitlement + 更新 StudentProfile.service_type。
"""
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models.student_profile import StudentProfile
from models.order import Order, ServiceEntitlement

billing_bp = Blueprint("billing_bp", __name__, url_prefix="/api")


def _current_user_id():
    ident = get_jwt_identity()
    if isinstance(ident, dict) and "id" in ident:
        return int(ident["id"])
    if isinstance(ident, (str, int)):
        return int(ident)
    return None


def _get_profile(user_id):
    if not user_id:
        return None
    return StudentProfile.query.filter_by(user_id=user_id).first()


def _plan_from_state(user_id):
    """
    根据 ServiceEntitlement + StudentProfile 推断当前套餐：
    - 若存在 active 的 plan/full 权益 → Pro
    - 否则看 StudentProfile.service_type：
        - full -> Pro
        - diy  -> DIY
        - 其他/空 -> Free
    """
    if not user_id:
        return {"name": "Free", "price_str": "¥0"}

    ent = (
        ServiceEntitlement.query
        .filter_by(user_id=user_id, kind="plan", code="full", status="active")
        .first()
    )
    if ent:
        return {"name": "Pro", "price_str": "¥9800"}

    prof = _get_profile(user_id)
    code = (prof.service_type if prof else None) or "diy"
    code = code.lower()

    if code == "full":
        return {"name": "Pro", "price_str": "¥9800"}
    if code == "diy":
        return {"name": "DIY", "price_str": "¥0"}

    return {"name": "Free", "price_str": "¥0"}


@billing_bp.get("/billing/plan")
@jwt_required(optional=True)
def my_plan():
    user_id = _current_user_id()
    plan = _plan_from_state(user_id)
    return jsonify(plan)


@billing_bp.get("/billing/invoices")
@jwt_required()
def invoices():
    """
    账单记录：直接使用订单表 Order 中 status = 'paid' 的记录。
    """
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"items": []})

    orders = (
        Order.query
        .filter_by(user_id=user_id, status="paid")
        .order_by(Order.paid_at.desc().nullslast(), Order.created_at.desc())
        .all()
    )

    items = []
    for o in orders:
        amt = o.total_amount or 0
        # 将 Decimal 转为字符串金额
        amount_str = f"¥{amt:.2f}" if hasattr(amt, "__format__") else str(amt)
        created = o.paid_at or o.created_at
        items.append(
            {
                "id": f"order_{o.id}",
                "title": o.description or "GoAbroady 服务",
                "amount_str": amount_str,
                "created_at": created.isoformat() if created else None,
            }
        )

    return jsonify({"items": items})


@billing_bp.post("/billing/checkout")
@jwt_required()
def checkout():
    """
    订阅/升级入口（Pro 全程服务最低可用实现）：

    当前版本：
    - 不接真实支付渠道，直接创建一个已支付订单 + plan 类型的 ServiceEntitlement
    - 更新 StudentProfile.service_type = 'full'
    - 返回一个站内跳转链接 /user/billing?plan=pro&status=success

    请求体示例：
    { "plan": "pro" }
    """
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "UNAUTHORIZED"}), 401

    data = request.get_json(force=True) or {}
    plan_code = (data.get("plan") or "pro").lower()

    # 目前仅支持 pro = full 套餐
    if plan_code not in ("pro", "full"):
        plan_code = "pro"

    now = datetime.utcnow()
    amount = Decimal("9800.00")  # 这里仅作示意，单位：CNY 元，未来可从配置或产品表读取

    # 创建订单（视为内部渠道 manual，并直接标记已支付）
    order = Order(
        user_id=user_id,
        status="paid",
        channel="manual",
        currency="CNY",
        total_amount=amount,
        description="GoAbroady Pro - 全程留学服务",
        created_at=now,
        paid_at=now,
    )
    db.session.add(order)
    db.session.flush()

    # 创建 plan 类型的权益记录
    ent = ServiceEntitlement(
        user_id=user_id,
        kind="plan",
        code="full",
        product_id=None,
        source_order_id=order.id,
        remaining_uses=None,
        valid_from=now,
        valid_to=None,
        status="active",
    )
    db.session.add(ent)

    # 更新学生档案
    profile = _get_profile(user_id)
    if not profile:
        profile = StudentProfile(user_id=user_id)
        db.session.add(profile)
    profile.service_type = "full"
    if hasattr(profile, "updated_at"):
        profile.updated_at = now

    db.session.commit()

    return jsonify(
        {
            "checkout_url": "/user/billing?plan=pro&status=success",
            "order_id": order.id,
        }
    )
