# models/recommender/pseudo.py
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import random

@dataclass
class Candidate:
    id: int
    title: str
    university: str
    country: str
    city: str
    discipline: str
    degree_level: str
    tuition: float | None
    gpa_min: float | None
    ielts_min: float | None
    gre_min: float | None

@dataclass
class InputPref:
    system_recommend: bool
    preferred_regions: List[str]
    preferred_schools: List[str]
    preferred_programs: List[str]
    features: Dict[str, Any]  # {'gpa':..., 'ielts':..., 'gre':...}

class PseudoRecommender:
    """占位伪模型：差距(硬性要求) + 偏好(可选) + 轻噪声，输出(0..1)及解释。"""
    def __init__(self, seed: int | None = None):
        self._rnd = random.Random(seed)

    def score(self, cand: Candidate, pref: InputPref) -> Tuple[float, Dict[str, Any]]:
        gpa = float(pref.features.get('gpa') or 0)
        ielts = float(pref.features.get('ielts') or 0)
        gre = float(pref.features.get('gre') or 0)

        score, wsum = 0.0, 0.0
        def add(part, w):  # 归一化累加
            nonlocal score, wsum
            score += part * w; wsum += w

        if cand.gpa_min is not None:
            add(max(min((gpa - cand.gpa_min) / 1.0, 1.0), -1.0)*0.5 + 0.5, 0.5)
        if cand.ielts_min is not None:
            add(max(min((ielts - cand.ielts_min) / 2.0, 1.0), -1.0)*0.5 + 0.5, 0.3)
        if cand.gre_min is not None:
            add(max(min((gre - cand.gre_min) / 50.0, 1.0), -1.0)*0.5 + 0.5, 0.2)

        # 偏好（如果前端暂不采集，也不影响）
        pref_bonus = 0.0
        region = f"{cand.country}|{cand.city}".lower()
        if any(r.lower() in region for r in pref.preferred_regions):
            pref_bonus += 0.1
        if any(s.lower() in cand.university.lower() for s in pref.preferred_schools):
            pref_bonus += 0.1
        if any(p.lower() in cand.title.lower() for p in pref.preferred_programs):
            pref_bonus += 0.1
        add(min(pref_bonus, 0.25), 0.25)

        # 轻噪声（打散同分）
        add(self._rnd.uniform(-0.02, 0.02) + 0.5, 0.05)

        final = (score / wsum) if wsum > 0 else 0.5

        # 可解释信息
        risks, improvements = [], []
        if cand.gpa_min and gpa < cand.gpa_min:
            diff = round(cand.gpa_min - gpa, 2)
            risks.append(f"GPA 低于最低要求 {diff} 分（需 ≥ {cand.gpa_min}）")
            improvements.append("提高相关课程平均分，补齐硬性要求")
        if cand.ielts_min and ielts < cand.ielts_min:
            diff = round(cand.ielts_min - ielts, 1)
            risks.append(f"IELTS 低于最低要求 {diff} 分（需 ≥ {cand.ielts_min}）")
            improvements.append("集中刷题与模考，适当报名冲刺班")
        if cand.gre_min and gre < cand.gre_min:
            diff = max(0, int(cand.gre_min - gre))
            if diff > 0:
                risks.append(f"GRE 低于最低要求 {diff} 分（需 ≥ {cand.gre_min}）")
                improvements.append("针对薄弱项（Quant/Verbal/写作）分模块提升")

        explain = {
            "low": max(0, round(final - 0.15, 3)),
            "high": min(1, round(final + 0.15, 3)),
            "risks": risks[:4],
            "improvements": list(dict.fromkeys(improvements))[:4],
            "basis": "伪模型：按与最低要求的差距 + 偏好匹配 + 轻噪声综合评分"
        }
        return max(0.0, min(1.0, round(final, 3))), explain
