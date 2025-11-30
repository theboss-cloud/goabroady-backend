# routes/assessments.py
from __future__ import annotations
from flask import Blueprint, request, jsonify, current_app
from uuid import uuid4
from typing import Any, Dict, List
from werkzeug.exceptions import BadRequest
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from extensions import db

from models.program import Program, ProgramRequirement
from models.assessment_result import AssessmentResult  # 确认字段见下
from services.assessment_service import recommend_programs

assessment_bp = Blueprint("assessment", __name__, url_prefix="/api/assessments")

# ---------- helpers ----------
def _json_obj() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        raise BadRequest("Invalid or missing JSON body.")
    return data

def _ok(payload: Dict[str, Any], status: int = 200):
    return jsonify(payload), status

def _err(message: str, status: int = 400):
    return jsonify({"error": message}), status

def _num(v, default=None):
    try:
        if v is None: return default
        n = float(v)
        if n != n:   # NaN
            return default
        return n
    except Exception:
        return default

def _first(arr) -> Dict[str, Any]:
    return (arr[0] if isinstance(arr, list) and arr else {}) or {}

def _extract_summary_from_top(top: Dict[str, Any]) -> Dict[str, Any]:
    """
    兼容多种字段名：prob/percent/score、low/high/ci_low/ci_high、risks/factors/explain.risks 等
    """
    explain = top.get("explain") or {}
    prob = (_num(top.get("prob"))
            or (_num(top.get("percent"))/100 if _num(top.get("percent")) is not None else None)
            or _num(top.get("score")))
    low  = _num(top.get("low")) or _num(top.get("ci_low")) or _num(explain.get("low"))
    high = _num(top.get("high")) or _num(top.get("ci_high")) or _num(explain.get("high"))

    risks = top.get("risks") or top.get("factors") or explain.get("risks") or []
    improvements = top.get("improvements") or explain.get("improvements") or []

    prog = top.get("program") or {}
    top_dict = {
        "program_id": prog.get("id") or top.get("program_id") or top.get("id"),
        "title": prog.get("title") or top.get("title") or top.get("program_name") or "",
        "university": prog.get("university") or top.get("university") or "",
        "country": prog.get("country") or top.get("country") or "",
        "city": prog.get("city") or top.get("city") or "",
    }
    return {
        "prob": prob, "low": low, "high": high,
        "risks": [str(x) for x in (risks or [])][:8],
        "improvements": [str(x) for x in (improvements or [])][:8],
        "top": top_dict
    }

# ---------- 提交评估 ----------
@assessment_bp.post("/submit")
def submit_assessment():
    try:
        data = _json_obj()
        features    = data.get("features")    or {}
        preferences = data.get("preferences") or {}
        filters     = data.get("filters")     or {}
        topk_raw    = data.get("topk", 10)
        anon_sid    = data.get("anon_session_id")

        try: topk = int(topk_raw)
        except Exception: topk = 10
        topk = max(1, min(topk, 50))

        out = recommend_programs(
            features=features,
            preferences=preferences,
            filters=filters,
            topk=topk,
        )
        # 透传 anon_session_id，便于前端 claim
        meta = out.get("meta") or {}
        meta["anon_session_id"] = anon_sid
        out["meta"] = meta
        return _ok(out)
    except BadRequest as e:
        return _err(str(e), status=400)
    except Exception:
        current_app.logger.exception("submit_assessment failed")
        return _err("Internal error in assessment submit.", status=500)

# ---------- 匿名会话开始 ----------
@assessment_bp.post("/start")
def start_assessment():
    try:
        anon_sid = str(uuid4())
        # 建议扁平返回；为兼容旧前端，也可以多返回一个 data 包装
        return _ok({"anon_session_id": anon_sid, "data": {"anon_session_id": anon_sid}})
    except Exception:
        current_app.logger.exception("start_assessment failed")
        return _err("Internal error starting assessment.", status=500)

