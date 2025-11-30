from flask import Blueprint, jsonify

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")

@dashboard_bp.route("/stats", methods=["GET"])
def get_stats():
    # 示例数据，先跑通，之后可改成数据库统计
    return jsonify({
        "code": 0,
        "data": {
            "degree_total": 120,   # 需求人数
            "published": 87,       # 提问数量
            "students": 320,       # 解决数量
            "visits_7d": 550       # 用户满意度（示例）
        }
    })

@dashboard_bp.route("/trend", methods=["GET"])
def get_trend():
    return jsonify({
        "code": 0,
        "data": {
            "labels": ["周一","周二","周三","周四","周五","周六","周日"],
            "data1": [2000,2800,2600,4000,5200,6100,7800],
            "data2": [1800,2300,2400,3200,4100,4800,5600]
        }
    })

@dashboard_bp.route("/latest", methods=["GET"])
def get_latest():
    return jsonify({
        "code": 0,
        "data": [
            {"date":"2025-08-08","new_students":30,"new_projects":5},
            {"date":"2025-08-07","new_students":22,"new_projects":4}
        ]
    })
