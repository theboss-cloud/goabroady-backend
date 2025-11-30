# routes/image_cache.py
# -*- coding: utf-8 -*-
import os
import logging
import hashlib
import base64
import traceback
from io import BytesIO
from urllib.parse import quote_plus

import requests
from flask import Blueprint, send_file, request, current_app, jsonify

# 你的 Program 模型（按你的项目结构）
from models.program import Program

image_cache_bp = Blueprint("image_cache", __name__)

# ========= 可调配置（环境变量覆盖） =========
# 是否在图片路由里查询数据库（默认关闭，避免 DB 绑定问题导致 500）
USE_DB_IN_IMAGE_ROUTE = os.getenv("IMAGE_CACHE_USE_DB", "0") == "1"
DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "program-images")
PLACEHOLDER_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "placeholder-wide.jpg")
DOWNLOAD_TIMEOUT = int(os.getenv("IMAGE_DL_TIMEOUT", "20"))      # 单次读取超时（秒）
CONNECT_TIMEOUT = int(os.getenv("IMAGE_DL_CONNECT_TIMEOUT", "8"))# 连接超时（秒）
RETRY_TIMES      = int(os.getenv("IMAGE_DL_RETRIES", "3"))       # 每个 URL 重试次数

# 1x1 透明 PNG（内置占位，任何情况下不 404）
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z/CfBwAF/wK1J4qk2gAAAABJRU5ErkJggg=="
)

# ========= 工具：缓存目录/路径 =========
def _cache_dir() -> str:
    d = getattr(current_app, "IMAGE_CACHE_DIR", None) or os.getenv("IMAGE_CACHE_DIR") or DEFAULT_CACHE_DIR
    d = os.path.abspath(d)
    os.makedirs(d, exist_ok=True)
    return d

def _cache_path(slug: str, kind: str) -> str:
    fname = f"{slug}-{kind}.jpg"
    return os.path.join(_cache_dir(), fname)

# ========= 工具：占位发送 =========
def _send_inline_placeholder():
    bio = BytesIO(_TINY_PNG)
    bio.seek(0)
    return send_file(bio, mimetype="image/png", max_age=60 * 60 * 24 * 7)

def _send_or_placeholder(path: str):
    try:
        # 命中本地缓存文件
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return send_file(path, mimetype="image/jpeg", max_age=60 * 60 * 24 * 30)
        # 文件占位图（可选）
        if os.path.exists(PLACEHOLDER_PATH):
            return send_file(PLACEHOLDER_PATH, mimetype="image/jpeg", max_age=60 * 60 * 24 * 7)
    except Exception:
        pass
    # 最终兜底：内置 1x1 PNG，绝不 404
    return _send_inline_placeholder()

# ========= Unsplash / Picsum 提供者 =========
def _normalize_unsplash_image_url(url: str, w: int, h: int) -> str:
    """
    把 images.unsplash.com 的 URL 规范到目标尺寸（裁剪居中）
    """
    if not url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}w={int(w)}&h={int(h)}&fit=crop&crop=faces,edges&auto=compress&q=80"

def _unsplash_api_random(query: str, orientation: str = "landscape") -> str | None:
    """
    官方 API - 随机图，返回 direct URL（regular/full）
    需要环境变量：UNSPLASH_ACCESS_KEY
    """
    key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not key:
        return None
    try:
        r = requests.get(
            "https://api.unsplash.com/photos/random",
            params={"query": query, "orientation": orientation, "content_filter": "high"},
            headers={"Accept-Version": "v1", "Authorization": f"Client-ID {key}"},
            timeout=(CONNECT_TIMEOUT, DOWNLOAD_TIMEOUT),
        )
        if r.status_code != 200:
            logging.warning("unsplash random non-200: %s %s", r.status_code, r.text[:180])
            return None
        data = r.json()
        if isinstance(data, list) and data:
            data = data[0]
        urls = (data.get("urls") or {})
        return urls.get("regular") or urls.get("full")
    except Exception as e:
        logging.warning("unsplash random error: %s", e)
        return None

def _unsplash_api_search_deterministic(query: str, seed: int, orientation: str = "landscape") -> str | None:
    """
    官方 API - search + seed 选第 N 张，保证同一 seed 稳定
    """
    key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not key:
        return None
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "orientation": orientation, "per_page": 30, "content_filter": "high"},
            headers={"Accept-Version": "v1", "Authorization": f"Client-ID {key}"},
            timeout=(CONNECT_TIMEOUT, DOWNLOAD_TIMEOUT),
        )
        if r.status_code != 200:
            logging.warning("unsplash search non-200: %s %s", r.status_code, r.text[:180])
            return None
        results = (r.json() or {}).get("results") or []
        if not results:
            return None
        idx = seed % len(results)
        urls = (results[idx].get("urls") or {})
        return urls.get("regular") or urls.get("full")
    except Exception as e:
        logging.warning("unsplash search error: %s", e)
        return None

def _unsplash_source_url(query: str, w=1600, h=900, sig=None) -> str:
    """
    老的 Heroku Source 入口（不稳定，作为备选）
    """
    q = quote_plus(query)
    sig = f"&sig={sig}" if sig is not None else ""
    return f"https://source.unsplash.com/featured/{int(w)}x{int(h)}/?{q}{sig}"

def _picsum_url(seed: str, w: int, h: int) -> str:
    return f"https://picsum.photos/seed/{quote_plus(seed)}/{int(w)}/{int(h)}"

def _hash_seed(*parts) -> int:
    s = "|".join(str(x) for x in parts)
    return int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16)

