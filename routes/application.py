# routes/application.py
from flask import Blueprint, request, jsonify
from datetime import datetime

from extensions import db
from models.application import Application, ApplicationStage, Material, STAGES

# 可选导入：如果你有 Student / Program 模型，就会用到
try:
    from models.student import Student  # 假如你的 student 表是这样命名
except Exception:
    Student = None

try:
    from models.program import Program  # 假如你的 program 表是这样命名
except Exception:
    Program = None

# JWT：用于解析当前登录用户身份
from flask_jwt_extended import jwt_required, get_jwt_identity

application_bp = Blueprint("application_bp", __name__)

# ---------- 工具：把用户 id 映射为 student_id ----------
def resolve_student_id_from_uid(uid: int | str):
    """
    如果你的业务里 "学生" 与 "用户" 是一对一/一对多，请在这里做映射。
    目前策略：
      - 有 Student 模型且存在 user_id 字段：用 user_id 去 Student 表找 id
      - 否则直接把 uid 当做 student_id 用（和你当前 Application.student_id 字段对齐）
    """
    # 显式转 int 防守
    try:
        uid = int(uid)
    except Exception:
        pass

    if Student is not None:
        try:
            s = Student.query.filter_by(user_id=uid).first()
            if s:
                return s.id
        except Exception:
            # 表结构可能不匹配，忽略异常，走兜底
            pass

    # 兜底：直接用 uid 当 student_id
    return uid


# ======================================================
# ================ 后台管理接口（保留） =================
# ======================================================

@application_bp.route("/api/apps", methods=["POST"])
@jwt_required()  # 可按需决定是否需要后台权限校验
def create_app():
    data = request.get_json(force=True) or {}
    student_id = data.get("student_id")
    program_id = data.get("program_id")

    if not student_id or not program_id:
        return jsonify({"code": 400, "message": "student_id & program_id required"}), 400

    app_obj = Application(student_id=student_id, program_id=program_id, current_stage="ai_intent")
    db.session.add(app_obj)
    db.session.flush()  # 拿到 id

    stage = ApplicationStage(app_id=app_obj.id, stage="ai_intent", status="active")
    db.session.add(stage)
    db.session.commit()
    return jsonify({"code": 0, "data": {"id": app_obj.id}})


@application_bp.route("/api/apps", methods=["GET"])
@jwt_required()  # 可按需决定是否需要后台权限校验
def list_apps():
    q = Application.query
    student_id = request.args.get("student_id", type=int)
    program_id = request.args.get("program_id", type=int)
    stage = request.args.get("stage")

    if student_id:
        q = q.filter_by(student_id=student_id)
    if program_id:
        q = q.filter_by(program_id=program_id)
    if stage:
        q = q.filter_by(current_stage=stage)

    rows = q.order_by(Application.updated_at.desc()).all()
    data = [{
        "id": r.id,
        "student_id": r.student_id,
        "program_id": r.program_id,
        "current_stage": r.current_stage,
        "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        "updated_at": r.updated_at.isoformat() if getattr(r, "updated_at", None) else None
    } for r in rows]
    return jsonify({"code": 0, "data": data})


@application_bp.route("/api/apps/<int:app_id>/stage", methods=["PUT"])
@jwt_required()  # 可按需决定是否需要后台权限校验
def move_stage(app_id):
    data = request.get_json(force=True) or {}
    to_stage = data.get("to_stage")
    if to_stage not in STAGES:
        return jsonify({"code": 400, "message": f"to_stage must be in {STAGES}"}), 400

    app_obj = Application.query.get_or_404(app_id)
    if app_obj.current_stage == to_stage:
        return jsonify({"code": 0, "message": "noop", "data": {"id": app_obj.id, "current_stage": app_obj.current_stage}})

    # 完成旧阶段
    old_stage = ApplicationStage.query.filter_by(app_id=app_id, stage=app_obj.current_stage, status="active").first()
    if old_stage:
        old_stage.status = "done"
        old_stage.completed_at = datetime.utcnow()

    # 激活新阶段（无则创建）
    new_stage = ApplicationStage.query.filter_by(app_id=app_id, stage=to_stage).first()
    if not new_stage:
        new_stage = ApplicationStage(app_id=app_id, stage=to_stage, status="active")
        db.session.add(new_stage)
    else:
        new_stage.status = "active"
        new_stage.started_at = new_stage.started_at or datetime.utcnow()

    app_obj.current_stage = to_stage
    db.session.commit()

    return jsonify({"code": 0, "data": {"id": app_obj.id, "current_stage": app_obj.current_stage}})


# ======================================================
# ================ 前台用户中心接口（新增）===============
# ======================================================

@application_bp.route("/api/applications", methods=["GET"])
@jwt_required()
def list_my_applications():
    """
    前端用户中心 Overview 使用：
      GET /api/applications?mine=1
    返回:
      { "items": [{ id, program_title, university, status, deadline }, ...] }
    """
    mine = request.args.get("mine")
    if str(mine) != "1":
        # 目前只支持 mine=1，其他查询按需扩展
        return jsonify({"items": []})

    uid = get_jwt_identity()
    student_id = resolve_student_id_from_uid(uid)

    q = Application.query.filter_by(student_id=student_id).order_by(Application.updated_at.desc()).all()

    items = []
    for r in q:
        # 默认值
        title = f"Program #{r.program_id}" if getattr(r, "program_id", None) else "未知项目"
        uni = "-"
        deadline = None

        # 如果 ORM 配了关系或能查到 Program，就补全一下展示字段
        # 1) 尝试一：Application 有 relationship: r.program
        prog = getattr(r, "program", None)
        if prog is not None:
            try:
                if hasattr(prog, "title") and prog.title:
                    title = prog.title
                if hasattr(prog, "university") and prog.university:
                    uni = prog.university
                # 你若有 deadline 字段可加：
                if hasattr(prog, "deadline") and prog.deadline:
                    try:
                        deadline = prog.deadline.isoformat()
                    except Exception:
                        deadline = str(prog.deadline)
            except Exception:
                pass
        # 2) 尝试二：没有关系但有 Program 模型，按 id 再查一下
        elif Program is not None and getattr(r, "program_id", None):
            try:
                p = Program.query.get(r.program_id)
                if p:
                    if hasattr(p, "title") and p.title:
                        title = p.title
                    if hasattr(p, "university") and p.university:
                        uni = p.university
                    if hasattr(p, "deadline") and p.deadline:
                        try:
                            deadline = p.deadline.isoformat()
                        except Exception:
                            deadline = str(p.deadline)
            except Exception:
                pass

        items.append({
            "id": r.id,
            "program_title": title,
            "university": uni,
            "status": r.current_stage,  # 你可以在前端映射成更友好的文本
            "deadline": deadline,
        })

    return jsonify({"items": items})
