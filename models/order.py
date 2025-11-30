from datetime import datetime
from extensions import db

class Order(db.Model):
    """
    用户订单记录：
    - 支持多渠道：wechat / alipay / manual / stripe 等
    - 为了简化前期开发，amount 使用 Numeric(10,2)，保持与 Product.price 一致
    """
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    status = db.Column(db.String(20), default="pending", index=True)  # pending | paid | cancelled | refunded
    channel = db.Column(db.String(20))                                # wechat / alipay / manual / stripe ...
    currency = db.Column(db.String(8), default="CNY")
    total_amount = db.Column(db.Numeric(10, 2), nullable=True)        # 总金额
    description = db.Column(db.String(255))                           # 简短描述（产品摘要）

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)

    items = db.relationship("OrderItem", backref="order", lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "channel": self.channel,
            "currency": self.currency,
            "total_amount": str(self.total_amount) if self.total_amount is not None else None,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class OrderItem(db.Model):
    """
    订单明细：
    - 一条订单可以对应多个 Product（目前前端可以只用 1 个）
    - unit_price/amount 使用 Numeric(10,2)
    """
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)

    # 冗余快照字段，避免产品后续改名/改价影响历史订单显示
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
    用户已开通的服务权益：
    - full 套餐：kind = 'plan', code = 'full'
    - 单项产品：kind = 'product', product_id 不为空
    - 未来可以扩展次数、有效期等
    """
    __tablename__ = "service_entitlements"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    kind = db.Column(db.String(20), nullable=False)   # plan | product
    code = db.Column(db.String(64), nullable=True)    # 例如 full / diy / slug 等
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)

    source_order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)

    remaining_uses = db.Column(db.Integer, nullable=True)  # None 表示不限次数
    valid_from = db.Column(db.DateTime, nullable=True)
    valid_to = db.Column(db.DateTime, nullable=True)

    status = db.Column(db.String(20), default="active")  # active | expired | revoked

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
