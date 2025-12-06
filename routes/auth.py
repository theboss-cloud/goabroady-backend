# routes/auth.py
from __future__ import annotations
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from extensions import db
from models.user import User  # 确保模型路径正确
from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# === 配置，可按需调整 ===
ACCESS_EXPIRES_HOURS = 2   # accessToken 有效期（小时）
REFRESH_EXPIRES_DAYS = 30  # refreshToken 有效期（天）


def _now_utc() -> datetime:
    return datetime.utcnow()


def _fmt_expires(dt: datetime) -> str:
    """返回前端友好的过期时间字符串（也可改为时间戳）"""
    return dt.strftime("%Y/%m/%d %H:%M:%S")


def _normalize_roles(user) -> list[str]:
    """
    把用户角色统一成字符串列表，并处理 superadmin → admin/staff 透传。
    兼容 user.role (str) 和 user.roles (list) 两种写法。
    """
    roles: list[str] = []
    if hasattr(user, "roles") and isinstance(user.roles, (list, tuple)):
        roles = [str(r) for r in user.roles]
    elif hasattr(user, "role") and getattr(user, "role", None):
        roles = [str(user.role)]
    # 超管包含 admin+staff
    if "superadmin" in roles:
        roles = list(set(roles + ["admin", "staff"]))
    return roles


def _check_password(user: User, raw_pwd: str) -> bool:
    """
    兼容两种密码实现：
      1) user.check_password(raw) -> bool
      2) user.password_hash（Werkzeug） 与 check_password_hash
    """
    if hasattr(user, "check_password") and callable(user.check_password):
        try:
            return bool(user.check_password(raw_pwd))
        except Exception:
            pass
    if hasattr(user, "password_hash") and user.password_hash:
        try:
            return check_password_hash(user.password_hash, raw_pwd)
        except Exception:
            pass
    # 如果你的 User 还有别的密码字段，请在此增加分支
    return False


