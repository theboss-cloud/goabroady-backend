# routes/me.py
from __future__ import annotations
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from werkzeug.exceptions import BadRequest
from sqlalchemy import desc

from extensions import db

# === 按你工程里的真实模型路径导入（这些模块在你的 app.py 中已出现过或常规命名）===
# 若你的文件名不同，请将下面的导入路径改成你的真实路径。
from models.assessment_result import AssessmentResult  # 你 app.py 中已 import 过
try:
    from models.user import User  # 若存在用户模型
except Exception:
    User = None

# 可能你已经有独立的 Profile 模块/表；如果是其它文件名，请改这里。
# 若暂时没有该模型，也可以先用 routes/profile 的逻辑，但此处我们使用 ORM 表，更易持久化。
try:
    from models.profile import StudentProfile
except Exception:
    StudentProfile = None

bp_me = Blueprint("me", __name__, url_prefix="/api")

# ========== 工具：从 JWT 提取当前用户 id ==========
def _current_user_id() -> int | None:
    """
    兼容两种常见写法：
      - identity 直接就是 user_id（登录时 create_access_token(identity=user_id)）
      - identity 是 dict，例如 {"id": 123, "username": "..."}
    """
    ident = get_jwt_identity()
    if ident is None:
        return None
    if isinstance(ident, dict):
        return ident.get("id") or ident.get("user_id")
    try:
        return int(ident)
    except Exception:
        return None

def _claims_username_email(default_name="用户"):
    """
    从 JWT claims 里尽力拿用户名/邮箱，失败就回退默认。
    """
    claims = get_jwt() or {}
    # 常见字段尝试
    username = (
        claims.get("username")
        or claims.get("name")
        or claims.get("sub")  # 有些场景 sub 是用户名
    )
    email = claims.get("email")
    return username or default_name, email

# ========== 0) 健壮的空档案 ==========
_ALLOWED_TIERS = {"985", "211", "普通", "海外Top100"}

def _empty_profile():
    return {
        "gpa": None,              # 0.0 ~ 4.0
        "ielts": None,            # 0 ~ 9
        "toefl": None,
        "gre": None,              # 260 ~ 340
        "major": None,
        "grad_year": None,
        "work_years": None,       # 年
        "undergrad_tier": None,   # 985/211/普通/海外Top100
        "country_pref": None,
        "budget": None,
        "target_uni": None,       # 前端用于展示目标
        "target_program": None,
    }

# ========== 1) 我是谁 ==========
@bp_me.get("/me")
@jwt_required()
def me():
    uid = _current_user_id()
    if not uid:
        return jsonify({"error": "UNAUTHORIZED"}), 401

    # 优先用 User 表（如果存在）
    if User is not None:
        user = db.session.get(User, uid)
        if user:
            return jsonify({
                "id": user.id,
                "username": getattr(user, "username", None),
                "email": getattr(user, "email", None),
                "name": getattr(user, "name", None) or getattr(user, "username", None),
            })

    # 否则从 JWT claims 兜底
    username, email = _claims_username_email()
    return jsonify({"id": uid, "username": username, "email": email})

# ========== 2) 个人资料（GET/PUT） ==========
@bp_me.get("/me/profile")
@jwt_required()
def get_profile():
    uid = _current_user_id()
    if not uid:
        return jsonify({"error": "UNAUTHORIZED"}), 401

    # 如果没有 ORM 的 StudentProfile，也返回空对象供前端兼容
    if StudentProfile is None:
        username, email = _claims_username_email()
        return jsonify({"user": {"id": uid, "username": username, "email": email}, "profile": _empty_profile()})

    prof = db.session.query(StudentProfile).filter_by(user_id=uid).first()
    if not prof:
        username, email = _claims_username_email()
        return jsonify({"user": {"id": uid, "username": username, "email": email}, "profile": _empty_profile()})

    # 把 ORM 对象映射为前端需要的字段（不存在的属性用 None 兜底）
    out = {
        "gpa": getattr(prof, "gpa", None),
        "ielts": getattr(prof, "ielts", None),
        "toefl": getattr(prof, "toefl", None),
        "gre": getattr(prof, "gre", None),
        "major": getattr(prof, "major", None),
        "grad_year": getattr(prof, "grad_year", None),
        "work_years": getattr(prof, "work_years", None),
        "undergrad_tier": getattr(prof, "undergrad_tier", None),
        "country_pref": getattr(prof, "country_pref", None),
        "budget": getattr(prof, "budget", None),
        "target_uni": getattr(prof, "target_uni", None),
        "target_program": getattr(prof, "target_program", None),
    }
    username, email = _claims_username_email()
    return jsonify({"user": {"id": uid, "username": username, "email": email}, "profile": out})

