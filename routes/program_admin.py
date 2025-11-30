# routes/program_admin.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError
from extensions import db
import json

from models.program import Program, ProgramRequirement

admin_program_bp = Blueprint("admin_program", __name__, url_prefix="/api/admin/programs")

def _parse_gallery(val):
    if val is None:
        return None
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            j = json.loads(s)
            if isinstance(j, list):
                return j
        except Exception:
            return [x.strip() for x in s.split(",") if x.strip()]
    return None

# 动态获取模型列，避免白名单遗漏
MODEL_COLUMNS = set(Program.__table__.columns.keys())

@admin_program_bp.get("")
@jwt_required()
def list_programs():
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 20))
    query = Program.query.order_by(Program.created_at.desc())
    total = query.count()
    items = query.offset((page-1)*size).limit(size).all()
    return jsonify({
        "page": page, "size": size, "total": total,
        "items": [p.to_dict(with_requirements=False) for p in items]
    })

@admin_program_bp.post("")
@jwt_required()
def create_program():
    data = request.get_json() or {}
    p = Program()

    for k, v in data.items():
        if k in MODEL_COLUMNS and k != "id":
            setattr(p, k, v)

    if "gallery_images" in data:
        p.gallery_images = _parse_gallery(data.get("gallery_images"))

    # requirements
    for r in data.get("requirements") or []:
        db.session.add(ProgramRequirement(
            program=p,
            req_type=r.get("req_type"),
            min_value=r.get("min_value"),
            note=r.get("note")
        ))
    try:
        db.session.add(p)
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"msg": "slug 已存在或字段非法", "error": str(e)}), 400

    return jsonify({"msg": "created", "program": p.to_dict()}), 201

@admin_program_bp.put("/<int:pid>")
@jwt_required()
def update_program(pid):
    p = Program.query.get_or_404(pid)
    data = request.get_json() or {}

    for k, v in data.items():
        if k in MODEL_COLUMNS and k not in ("id", "created_at", "updated_at"):
            setattr(p, k, v)

    if "gallery_images" in data:
        p.gallery_images = _parse_gallery(data.get("gallery_images"))

    # 简单做法：重建 requirements
    if "requirements" in data:
        ProgramRequirement.query.filter_by(program_id=p.id).delete()
        for r in data.get("requirements") or []:
            db.session.add(ProgramRequirement(
                program=p,
                req_type=r.get("req_type"),
                min_value=r.get("min_value"),
                note=r.get("note")
            ))

    db.session.commit()
    return jsonify({"msg": "updated", "program": p.to_dict()}), 200

@admin_program_bp.delete("/<int:pid>")
@jwt_required()
def delete_program(pid):
    p = Program.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    return jsonify({"msg": "deleted"}), 200

@admin_program_bp.post("/<int:pid>/publish")
@jwt_required()
def publish_program(pid):
    p = Program.query.get_or_404(pid)
    p.status = "published"
    db.session.commit()
    return jsonify({"msg": "ok", "status": p.status})

@admin_program_bp.post("/<int:pid>/unpublish")
@jwt_required()
def unpublish_program(pid):
    p = Program.query.get_or_404(pid)
    p.status = "draft"
    db.session.commit()
    return jsonify({"msg": "ok", "status": p.status})