def _unsplash_provider_urls(query: str, w: int, h: int, seed: int, orientation: str = "landscape") -> list[str]:
    """
    返回按优先级排列的候选 URL 列表：
    1) 官方 API random（规范化到 w*h）
    2) 官方 API search + seed（稳定，同一 seed 每次同图）
    3) source.unsplash.com（老入口）
    4) picsum.photos（兜底真图）
    """
    urls: list[str] = []

    # 1) random
    api_random = _unsplash_api_random(query, orientation=orientation)
    if api_random:
        urls.append(_normalize_unsplash_image_url(api_random, w, h))

    # 2) deterministic search
    api_search = _unsplash_api_search_deterministic(query, seed=seed, orientation=orientation)
    if api_search:
        urls.append(_normalize_unsplash_image_url(api_search, w, h))

    # 3) source（可能偶发挂）
    urls.append(_unsplash_source_url(query, w, h, sig=seed % 10_000_000))

    # 4) picsum 兜底
    urls.append(_picsum_url(f"{query}-{seed}", w, h))

    return urls

# ========= 下载到文件（多 URL 依次尝试） =========
def _download_to_file(urls: list[str], path: str) -> tuple[bool, str | None]:
    """
    尝试依次下载 urls 中的任一地址，成功写入 path 即返回 True
    """
    # 命中已缓存
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return True, "cached"

    last_err = None
    for u in urls:
        for attempt in range(1, RETRY_TIMES + 1):
            try:
                r = requests.get(u, stream=True, timeout=(CONNECT_TIMEOUT, DOWNLOAD_TIMEOUT))
                if r.status_code != 200:
                    logging.warning("image non-200: %s -> %s", u, r.status_code)
                    raise RuntimeError(f"http {r.status_code}")
                tmp = f"{path}.part"
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(8192):
                        if chunk:
                            f.write(chunk)
                os.replace(tmp, path)
                logging.info("image cached: %s <- %s", path, u)
                return True, u
            except Exception as e:
                last_err = str(e)
                logging.warning("dl fail (%s/%s): %s (%s)", attempt, RETRY_TIMES, u, e)
        # 当前 URL 连续失败后，换下一个源
    logging.error("all providers failed for %s ; last_err=%s", path, last_err)
    return False, last_err

# ========= 路由 =========
@image_cache_bp.get("/media/ping")
def media_ping():
    return jsonify({"ok": True, "where": "image_cache"}), 200

@image_cache_bp.get("/media/programs/<slug>/<kind>.jpg")
def media_program_image(slug: str, kind: str):
    """
    kind: cover | hero | intro | overview | g1..g5
    ?debug=1 返回诊断 JSON；非 debug 返回图片/占位
    """
    debug = request.args.get("debug") == "1"
    try:
        dst = _cache_path(slug, kind)

        # 命中缓存
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            if debug:
                return {
                    "ok": True, "from": "cache", "path": os.path.abspath(dst),
                    "slug": slug, "kind": kind
                }, 200
            return _send_or_placeholder(dst)

        # ===== 只在开关允许时尝试查库，否则严格避免使用 p =====
        p = None
        if USE_DB_IN_IMAGE_ROUTE:
            try:
                p = Program.query.filter_by(slug=slug).first()
            except Exception as e:
                current_app.logger.warning("Program lookup failed, fallback to DB-less mode: %s", e)

        # ===== 基于 p（可能为 None）安全地生成 city / discipline =====
        city = (getattr(p, "city", None) or "").strip() if p else ""
        discipline = (getattr(p, "discipline", None) or "").strip() if p else ""

        # 若没从 DB 拿到，就从 slug 猜一点关键词
        if not city:
            parts = (slug or "").replace("-", " ").split()
            if parts:
                city = parts[0].capitalize()

        # 👉 确保在使用之前定义 orientation
        orientation = "landscape"

        # ===== 根据 kind 生成 query / 尺寸（完全不再引用 p）=====
        if kind == "cover":
            query, w, h = (f"{city} skyline university" if city else "university campus", 1600, 900)
        elif kind == "hero":
            query, w, h = (f"{city} university campus" if city else "university campus", 1600, 900)
        elif kind == "intro":
            query, w, h = (f"{discipline} students" if discipline else "students studying", 1200, 800)
        elif kind == "overview":
            query, w, h = ((f"{city} {discipline} classroom" if (city and discipline) else "classroom lecture"), 1200, 800)
        else:
            gallery_q = [
                f"{city} street" if city else "city street",
                "library study",
                "international students",
                f"{discipline} classroom" if discipline else "classroom",
                "coworking space"
            ]
            try:
                idx = int(kind[1:]) - 1  # g1..g5
            except Exception:
                idx = 0
            query, w, h = (gallery_q[idx] if 0 <= idx < len(gallery_q) else "campus", 1600, 900)

        # 候选源 & 下载
        seed = _hash_seed(slug, kind)
        providers = _unsplash_provider_urls(query, w, h, seed, orientation=orientation)

        if debug:
            return {
                "ok": True,
                "slug": slug, "kind": kind,
                "query": query, "w": w, "h": h, "orientation": orientation,
                "providers": providers,
                "cache_path": os.path.abspath(dst),
                "used_db": bool(p)
            }, 200

        ok, _ = _download_to_file(providers, dst)
        return _send_or_placeholder(dst)

    except Exception as e:
        if debug:
            import traceback
            return {"ok": False, "error": str(e), "trace": traceback.format_exc()}, 500
        return _send_or_placeholder(_cache_path(slug, kind))
