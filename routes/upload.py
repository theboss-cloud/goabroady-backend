from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from routes.auth import role_required

upload_bp = Blueprint("upload", __name__)

@upload_bp.post("/api/admin/upload/policy")
@role_required("admin", "superadmin")
def oss_policy():
    # 冲刺2先返回假数据占位；下一轮接入阿里云STS或服务端签名
    # 前端可以用本地上传，拿到 URL 回填到 hero/intro 字段
    return jsonify({
        "upload": "placeholder",
        "message": "下一轮接入阿里云STS/服务端签名。现在请直接把图片推到你可访问的CDN/本地静态服务器，并回填URL。"
    })
