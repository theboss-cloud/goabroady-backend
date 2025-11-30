# routes/media_public.py
import os
from flask import Blueprint, send_from_directory, jsonify, abort

# 媒体根目录：优先读环境变量，默认 /srv/goabroady/media
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", "/srv/goabroady/media")

media_public_bp = Blueprint("media_public", __name__)

@media_public_bp.get("/media/ping")
def media_ping():
    return jsonify({"ok": True, "root": MEDIA_ROOT})

@media_public_bp.route("/media/<path:subpath>")
def media_serve(subpath: str):
    # 简单防护：不允许越权访问
    if ".." in subpath or subpath.startswith("/"):
        abort(400)
    return send_from_directory(MEDIA_ROOT, subpath, conditional=True)
