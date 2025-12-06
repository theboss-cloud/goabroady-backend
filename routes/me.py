# backend/routes/me.py
from __future__ import annotations
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import desc
from extensions import db

# 动态导入模型，防止循环引用
try:
    from models.user import User
except ImportError:
    User = None

try:
    from models.student_profile import StudentProfile
except ImportError:
    StudentProfile = None

try:
    from models.assessment_result import AssessmentResult
except ImportError:
    AssessmentResult = None

bp_me = Blueprint("me", __name__, url_prefix="/api")

def _current_user_id() -> int | None:
    ident = get_jwt_identity()
    if ident is None: return None
    if isinstance(ident, dict): return ident.get("id")
    try: return int(ident)
    except: return None

# 1. 我是谁
@bp_me.get("/me")
@jwt_required()
def me():
    uid = _current_user_id()
    if not uid: return jsonify({"error": "UNAUTHORIZED"}), 401
    
    if User:
        user = db.session.get(User, uid)
        if user:
            return jsonify({
                "id": user.id,
                "username": user.username,
                "email": getattr(user, "email", ""),
                "phone": getattr(user, "phone", ""),
                "avatar": getattr(user, "avatar", "")
            })
    return jsonify({"id": uid, "msg": "User not found"})

# 2. 获取个人资料 (🔥 修复：扁平化返回 + 查数据库)
@bp_me.get("/me/profile")
@jwt_required()
def get_profile():
    uid = _current_user_id()
    if not uid: return jsonify({"error": "UNAUTHORIZED"}), 401

    # 1. 获取 User (为了拿 phone, email, avatar)
    user = db.session.get(User, uid) if User else None
    if not user:
        return jsonify({"msg": "User not found"}), 404

    # 2. 获取 Profile (为了拿 gpa, major 等)
    prof = None
    if StudentProfile:
        prof = db.session.query(StudentProfile).filter_by(user_id=uid).first()
        if not prof:
            prof = StudentProfile(user_id=uid)
            db.session.add(prof)
            db.session.commit()

    # 🔥 关键：把 User 表的数据和 Profile 表的数据合并返回
    data = {
        # --- User 表字段 ---
        "id": user.id,
        "username": user.username,
        "phone": getattr(user, "phone", "") or "",   
        "email": getattr(user, "email", "") or "",   
        "avatar": getattr(user, "avatar", "") or "", 
        
        # --- Profile 表字段 ---
        "gpa": getattr(prof, "gpa", None) if prof else None,
        "gpa_scale": getattr(prof, "gpa_scale", "4.0") if prof else "4.0",
        "ielts": getattr(prof, "ielts", None) if prof else None,
        "toefl": getattr(prof, "toefl", None) if prof else None,
        "gre": getattr(prof, "gre", None) if prof else None,
        "english_test": getattr(prof, "english_test", None) if prof else None,
        "english_score": getattr(prof, "english_score", None) if prof else None,
        "major": getattr(prof, "major", None) if prof else None,
        "grad_year": getattr(prof, "grad_year", None) if prof else None,
        "work_years": getattr(prof, "work_years", None) if prof else None,
        "target_country": getattr(prof, "target_country", None) if prof else None,
        "budget": getattr(prof, "budget", None) if prof else None,
        
        # 兼容旧字段
        "country_pref": getattr(prof, "country_pref", None) if prof else None,
        "target_uni": getattr(prof, "target_uni", None) if prof else None,
        "target_program": getattr(prof, "target_program", None) if prof else None,
        "undergrad_tier": getattr(prof, "undergrad_tier", None) if prof else None,
    }
    return jsonify(data)

# 3. 更新个人资料 (🔥 修复：同时更新 User 和 Profile)
@bp_me.put("/me/profile")
@jwt_required()
def put_profile():
    uid = _current_user_id()
    if not uid: return jsonify({"error": "UNAUTHORIZED"}), 401

    data = request.get_json(silent=True) or {}
    
    # 🔥 关键修复：显式更新 User 表！
    if User:
        user = db.session.get(User, uid)
        if user:
            if "phone" in data: user.phone = data["phone"]
            if "email" in data: user.email = data["email"]
            if "avatar" in data: user.avatar = data["avatar"]

    # 更新 Profile 表
    if StudentProfile:
        prof = db.session.query(StudentProfile).filter_by(user_id=uid).first()
        if not prof:
            prof = StudentProfile(user_id=uid)
            db.session.add(prof)

        # 这里放档案相关的字段
        allowed_fields = [
            "gpa", "gpa_scale", "ielts", "toefl", "gre", 
            "english_test", "english_score", "major", 
            "grad_year", "work_years", "target_country", "budget",
            "country_pref", "target_uni", "target_program", "undergrad_tier"
        ]
        
        for k in allowed_fields:
            if k in data:
                setattr(prof, k, data[k])

    try:
        db.session.commit()
        return jsonify({"msg": "保存成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": f"保存失败: {str(e)}"}), 500

# 4. 最近评测 (保持不变)
@bp_me.get("/me/assessments/latest")
@jwt_required()
def latest_assessment():
    uid = _current_user_id()
    if not uid: return jsonify({"error": "UNAUTHORIZED"}), 401
    if not AssessmentResult: return "", 204

    q = db.session.query(AssessmentResult)
    if hasattr(AssessmentResult, "user_id"): q = q.filter(AssessmentResult.user_id == uid)
    elif hasattr(AssessmentResult, "student_id"): q = q.filter(AssessmentResult.student_id == uid)
    if hasattr(AssessmentResult, "created_at"): q = q.order_by(desc(AssessmentResult.created_at))
    
    a = q.first()
    if not a: return "", 204

    results = getattr(a, "results", None) or []
    payload = getattr(a, "payload", None) or {}
    top_item = results[0] if results else {}
    prob = top_item.get("prob")
    if prob is None and "percent" in top_item: prob = top_item["percent"] / 100.0
    p_obj = top_item.get("program") or {}
    top = {
        "title": p_obj.get("title") or top_item.get("title"),
        "university": p_obj.get("university") or top_item.get("university"),
        "country": p_obj.get("country") or top_item.get("country"),
    }
    return jsonify({
        "prob": prob, "results": results, "top": top, "input": payload
    })