# ---------- 登录后归档 ----------
@assessment_bp.post("/claim")
@jwt_required(optional=True)
def claim_assessment():
    """
    统一契约（推荐）：
      { anon_session_id: str, input?: object, results?: array }
    行为：
      - 校验 anon_session_id 存在
      - 登录用户：幂等落库（user_id + anon_session_id 唯一）
      - 未登录：直接 200 ok，不写库（前端也能继续流程）
    """
    try:
        ident = get_jwt_identity()
        user_id = ident["id"] if isinstance(ident, dict) and "id" in ident else ident

        data = _json_obj()
        anon_sid = (data.get("anon_session_id") or "").strip()
        if not anon_sid:
            return _err("anon_session_id is required", status=422)

        input_payload = data.get("input") or {}
        results: List[Dict[str, Any]] = data.get("results") or []

        # 未登录：不报错，直接返回 ok，以提升体验稳定性
        if not user_id:
            return _ok({"ok": True, "saved_id": None, "duplicate": False})

        # 幂等：同一 user + anon_session_id 只写一次
        existed = (AssessmentResult.query
                   .filter_by(user_id=int(user_id), anon_session_id=anon_sid)
                   .first())
        duplicate = existed is not None

        # 由后端提取 summary，抹平字段差异
        top = _first(results)
        summary = _extract_summary_from_top(top)

        if not duplicate:
            row = AssessmentResult(
                user_id=int(user_id),
                anon_session_id=anon_sid,           # 需要模型有这个字段 & 唯一索引
                input_payload=input_payload,        # 需要模型有 JSON 字段 input_payload
                results=results,                    # JSON
                top_program_id=summary["top"]["program_id"],
                top_program_title=summary["top"]["title"],
                top_university=summary["top"]["university"],
                top_country=summary["top"]["country"],
                top_city=summary["top"]["city"],
                prob=_num(summary["prob"]),
                prob_low=_num(summary["low"]),
                prob_high=_num(summary["high"]),
                risks=summary["risks"],
                improvements=summary["improvements"],
            )
            db.session.add(row)
            db.session.commit()
            saved = row
        else:
            saved = existed

        latest = {
            "id": saved.id,
            "prob": saved.prob,
            "low": saved.prob_low,
            "high": saved.prob_high,
            "risks": saved.risks or [],
            "improvements": saved.improvements or [],
            "top": {
                "program_id": saved.top_program_id,
                "title": saved.top_program_title,
                "university": saved.top_university,
                "country": saved.top_country,
                "city": saved.top_city,
            },
            "created_at": getattr(saved, "created_at", None).isoformat() if getattr(saved, "created_at", None) else None,
        }
        return _ok({"ok": True, "saved_id": saved.id, "duplicate": duplicate, "latest": latest})

    except BadRequest as e:
        return _err(str(e), status=400)
    except Exception:
        current_app.logger.exception("claim_assessment failed")
        return _err("Internal error in claim.", status=500)

# ---------- 调试 ----------
@assessment_bp.post("/_debug_counts")
def debug_counts():
    try:
        total = Program.query.count()
        by_country = dict(Program.query.with_entities(Program.country, func.count(Program.id)).group_by(Program.country).all())
        by_disc = dict(Program.query.with_entities(Program.discipline, func.count(Program.id)).group_by(Program.discipline).all())
        by_degree = dict(Program.query.with_entities(Program.degree_level, func.count(Program.id)).group_by(Program.degree_level).all())
        req_types = dict(ProgramRequirement.query.with_entities(ProgramRequirement.req_type, func.count(ProgramRequirement.id)).group_by(ProgramRequirement.req_type).all())
        return _ok({"program_total": total, "by_country": by_country, "by_discipline": by_disc, "by_degree_level": by_degree, "requirement_types": req_types})
    except Exception:
        current_app.logger.exception("_debug_counts failed")
        return _err("Internal error in debug_counts.", status=500)

@assessment_bp.post("/_debug_probe")
def debug_probe():
    try:
        data = _json_obj()
        filters = data.get("filters") or {}
        q = Program.query.options(joinedload(Program.requirements))
        if filters.get("country"): q = q.filter(Program.country.in_(filters["country"]))
        if filters.get("discipline"): q = q.filter(Program.discipline.in_(filters["discipline"]))
        if filters.get("degree_level"): q = q.filter(Program.degree_level.in_(filters["degree_level"]))
        sample = q.limit(5).all()
        try: count_est = q.count()
        except Exception: count_est = None
        return _ok({"filtered_count_est": count_est, "sample": [{"id": p.id, "title": p.title, "discipline": p.discipline, "country": p.country} for p in sample]})
    except BadRequest as e:
        return _err(str(e), status=400)
    except Exception:
        current_app.logger.exception("_debug_probe failed")
        return _err("Internal error in debug_probe.", status=500)
