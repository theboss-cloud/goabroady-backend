# routes/profile.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models.user import User                  # 模块名 user（小写），类名 User（大写）✅
from models.student_profile import StudentProfile
from models.assessment_result import AssessmentResult  # 新增：预测结果模型

profile_bp = Blueprint("profile", __name__)

def _current_user_id():
    ident = get_jwt_identity()
    if isinstance(ident, dict) and 'id' in ident:
        return int(ident['id'])
    if isinstance(ident, (str, int)):
        return int(ident)
    return None

def _sp_to_dict(sp: StudentProfile | None):
    if not sp:
        return {}
    # 按你模型字段调整；这里只序列化常用字段，避免泄露 SQLAlchemy 内部状态
    return {
        "user_id": sp.user_id,
        "gpa": sp.gpa,
        "ielts": sp.ielts,
        "toefl": sp.toefl,
        "gre": sp.gre,
        "major": sp.major,
        "grad_year": sp.grad_year,
        "work_years": sp.work_years,
        "country_pref": sp.country_pref,
        "budget": sp.budget,
    }

@profile_bp.get("/api/me/profile")
@jwt_required()
def get_profile():
    uid = _current_user_id()
    if not uid:
        return jsonify({"msg": "Unauthorized"}), 401

    # 可选：附带基础用户信息
    user = User.query.get(uid)
    sp = StudentProfile.query.filter_by(user_id=uid).first()

    data = {
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "status": user.status,
        } if user else {},
        "profile": _sp_to_dict(sp)
    }
    return jsonify(data)

@profile_bp.put("/api/me/profile")
@jwt_required()
def put_profile():
    uid = _current_user_id()
    if not uid:
        return jsonify({"msg": "Unauthorized"}), 401

    data = request.get_json() or {}
    sp = StudentProfile.query.filter_by(user_id=uid).first()
    if not sp:
        sp = StudentProfile(user_id=uid)
        db.session.add(sp)

    for f in ["gpa","ielts","toefl","gre","major","grad_year","work_years","country_pref","budget"]:
        if f in data:
            setattr(sp, f, data[f])

    db.session.commit()
    return jsonify({"msg": "saved"})

# ---------- 我的预测结果：列表 ----------
@profile_bp.get("/api/me/assessment-results")
@jwt_required()
def list_assessment_results():
    uid = _current_user_id()
    if not uid:
        return jsonify({"msg": "Unauthorized"}), 401

    limit = int(request.args.get("limit", 20))
    q = AssessmentResult.query.filter_by(user_id=uid).order_by(AssessmentResult.created_at.desc())
    items = q.limit(limit).all()

    def to_dict(x: AssessmentResult):
        return {
            "id": x.id,
            "created_at": x.created_at.isoformat() if x.created_at else None,
            "top": {
                "program_id": x.top_program_id,
                "title": x.top_program_title,
                "university": x.top_university,
                "country": x.top_country,
                "city": x.top_city,
            },
            "prob": x.prob,
            "low": x.prob_low,
            "high": x.prob_high,
            "risks": x.risks or [],
            "improvements": x.improvements or [],
            "results": x.results,          # 前端可用来展开更多详情
            "input": x.input_payload,      # 可选：用于“再次评估”预填
        }

    return jsonify({"items": [to_dict(i) for i in items]})

# ---------- 我的预测结果：最近一次 ----------
@profile_bp.get("/api/me/assessment-results/latest")
@jwt_required()
def latest_assessment_result():
    uid = _current_user_id()
    if not uid:
        return jsonify({"msg": "Unauthorized"}), 401

    x = AssessmentResult.query.filter_by(user_id=uid).order_by(AssessmentResult.created_at.desc()).first()
    if not x:
        return jsonify({})

    return jsonify({
        "id": x.id,
        "created_at": x.created_at.isoformat() if x.created_at else None,
        "top": {
            "program_id": x.top_program_id,
            "title": x.top_program_title,
            "university": x.top_university,
            "country": x.top_country,
            "city": x.top_city,
        },
        "prob": x.prob,
        "low": x.prob_low,
        "high": x.prob_high,
        "risks": x.risks or [],
        "improvements": x.improvements or [],
        "results": x.results,
        "input": x.input_payload,
    })
