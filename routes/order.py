# routes/order.py
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models.product import Product
from models.order import Order, OrderItem, ServiceEntitlement

orders_bp = Blueprint("orders_bp", __name__, url_prefix="/api")


def _current_user_id():
    ident = get_jwt_identity()
    if isinstance(ident, dict) and "id" in ident:
        return int(ident["id"])
    if isinstance(ident, (str, int)):
        return int(ident)
    return None


@orders_bp.post("/orders")
@jwt_required()
def create_order():
    """
    创建单个产品的订单（最小可用版本）：

    请求体示例：
    {
        "product_id": 123,
        "quantity": 1,
        "channel": "wechat"  // wechat | alipay | manual ...
    }

    当前版本：
    - 直接创建 pending 状态的订单与明细
    - 返回订单信息 + 一个“伪二维码内容”（pay_qr_content），前端可据此生成二维码
    - 将来接入真实支付时，只需要在此处创建支付会话并返回真正的支付链接/二维码内容
    """
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "UNAUTHORIZED"}), 401

    data = request.get_json(force=True) or {}
    product_id = data.get("product_id")
    quantity = int(data.get("quantity") or 1)
    quantity = max(quantity, 1)
    channel = (data.get("channel") or "wechat").lower()

    if not product_id:
        return jsonify({"error": "MISSING_PRODUCT_ID"}), 400

    product = Product.query.filter_by(id=product_id, is_published=True).first()
    if not product:
        return jsonify({"error": "PRODUCT_NOT_FOUND"}), 404

    # 单价优先使用 plans 中的第一个价格，其次使用 price 字段
    unit_price = None
    if product.plans and isinstance(product.plans, list):
        try:
            first_plan = product.plans[0]
            unit_price = Decimal(str(first_plan.get("price")))
        except Exception:
            unit_price = None
    if unit_price is None and product.price is not None:
        unit_price = Decimal(str(product.price))
    if unit_price is None:
        unit_price = Decimal("0.00")

    amount = unit_price * quantity

    order = Order(
        user_id=user_id,
        status="pending",
        channel=channel,
        currency="CNY",
        total_amount=amount,
        description=product.title,
    )
    db.session.add(order)
    db.session.flush()  # 先拿到 order.id

    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        product_title=product.title,
        product_slug=product.slug,
        unit_price=unit_price,
        quantity=quantity,
        amount=amount,
    )
    db.session.add(item)
    db.session.commit()

    # 伪二维码内容：将来可换成真实支付平台生成的 code_url
    pay_qr_content = f"order:{order.id}:user:{user_id}:channel:{channel}"

    payload = order.to_dict()
    payload["pay_qr_content"] = pay_qr_content
    return jsonify(payload), 201


@orders_bp.get("/orders")
@jwt_required()
def list_my_orders():
    """列出当前用户的订单（按时间倒序）"""
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"items": []})

    q = (
        Order.query
        .filter_by(user_id=user_id)
        .order_by(Order.created_at.desc())
    )
    items = [o.to_dict() for o in q.all()]
    return jsonify({"items": items})


@orders_bp.get("/orders/<int:order_id>")
@jwt_required()
def get_order(order_id: int):
    """单个订单详情"""
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "UNAUTHORIZED"}), 401

    order = Order.query.filter_by(id=order_id, user_id=user_id).first()
    if not order:
        return jsonify({"error": "NOT_FOUND"}), 404

    return jsonify(order.to_dict())


@orders_bp.post("/orders/<int:order_id>/mock-pay")
@jwt_required()
def mock_pay(order_id: int):
    """
    模拟支付成功（开发阶段使用）：

    - 将订单状态设为 paid，记录 paid_at
    - 为该订单对应的每个产品，创建一条 ServiceEntitlement（kind='product'）
    - 将来接入真实支付时，可以由支付平台回调触发同样的逻辑
    """
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "UNAUTHORIZED"}), 401

    order = Order.query.filter_by(id=order_id, user_id=user_id).first()
    if not order:
        return jsonify({"error": "NOT_FOUND"}), 404

    if order.status == "paid":
        # 已支付则直接返回
        return jsonify(order.to_dict())

    now = datetime.utcnow()
    order.status = "paid"
    order.paid_at = now

    # 为每个订单项生成服务权益（单项服务）
    for item in order.items:
        ent = ServiceEntitlement(
            user_id=user_id,
            kind="product",
            code=item.product_slug,
            product_id=item.product_id,
            source_order_id=order.id,
            remaining_uses=None,
            valid_from=now,
            valid_to=None,
            status="active",
        )
        db.session.add(ent)

    db.session.commit()
    return jsonify(order.to_dict())
