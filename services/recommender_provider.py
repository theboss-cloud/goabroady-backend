# services/recommender_provider.py
"""
统一的推荐模型入口。

当前使用 PseudoRecommender（规则 + 伪随机），
未来如果切换为深度学习 / 神经网络，只需要在本文件中
替换 get_recommender() / score_candidate() 的实现，
业务层（assessment_service 等）代码无需修改。
"""
from __future__ import annotations

from typing import Tuple, Dict, Any
import os

from models.recommender.pseudo import PseudoRecommender, Candidate, InputPref

# 全局单例，避免每次请求都重新构造模型对象（后续可换成加载大模型等）
_model: PseudoRecommender | None = None


def get_recommender() -> PseudoRecommender:
    """根据环境变量选择具体模型，目前仅支持 'pseudo'。"""
    global _model
    if _model is not None:
        return _model

    backend = os.getenv("RECOMMENDER_BACKEND", "pseudo").lower()
    if backend == "pseudo":
        _model = PseudoRecommender()
    else:
        # 兜底：未知配置时仍然使用伪模型，避免线上报错
        _model = PseudoRecommender()
    return _model


def score_candidate(cand: Candidate, pref: InputPref) -> Tuple[float, Dict[str, Any]]:
    """对单个候选项目打分并给出解释。

    - cand: 候选项目（由 assessment_service._program_to_candidate 构造）
    - pref: 用户偏好与特征（由 assessment_service 构造的 InputPref）

    返回 (score, explain_dict)，其中：
    - score: 0~1 之间的浮点数
    - explain_dict: { 'low', 'high', 'risks', 'improvements', 'basis', ... }
    """
    model = get_recommender()
    return model.score(cand, pref)
