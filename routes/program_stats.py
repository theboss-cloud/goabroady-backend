from flask import Blueprint, jsonify
from sqlalchemy import func
from models.program import Program
from extensions import db

program_stats_bp = Blueprint("program_stats", __name__)

@program_stats_bp.get("/api/programs/stats/country")
def stats_by_country():
    rows = db.session.query(Program.country, func.count(Program.id))\
        .filter(Program.status == "published")\
        .group_by(Program.country).all()
    return jsonify({"items": [{"country": c or "Unknown", "count": int(n)} for c, n in rows]})