@auth_bp.post("/login")
def login():
    """
    用户名密码登录：
      入参：{"username": "...", "password": "..."}
      返回：顶层 + data.* 同时包含 token（前端/后台两边都兼容）
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or data.get("account") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"success": False, "msg": "用户名或密码不能为空"}), 200

    user = User.query.filter_by(username=username).first()
    if not user or not _check_password(user, password):
        return jsonify({"success": False, "msg": "用户名或密码错误"}), 200

    roles = _normalize_roles(user)
    # 统一：JWT identity 用**字符串**，避免 422
    identity = str(getattr(user, "id", None) or getattr(user, "username"))

    access_expires_delta = timedelta(hours=ACCESS_EXPIRES_HOURS)
    access_expires_at = _now_utc() + access_expires_delta
    refresh_expires_delta = timedelta(days=REFRESH_EXPIRES_DAYS)

    claims = {"roles": roles}
    access_token = create_access_token(
        identity=identity,
        additional_claims=claims,
        expires_delta=access_expires_delta,
    )
    refresh_token = create_refresh_token(
        identity=identity,
        additional_claims=claims,
        expires_delta=refresh_expires_delta,
    )

    # 展示信息（按你的模型字段取）
    avatar = getattr(user, "avatar", "") or ""
    nickname = getattr(user, "nickname", "") or ""

    # 关键：把 token 同时放顶层 & data.*
    resp = {
        "success": True,
        # 顶层：给前台站点（AuthModal.onLoginOk）直接读取
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "expires": _fmt_expires(access_expires_at),
        # data：保留给后台管理（PureAdmin）等处使用
        "data": {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expires": _fmt_expires(access_expires_at),
            "username": user.username,
            "nickname": nickname,
            "avatar": avatar,
            "roles": roles,
            "permissions": ["*:*:*"],
        },
    }
    return jsonify(resp), 200


@auth_bp.post("/refresh-token")
def refresh_token():
    """
    刷新 accessToken：
      入参：{"refreshToken": "..."}（在 body，非 Authorization 头）
      返回：同样顶层 + data.* 都包含新的 accessToken
    """
    data = request.get_json(silent=True) or {}
    raw_refresh = data.get("refreshToken", "")

    if not raw_refresh:
        return jsonify({"success": False, "msg": "缺少 refreshToken"}), 401

    try:
        decoded = decode_token(raw_refresh)  # 过期会抛异常
        # 额外保险：检查 exp
        exp_ts = decoded.get("exp")
        if exp_ts and _now_utc().timestamp() >= float(exp_ts):
            return jsonify({"success": False, "msg": "refreshToken 已过期"}), 401

        # 我们登录时 identity 用的是字符串（id 或 username）
        identity = str(decoded.get("sub") or "")
        if not identity:
            return jsonify({"success": False, "msg": "refreshToken 无效"}), 401

        # 取 roles：我们在生成 refresh 时也放了 claims.roles
        claims = (decoded.get("claims") or {}) if isinstance(decoded.get("claims"), dict) else {}
        roles = claims.get("roles") or []

        # 如果 claims 里没有 roles，可从 DB 兜底再查一次
        if not roles:
            user = None
            # identity 可能是 id 或 username，尽量都试一遍
            try:
                user = User.query.filter_by(id=int(identity)).first()
            except Exception:
                pass
            if not user:
                user = User.query.filter_by(username=identity).first()
            if user:
                roles = _normalize_roles(user)

        access_expires_delta = timedelta(hours=ACCESS_EXPIRES_HOURS)
        access_expires_at = _now_utc() + access_expires_delta
        new_access = create_access_token(
            identity=identity,
            additional_claims={"roles": roles},
            expires_delta=access_expires_delta,
        )

        resp = {
            "success": True,
            "accessToken": new_access,      # 顶层
            "refreshToken": raw_refresh,    # 顶层沿用旧的 refresh
            "expires": _fmt_expires(access_expires_at),
            "data": {
                "accessToken": new_access,
                "refreshToken": raw_refresh,
                "expires": _fmt_expires(access_expires_at),
            },
        }
        return jsonify(resp), 200

    except Exception:
        return jsonify({"success": False, "msg": "refreshToken 无效或已过期"}), 401


def role_required(*required_roles):
    """
    装饰器：限制接口必须由特定角色访问。
    使用：@role_required("admin", "staff")
    """
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt() or {}
            user_roles = claims.get("roles") or claims.get("role") or []
            if isinstance(user_roles, str):
                user_roles = [user_roles]
            if not any(role in user_roles for role in required_roles):
                return jsonify({"msg": "权限不足"}), 403
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper


@auth_bp.post("/register")
def register():

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    phone = (data.get("phone") or "").strip()  # 🔥 新增：获取手机号

    if not username or not password:
        return jsonify({"success": False, "msg": "用户名或密码不能为空"}), 200

    if User.query.filter_by(username=username).first():
        return jsonify({"success": False, "msg": "用户名已存在"}), 200
    
    # 如果填了手机号，检查是否重复
    if phone and User.query.filter_by(phone=phone).first():
        return jsonify({"success": False, "msg": "该手机号已被注册"}), 200

    # 🔥 存入 phone
    user = User(username=username, phone=phone if phone else None)
    
    if hasattr(user, "set_password"):
        user.set_password(password)
    
    db.session.add(user)
    db.session.commit()

    roles = ["user"]
    identity = str(user.id)
    access_token = create_access_token(identity=identity, additional_claims={"roles": roles})
    refresh_token = create_refresh_token(identity=identity, additional_claims={"roles": roles})
    expires = _fmt_expires(_now_utc() + timedelta(hours=ACCESS_EXPIRES_HOURS))

    return jsonify({
        "success": True,
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "expires": expires,
        "data": {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expires": expires,
            "username": user.username,
            "phone": user.phone, # 可以把手机号也返回给前端
            "roles": roles
        }
    }), 200
