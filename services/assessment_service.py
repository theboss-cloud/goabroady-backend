from typing import Dict, Any, List, Tuple
import re
from sqlalchemy.orm import joinedload
from models.program import Program, ProgramRequirement
from models.recommender.pseudo import Candidate, InputPref
from services.recommender_provider import score_candidate

_gpa_num_re = re.compile(r"([\d\.]+)\s*/\s*([\d\.]+)")
_num_re = re.compile(r"^\s*([\d\.]+)\s*$")

def _parse_gpa_min(val) -> float | None:
    """
    支持 '2.7/4.0', '85/100', '3.0', 3, 以及 '2.8 / 5' 等，统一换算成 4 分制。
    """
    if val is None:
        return None
    s = str(val)
    m = _gpa_num_re.match(s)
    if m:
        num = float(m.group(1)); den = float(m.group(2))
        if den > 0:
            return round((num / den) * 4.0, 3)
    m2 = _num_re.match(s)
    if m2:
        # 如果是纯数字，默认已经是 4 分制（最多 4.0）
        v = float(m2.group(1))
        # 如果明显 > 4，可能是百分制，按 100 转 4
        if v > 5:
            return round((v / 100.0) * 4.0, 3)
        return v
    return None

def _as_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except Exception:
        return None

def _program_to_candidate(p: Program) -> Candidate:
    req_map = {r.req_type: r for r in (p.requirements or [])}
    gpa_min = req_map.get("GPA").min_value if req_map.get("GPA") else None
    ielts_min = req_map.get("IELTS").min_value if req_map.get("IELTS") else None
    gre_min = req_map.get("GRE").min_value if req_map.get("GRE") else None
    return Candidate(
        id=p.id,
        title=p.title or "",
        university=p.university or "",
        country=p.country or "",
        city=p.city or "",
        discipline=p.discipline or "",
        degree_level=p.degree_level or "",
        tuition=p.tuition,
        gpa_min=_parse_gpa_min(gpa_min),
        ielts_min=_as_float(ielts_min),
        gre_min=_as_float(gre_min),
    )

def _card(p: Program, score: float, expl: dict, featured=False, rank=1) -> Dict[str, Any]:
    return {
        "rank": rank,
        "featured": featured,
        "prob": score,
        "percent": int(round(score * 100)),
        "program": {
            "id": p.id,
            "slug": p.slug,
            "title": p.title,
            "university": p.university,
            "city": p.city,
            "country": p.country,
            "degree_level": p.degree_level,
            "discipline": p.discipline,
            "cover_image": getattr(p, "cover_image", None),
            "hero_image_url": getattr(p, "hero_image_url", None),
            "overview_brief": getattr(p, "overview_brief", None),
        },
        "explain": {
            "low": expl.get("low"),
            "high": expl.get("high"),
            "risks": expl.get("risks"),
            "improvements": expl.get("improvements"),
            "basis": expl.get("basis"),
        },
    }

def _apply_filters(base_q, filters: Dict[str, Any]):
    q = base_q
    # 轻过滤：只应用非空的
    if filters.get("country"):
        q = q.filter(Program.country.in_(filters["country"]))
    if filters.get("discipline"):
        q = q.filter(Program.discipline.in_(filters["discipline"]))
    if filters.get("degree_level"):
        q = q.filter(Program.degree_level.in_(filters["degree_level"]))
    return q

def recommend_programs(
    features: Dict[str, Any],
    preferences: Dict[str, Any] | None = None,
    filters: Dict[str, Any] | None = None,
    topk: int = 10,
) -> Dict[str, Any]:
    preferences = preferences or {}
    filters = filters or {}
    topk = max(1, min(int(topk or 10), 50))  # 合理上限

    # 1) 读取候选（预加载 requirements 避免 N+1）
    base_q = Program.query.options(joinedload(Program.requirements))

    # 先按用户过滤获取候选
    q = _apply_filters(base_q, filters)
    programs = q.limit(1000).all()

    # 如果过滤后 0 条，自动放宽（逐步去掉 discipline -> degree_level -> country）
    if not programs:
        relaxed = dict(filters)
        for key in ("discipline", "degree_level", "country"):
            if relaxed.get(key):
                relaxed[key] = []
                q2 = _apply_filters(base_q, relaxed)
                programs = q2.limit(1000).all()
                if programs:
                    filters = relaxed
                    break

    # 2) 转候选 + 打分
    cands = [_program_to_candidate(p) for p in programs]
    pref = InputPref(
        system_recommend=bool(preferences.get("system_recommend", True)),
        preferred_regions=list(preferences.get("regions") or []),
        preferred_schools=list(preferences.get("schools") or []),
        preferred_programs=list(preferences.get("programs") or []),
        features=features or {},
    )

    scored: List[Tuple[Program, float, Dict[str, Any]]] = []
    for p, c in zip(programs, cands):
        s, expl = score_candidate(c, pref)
        scored.append((p, s, expl))


    scored.sort(key=lambda t: t[1], reverse=True)
    top = scored[:topk] if scored else []

    results: List[Dict[str, Any]] = []
    if top:
        results.append(_card(top[0][0], top[0][1], top[0][2], featured=True, rank=1))
        for idx, (p, s, e) in enumerate(top[1:], start=2):
            results.append(_card(p, s, e, featured=False, rank=idx))

    return {
        "results": results,
        "meta": {
            "total": len(scored),
            "returned": len(results),
            "system_recommend": pref.system_recommend,
            "applied_filters": filters,  # 返回实际应用的过滤（便于前端提示“已自动放宽筛选条件”）
        },
    }
