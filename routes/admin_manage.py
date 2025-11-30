# backend/routes/admin_manage.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from extensions import db
from models.admin_user import AdminUser, StudentUser
from models.rbac import Role, Permission

admin_manage_bp = Blueprint("admin_manage_bp", __name__, url_prefix="/api/admin")

def require_roles(*need):
    def deco(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*args, **kwargs):
            claims = get_jwt() or {}
            roles = claims.get("roles") or claims.get("role") or []
            if isinstance(roles, str):
                roles = [roles]
            if not any(r in roles for r in need):
                return jsonify({"msg": "forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco

# ========== 管理员（AdminUser） ==========
@admin_manage_bp.get("/admins")
@jwt_required()
@require_roles("admin")
def list_admins():
    q = AdminUser.query.order_by(AdminUser.id.desc()).all()
    return jsonify([a.to_dict() for a in q])

@admin_manage_bp.post("/admins")
@jwt_required()
@require_roles("admin")
def create_admin():
    data = request.get_json(force=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"msg": "username/password required"}), 400
    if AdminUser.query.filter_by(username=username).first():
        return jsonify({"msg": "username exists"}), 409
    a = AdminUser(username=username, is_active=True)
    a.set_password(password)
    # 可选：初始化角色
    role_names = data.get("roles") or []
    if role_names:
        roles = Role.query.filter(Role.name.in_(role_names)).all()
        a.roles = roles
    db.session.add(a)
    db.session.commit()
    return jsonify(a.to_dict())

@admin_manage_bp.put("/admins/<int:aid>")
@jwt_required()
@require_roles("admin")
def update_admin(aid):
    a = AdminUser.query.get_or_404(aid)
    data = request.get_json(force=True) or {}
    if "password" in data and data["password"]:
        a.set_password(data["password"])
    if "is_active" in data:
        a.is_active = bool(data["is_active"])
    if "roles" in data:
        roles = Role.query.filter(Role.name.in_(data["roles"] or [])).all()
        a.roles = roles
    db.session.commit()
    return jsonify(a.to_dict())

@admin_manage_bp.delete("/admins/<int:aid>")
@jwt_required()
@require_roles("admin")
def delete_admin(aid):
    a = AdminUser.query.get_or_404(aid)
    db.session.delete(a)
    db.session.commit()
    return jsonify({"msg": "deleted"})

# ========== 角色（Role） ==========
@admin_manage_bp.get("/roles")
@jwt_required()
@require_roles("admin")
def list_roles():
    roles = Role.query.order_by(Role.id.asc()).all()
    return jsonify([r.to_dict() for r in roles])

@admin_manage_bp.post("/roles")
@jwt_required()
@require_roles("admin")
def create_role():
    data = request.get_json(force=True) or {}
    name = data.get("name")
    if not name:
        return jsonify({"msg": "name required"}), 400
    if Role.query.filter_by(name=name).first():
        return jsonify({"msg": "role exists"}), 409
    r = Role(name=name, desc=data.get("desc"))
    db.session.add(r)
    db.session.commit()
    return jsonify(r.to_dict())

@admin_manage_bp.put("/roles/<int:rid>")
@jwt_required()
@require_roles("admin")
def update_role(rid):
    r = Role.query.get_or_404(rid)
    data = request.get_json(force=True) or {}
    if "name" in data and data["name"]:
        r.name = data["name"]
    if "desc" in data:
        r.desc = data["desc"]
    db.session.commit()
    return jsonify(r.to_dict())

@admin_manage_bp.delete("/roles/<int:rid>")
@jwt_required()
@require_roles("admin")
def delete_role(rid):
    r = Role.query.get_or_404(rid)
    db.session.delete(r)
    db.session.commit()
    return jsonify({"msg": "deleted"})

# ========== 权限（Permission） ==========
@admin_manage_bp.get("/permissions")
@jwt_required()
@require_roles("admin")
def list_permissions():
    perms = Permission.query.order_by(Permission.id.asc()).all()
    return jsonify([p.to_dict() for p in perms])

@admin_manage_bp.post("/permissions")
@jwt_required()
@require_roles("admin")
def create_permission():
    data = request.get_json(force=True) or {}
    code = data.get("code")
    name = data.get("name")
    if not code or not name:
        return jsonify({"msg": "code/name required"}), 400
    if Permission.query.filter_by(code=code).first():
        return jsonify({"msg": "permission exists"}), 409
    p = Permission(code=code, name=name)
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict())

@admin_manage_bp.put("/roles/<int:rid>/permissions")
@jwt_required()
@require_roles("admin")
def set_role_permissions(rid):
    r = Role.query.get_or_404(rid)
    data = request.get_json(force=True) or {}
    codes = data.get("codes") or []
    perms = Permission.query.filter(Permission.code.in_(codes)).all()
    r.permissions = perms
    db.session.commit()
    return jsonify(r.to_dict())
