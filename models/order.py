# backend/models/order.py
from datetime import datetime
from extensions import db

class Order(db.Model):
    """
    用户订单记录 (融合版)：
    - 兼容原有字段：total_amount, items, description
    - 新增支付字段：out_trade_no, trade_no, product_name, amount, pay_time
    """
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    # === 原有字段 (保持不变) ===
    status = db.Column(db.String(20), default="pending", index=True)  # pending | paid | cancelled | refunded (注意：pay.py使用 'PENDING'/'PAID'，建议统一)
    channel = db.Column(db.String(20))                                # wechat / alipay / manual / stripe ...
    currency = db.Column(db.String(8), default="CNY")
    total_amount = db.Column(db.Numeric(10, 2), nullable=True)        # 原有金额字段
    description = db.Column(db.String(255))                           # 原有描述字段
    paid_at = db.Column(db.DateTime)                                  # 原有支付时间

    # === 🔥 新增字段 (为了兼容 pay.py 的逻辑) ===
    # 支付平台必须的唯一商户订单号
    out_trade_no = db.Column(db.String(64), unique=True, nullable=True, index=True) 
    # 支付宝/微信返回的流水号
    trade_no = db.Column(db.String(64), nullable=True)
    # 商品名称 (pay.py 使用 product_name 而不是 description)
    product_name = db.Column(db.String(128), nullable=True)
    # 支付金额 (pay.py 使用 amount (Float) 而不是 total_amount (Numeric))
    # 建议：后续代码统一逻辑，暂时并存以防报错
    amount = db.Column(db.Float, nullable=True)
    # 支付时间 (pay.py 使用 pay_time 而不是 paid_at)
    pay_time = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联关系 (保持不变)
    items = db.relationship("OrderItem", backref="order", lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "channel": self.channel,
            "currency": self.currency,
            # 优先返回 pay.py 用的字段，如果没有则返回旧字段
            "out_trade_no": self.out_trade_no,
            "trade_no": self.trade_no,
            "product_name": self.product_name or self.description,
            "amount": self.amount if self.amount is not None else (str(self.total_amount) if self.total_amount else 0),
            
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else (self.pay_time.isoformat() if self.pay_time else None),
            
            # 保持原有的 items 输出
            "items": [i.to_dict() for i in self.items],
        }


class OrderItem(db.Model):
    """
    订单明细 (保持不变)
    """
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)

    product_title = db.Column(db.String(200), nullable=False)
    product_slug = db.Column(db.String(120), nullable=False)

    unit_price = db.Column(db.Numeric(10, 2), nullable=True)
    quantity = db.Column(db.Integer, default=1)
    amount = db.Column(db.Numeric(10, 2), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_title": self.product_title,
            "product_slug": self.product_slug,
            "unit_price": str(self.unit_price) if self.unit_price is not None else None,
            "quantity": self.quantity,
            "amount": str(self.amount) if self.amount is not None else None,
        }


class ServiceEntitlement(db.Model):
    """
    用户权益 (保持不变)
    """
    __tablename__ = "service_entitlements"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    kind = db.Column(db.String(20), nullable=False)   # plan | product
    code = db.Column(db.String(64), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)

    source_order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)

    remaining_uses = db.Column(db.Integer, nullable=True)
    valid_from = db.Column(db.DateTime, nullable=True)
    valid_to = db.Column(db.DateTime, nullable=True)

    status = db.Column(db.String(20), default="active")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "code": self.code,
            "product_id": self.product_id,
            "source_order_id": self.source_order_id,
            "remaining_uses": self.remaining_uses,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }