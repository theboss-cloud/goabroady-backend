import os
import time
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from flask_jwt_extended import jwt_required
# 如果你还需要保留原来的 role_required，请保留引入
from routes.auth import role_required 

upload_bp = Blueprint("upload", __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# === 新增：用户头像上传接口 (用于个人资料页) ===
@upload_bp.route('/api/upload/image', methods=['POST'])
@jwt_required()
def upload_image():
    if 'file' not in request.files:
        return jsonify({'msg': '没有文件部分'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'msg': '未选择文件'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # 重命名防止冲突: timestamp_filename
        filename = f"{int(time.time())}_{filename}"
        
        # 确保 upload 文件夹存在
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        file.save(os.path.join(upload_folder, filename))
        
        # 返回访问 URL
        url = f"/static/uploads/{filename}" 
        return jsonify({'url': url, 'msg': '上传成功'})
        
    return jsonify({'msg': '不支持的文件格式'}), 400

# === 保留：原有的 Admin 占位接口 ===
@upload_bp.post("/api/admin/upload/policy")
@role_required("admin", "superadmin")
def oss_policy():
    return jsonify({
        "upload": "placeholder",
        "message": "下一轮接入阿里云STS/服务端签名。现在请直接把图片推到你可访问的CDN/本地静态服务器，并回填URL。"
    })