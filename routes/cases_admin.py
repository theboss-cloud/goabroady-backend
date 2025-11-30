from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from extensions import db
from models.case_study import CaseStudy

cases_admin_bp = Blueprint("cases_admin", __name__, url_prefix="/api/admin")

def has_role(required, roles):
    if isinstance(roles, str): roles = [roles]
    s = set([r.lower() for r in roles or []])
    return any(r in s for r in [x.lower() for x in required])

def role_required(*required_roles):
    def deco(fn):
        def wrapper(*args, **kwargs):
            claims = get_jwt() or {}
            roles = claims.get("roles") or claims.get("role") or []
            if not has_role(required_roles, roles):
                return jsonify({"code":"FORBIDDEN","message":"insufficient role"}), 403
            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        return jwt_required()(wrapper)
    return deco

@cases_admin_bp.get("/cases")
@role_required("admin","superadmin","staff")
def admin_list_cases():
    q = CaseStudy.query.order_by(CaseStudy.order.desc(), CaseStudy.created_at.desc())
    return jsonify({"items": [c.to_dict() for c in q.all()]})

@cases_admin_bp.post("/cases")
@role_required("admin","superadmin","staff")
def admin_create_case():
    data = request.get_json(force=True) or {}
    c = CaseStudy(**{k: data.get(k) for k in [
        "title","student_alias","target_university","target_program","outcome",
        "highlights","cover_image","tags","status","order"
    ]})
    db.session.add(c); db.session.commit()
    return jsonify(c.to_dict())

@cases_admin_bp.put("/cases/<int:cid>")
@role_required("admin","superadmin","staff")
def admin_update_case(cid):
    c = CaseStudy.query.get_or_404(cid)
    data = request.get_json(force=True) or {}
    for k in ("title","student_alias","target_university","target_program",
              "outcome","highlights","cover_image","tags","status","order"):
        if k in data: setattr(c, k, data[k])
    db.session.commit()
    return jsonify(c.to_dict())

@cases_admin_bp.delete("/cases/<int:cid>")
@role_required("admin","superadmin")
def admin_delete_case(cid):
    c = CaseStudy.query.get_or_404(cid)
    db.session.delete(c); db.session.commit()
    return jsonify({"msg":"deleted"})
