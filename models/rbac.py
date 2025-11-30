# backend/models/rbac.py
from extensions import db

# 角色与权限的多对多
role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)

class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)  # 如 "admin", "staff", "finance"
    desc = db.Column(db.String(200))

    permissions = db.relationship("Permission", secondary=role_permissions, backref="roles", lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "desc": self.desc,
            "permissions": [p.code for p in self.permissions],
        }

class Permission(db.Model):
    __tablename__ = "permissions"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)  # 如 "orders.read", "orders.refund"
    name = db.Column(db.String(100), nullable=False)  # 展示名

    def to_dict(self):
        return {"id": self.id, "code": self.code, "name": self.name}