@bp_me.put("/me/profile")
@jwt_required()
def put_profile():
    uid = _current_user_id()
    if not uid:
        return jsonify({"error": "UNAUTHORIZED"}), 401

    if StudentProfile is None:
        # 没有表就直接告诉前端不可用
        return jsonify({"error": "PROFILE_MODEL_NOT_FOUND"}), 501

    data = request.get_json(force=True) or {}

    # 基础校验
    def _to_float_or_none(v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except Exception:
            raise BadRequest("invalid number")

    gpa = _to_float_or_none(data.get("gpa"))
    if gpa is not None and not (0.0 <= gpa <= 4.0):
        raise BadRequest("gpa must be in [0,4]")

    work_years = _to_float_or_none(data.get("work_years"))
    if work_years is not None and work_years < 0:
        raise BadRequest("work_years must be >= 0")

    tier = data.get("undergrad_tier")
    if tier is not None and tier not in _ALLOWED_TIERS:
        raise BadRequest("undergrad_tier invalid")

    # 取或建
    prof = db.session.query(StudentProfile).filter_by(user_id=uid).first()
    if not prof:
        prof = StudentProfile(user_id=uid)
        db.session.add(prof)

    # 允许更新的字段（和上面的 _empty_profile 对齐）
    allowed_fields = {
        "gpa", "ielts", "toefl", "gre", "major", "grad_year",
        "work_years", "undergrad_tier", "country_pref", "budget",
        "target_uni", "target_program",
    }
    for k in allowed_fields:
        if k in data:
            setattr(prof, k, data[k])

    db.session.commit()

    return jsonify({"ok": True})

# ========== 3) 最近一次评测 ==========
@bp_me.get("/me/assessments/latest")
@jwt_required()
def latest_assessment():
    uid = _current_user_id()
    if not uid:
        return jsonify({"error": "UNAUTHORIZED"}), 401

    # AssessmentResult 表：你的 app.py 已经导入，说明存在
    q = db.session.query(AssessmentResult)

    # 兼容不同列名：user_id / student_id
    if hasattr(AssessmentResult, "user_id"):
        q = q.filter(AssessmentResult.user_id == uid)
    elif hasattr(AssessmentResult, "student_id"):
        q = q.filter(AssessmentResult.student_id == uid)

    # 按时间倒序取最新
    if hasattr(AssessmentResult, "created_at"):
        q = q.order_by(desc(AssessmentResult.created_at))
    elif hasattr(AssessmentResult, "updated_at"):
        q = q.order_by(desc(AssessmentResult.updated_at))

    a = q.first()
    if not a:
        # 没有数据：返回 204 或 {}
        return "", 204

    # 将评测结果整理为前端 Overview 期望的结构
    # 假设 AssessmentResult 有 fields: results(JSON), payload(JSON) 等
    results = getattr(a, "results", None) or []
    payload = getattr(a, "payload", None) or {}

    top = None
    prob = None
    low = None
    high = None
    risks = []
    improvements = []

    if results and isinstance(results, list):
        top_item = results[0] or {}
        prob = (
            top_item.get("prob")
            if isinstance(top_item.get("prob"), (int, float))
            else (top_item.get("percent") / 100.0 if isinstance(top_item.get("percent"), (int, float)) else None)
        )
        # 置信区间的多种命名兼容
        expl = top_item.get("explain", {}) or {}
        low  = expl.get("low")  or top_item.get("low")  or top_item.get("ci_low")
        high = expl.get("high") or top_item.get("high") or top_item.get("ci_high")

        risks = (expl.get("risks") or top_item.get("risks") or [])[:8]
        improvements = (expl.get("improvements") or top_item.get("improvements") or [])[:8]

        p_obj = top_item.get("program") or {}
        top = {
            "program_id": p_obj.get("id") or top_item.get("id") or top_item.get("program_id"),
            "title":      p_obj.get("title") or top_item.get("title") or top_item.get("program_name", ""),
            "university": p_obj.get("university") or top_item.get("university", ""),
            "country":    p_obj.get("country") or top_item.get("country", ""),
            "city":       p_obj.get("city") or top_item.get("city", ""),
        }

    return jsonify({
        "prob": prob,
        "low": low,
        "high": high,
        "risks": risks,
        "improvements": improvements,
        "results": results,
        "top": top,
        "input": payload,
    })
