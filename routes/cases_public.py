from flask import Blueprint, request, jsonify
from models.case_study import CaseStudy

cases_public_bp = Blueprint("cases_public", __name__)

@cases_public_bp.get("/api/cases")
def list_cases_public():
    limit = int(request.args.get("limit", 6))
    if limit < 1 or limit > 50: limit = 6
    q = CaseStudy.query.filter_by(status="published")\
        .order_by(CaseStudy.order.desc(), CaseStudy.created_at.desc())
    items = [c.to_dict() for c in q.limit(limit).all()]
    return jsonify({"items": items})
