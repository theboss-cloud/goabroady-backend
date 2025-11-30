# routes/tasks.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db

# 档案模型（用于判断“是否需要完善个人资料”）
try:
    from models.student_profile import StudentProfile
except Exception:  # 万一模型名改了，也不至于整个接口炸掉
    StudentProfile = None

# 申请 & 材料 & 项目模型（用于生成材料任务）
from models.application import Application, Material
from models.program import Program

tasks_bp = Blueprint("tasks_bp", __name__, url_prefix="/api")


def _current_user_id():
    """从 JWT identity 中解析当前用户 id，兼容 int / str / dict 三种情况。"""
    ident = get_jwt_identity()
    if ident is None:
        return None
    if isinstance(ident, dict):
        return ident.get("id") or ident.get("user_id")
    try:
        return int(ident)
    except Exception:
        return None


def _build_profile_task(uid):
    """
    根据档案完整度构建一条“完善个人资料”的任务（如有必要）。
    没档案 / 关键字段缺失时才生成。
    """
    if StudentProfile is None or uid is None:
        return None

    prof = db.session.query(StudentProfile).filter_by(user_id=uid).first()

    # 没有档案 → 强烈建议先补档案
    if not prof:
        return {
            "id": 1000,
            "text": "完善个人资料",
            "note": "先补充 GPA、专业、毕业年份、目标国家和英语成绩，后续推荐会更准确。",
            "done": False,
        }

    # 简单检查几个核心字段
    missing_labels = []
    field_labels = [
        ("gpa", "GPA"),
        ("major", "本科专业"),
        ("grad_year", "毕业/预计毕业年份"),
        ("target_country", "目标国家"),
        ("english_score", "英语成绩"),
    ]
    for field, label in field_labels:
        val = getattr(prof, field, None)
        if val is None or (isinstance(val, str) and not val.strip()):
            missing_labels.append(label)

    # 全都不缺 → 不生成“完善档案”任务
    if not missing_labels:
        return None

    # 只展示前几个字段名称，避免太长
    if len(missing_labels) > 3:
        note = "建议优先补充：" + "、".join(missing_labels[:3]) + " 等关键信息。"
    else:
        note = "建议补充：" + "、".join(missing_labels) + "。"

    return {
        "id": 1000,
        "text": "完善个人资料",
        "note": note,
        "done": False,
    }


def _build_material_tasks(uid):
    """
    根据 materials 构建上传/检查材料的任务列表。
    每一条 Material → 一条任务（带项目名称）。
    """
    if uid is None:
        return []

    q = (
        db.session.query(Material, Application, Program)
        .join(Application, Material.app_id == Application.id)
        .join(Program, Application.program_id == Program.id)
        .filter(Application.student_id == uid)
        .order_by(Material.due_at.asc())
    )

    tasks = []
    base_id = 2000
    for mat, app, prog in q:
        # 文案友好一点
        type_label = mat.type or "申请材料"
        prog_title = prog.title or ""
        uni = prog.university or prog.university_cn or ""
        title_parts = []
        if uni:
            title_parts.append(uni)
        if prog_title:
            title_parts.append(prog_title)
        title_str = " · ".join(title_parts) if title_parts else "目标项目"

        # 认为以下情况算“已完成”：已上传且不是 missing，或者 status=approved
        done = False
        status = getattr(mat, "status", None)
        file_url = getattr(mat, "file_url", None)
        if status == "approved":
            done = True
        elif file_url and status != "missing":
            done = True

        note = "已上传，等待顾问或学校审核。" if done else "前往「文档材料」上传或检查这一项。"

        tasks.append(
            {
                "id": base_id,
                "text": f"{type_label} - {title_str}",
                "note": note,
                "done": done,
            }
        )
        base_id += 1

    return tasks


@tasks_bp.get("/me/tasks")
@jwt_required(optional=True)
def list_tasks():
    """
    返回当前用户的任务清单：
      - 一条“完善个人资料”的智能任务（如有需要）
      - 若干条基于 materials 的上传/检查任务

    未登录则返回空列表（/user 本身已经需要登录）。
    """
    uid = _current_user_id()
    if not uid:
        return jsonify({"items": []})

    items = []

    profile_task = _build_profile_task(uid)
    if profile_task:
        items.append(profile_task)

    items.extend(_build_material_tasks(uid))

    return jsonify({"items": items})


@tasks_bp.put("/me/tasks/<int:task_id>")
@jwt_required(optional=True)
def toggle_task(task_id):
    """
    目前任务是由后端实时根据档案和材料生成的，
    不直接在 DB 中存储“完成”状态。

    因此这里不修改数据库，只是回显前端传入的 done 状态，保证接口兼容。
    将来如果引入独立 Task 表，可在此处做真正的持久化。
    """
    data = request.get_json(force=True) or {}
    done = bool(data.get("done"))
    return jsonify({"ok": True, "item": {"id": task_id, "done": done}})
