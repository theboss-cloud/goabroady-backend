from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.program import Program, ProgramRequirement
from models.student_profile import StudentProfile

predict_bp = Blueprint("predict", __name__)

def _float(v, default=None):
    try:
        return float(v)
    except Exception:
        return default

@predict_bp.post("/api/programs/<int:pid>/predict")
@jwt_required()
def predict_program(pid):
    ident = get_jwt_identity()
    uid = ident["id"]

    program = Program.query.get_or_404(pid)
    profile = StudentProfile.query.filter_by(user_id=uid).first()
    if not profile:
        return jsonify({"msg": "请先完善学生画像"}), 400

    # --- 规则版占位打分：根据要求差距计算 0~1 ---
    # 权重可调：GPA 0.4, IELTS 0.4, GRE 0.2
    weights = {"GPA": 0.4, "IELTS": 0.4, "GRE": 0.2}
    req_map = {r.req_type.upper(): r for r in program.requirements}

    score = 0.0
    total_w = 0.0

    # GPA
    if "GPA" in req_map:
        need = _float(req_map["GPA"].min_value)
        if need is not None and profile.gpa is not None:
            s = max(min((profile.gpa - need) + 1.0, 1.0), 0.0)  # 简单映射
            score += s * weights["GPA"]; total_w += weights["GPA"]
    # IELTS
    if "IELTS" in req_map:
        need = _float(req_map["IELTS"].min_value)
        if need is not None and profile.ielts is not None:
            s = max(min((profile.ielts - need) + 1.0, 1.0), 0.0)
            score += s * weights["IELTS"]; total_w += weights["IELTS"]
    # GRE
    if "GRE" in req_map:
        need = _float(req_map["GRE"].min_value)
        if need is not None and profile.gre is not None:
            s = max(min((profile.gre - need) / 50.0, 1.0), 0.0)  # 粗略
            score += s * weights["GRE"]; total_w += weights["GRE"]

    prob = (score / total_w) if total_w > 0 else 0.3  # 无要求时给中性分
    return jsonify({
        "program_id": program.id,
        "user_id": uid,
        "prob": round(prob, 3),     # 0~1
        "percent": int(round(prob*100)),
        "explain": "基于你与最低申请要求（GPA/IELTS/GRE）的差距做的初步估算；仅供参考，不代表录取承诺。"
    })
