# routes/messages.py
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta

from models.application import Application, Material

messages_bp = Blueprint("messages_bp", __name__, url_prefix="/api")

@messages_bp.get("/messages")
@jwt_required(optional=True)
def list_messages():
    # Lightweight virtual message center composed from materials & applications
    user_id = get_jwt_identity()
    items = []
    if user_id:
        apps = Application.query.filter_by(user_id=user_id).all()
        for a in apps:
            # stage message
            items.append({
                "id": f"stage-{a.id}",
                "title": f"申请进度更新：{a.stage}",
                "subtitle": a.title or "",
                "body": f"你的申请【{a.title or a.id}】当前处于「{a.stage}」阶段。",
                "read": False,
                "link": f"/user/applications",
                "created_at": a.started_at.isoformat() if a.started_at else datetime.utcnow().isoformat(),
            })
            # materials due reminders
            mats = Material.query.filter_by(app_id=a.id).all()
            for m in mats:
                if m.due_at and m.status != "approved":
                    items.append({
                        "id": f"mat-{m.id}",
                        "title": f"材料待提交：{m.type}",
                        "subtitle": a.title or "",
                        "body": f"请在 {m.due_at.date()} 前提交 {m.type}。",
                        "read": False,
                        "link": f"/user/materials",
                        "created_at": m.updated_at.isoformat() if m.updated_at else datetime.utcnow().isoformat(),
                    })
    else:
        items.append({
            "id": "login-tip",
            "title": "登录以同步消息",
            "subtitle": "",
            "body": "登录后将为你展示与申请、材料、评估相关的提醒。",
            "read": False,
            "link": "/start?tab=login",
            "created_at": datetime.utcnow().isoformat(),
        })
    return jsonify({"items": items})

@messages_bp.put("/messages/<string:msg_id>/read")
@jwt_required(optional=True)
def mark_read(msg_id):
    # stateless demo endpoint
    return jsonify({"ok": True})
