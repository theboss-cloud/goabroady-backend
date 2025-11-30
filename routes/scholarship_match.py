# routes/scholarship_match.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.program import Program

scholar_bp = Blueprint("scholar_bp", __name__, url_prefix="/api")

@scholar_bp.post("/scholarships/match")
@jwt_required(optional=True)
def match():
    cond = request.get_json(force=True) or {}
    degree = cond.get("degree")
    country = cond.get("country") or cond.get("target_country")
    # naive match: pick programs with scholarships_md and optional country filter
    q = Program.query
    if country:
        q = q.filter(Program.country == country)
    items = []
    for p in q.limit(100).all():
        if (p.scholarships_md or "").strip():
            items.append({
                "slug": p.slug,
                "title": p.title,
                "university": p.university,
                "country": p.country,
                "city": p.city,
                "scholarships_md": p.scholarships_md,
            })
    return jsonify({"items": items, "coverage": 0.75})
