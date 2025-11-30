# routes/pay.py
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

pay_bp = Blueprint("pay_bp", __name__, url_prefix="/api")


def _current_user_id():
    """和 routes/order.py 里保持一致的小工具函数"""
    ident = get_jwt_identity()
    if isinstance(ident, dict) and "id" in ident:
        return int(ident["id"])
    if isinstance(ident, (str, int)):
        return int(ident)
    return None


@pay_bp.post("/pay/prepare")
@jwt_required()
def prepare_pay():
    """
    统一收银台专用：根据购物车生成一个“待支付订单号 + 二维码内容”。

    当前版本只返回模拟的 UnionPay code_url，
    将来接入真实银联 / 微信等时，把这里改成真正的支付网关调用即可。
    """
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"error": "UNAUTHORIZED"}), 401

    data = request.get_json(force=True) or {}
    channel = (data.get("channel") or "unionpay").lower()
    items = data.get("items") or []
    amount_raw = data.get("amount")

    # 兜底计算金额
    try:
        amount = Decimal(str(amount_raw))
    except Exception:
        total = Decimal("0.00")
        for item in items:
            price = Decimal(str(item.get("price") or "0"))
            qty = int(item.get("qty") or 1)
            total += price * qty
        amount = total

    now = datetime.utcnow()
    # 简单生成一个订单号（真正接支付时，会由支付平台给出 trade_no）
    order_no = f"{channel.upper()}{now.strftime('%Y%m%d%H%M%S')}{user_id:06d}"

    # 统一使用 code_url 字段给前端
    code_url = f"UNIONPAY://ORDER/{order_no}?amount={amount}"

    return jsonify(
        {
            "order_no": order_no,
            "code_url": code_url,
            "channel": channel,
            "amount": str(amount),
            "items": items,
        }
    )
