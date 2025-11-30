# routes/program_export.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, jsonify, send_file, Response, request
from io import BytesIO
from datetime import datetime
import json
import csv

# 依赖：pip install pandas openpyxl
import pandas as pd

# 你的项目内模块（按需调整路径）
from models.program import Program, ProgramRequirement
from extensions import db

# ===================== 配置 =====================
USE_JWT = True
try:
    from flask_jwt_extended import jwt_required
except Exception:
    # 未安装时兜底
    def jwt_required():
        def _wrap(f): return f
        return _wrap

def maybe_jwt():
    """按 USE_JWT 决定是否加 jwt_required 修饰器"""
    return jwt_required() if USE_JWT else (lambda f: f)

program_export_bp = Blueprint(
    "program_export",
    __name__,
    url_prefix="/api/admin/programs"
)

# =============== 固定列（基线表头）===============
# 这些列会优先、靠前显示；其余列在导出时动态追加
PROGRAM_COLUMNS_BASE = [
    "id","slug","title","status",
    "country","city","university","degree_level","discipline",
    # 常用“中文三字段”
    "country_cn","city_cn","university_cn",
    "duration","start_terms","tuition","credits",
    "cover_image","hero_image_url","intro_image_url","overview_image",
    "summary","overview_brief","overview_md","intro_md","advantages_md","highlights_md",
    "key_dates_md","timeline_md","costs_md",
    "scholarships_md","savings_md",
    "destination_md","faq_md",
    "gallery_images",   # JSON 或 逗号分隔
    "created_at","updated_at"
]

REQUIREMENT_COLUMNS_BASE = ["program_id","program_slug","req_type","min_value","note"]

PROGRAM_FIELD_HELP = {
    "id":"数据库主键（只读）","slug":"URL 唯一标识（必填）","title":"项目标题（必填）","status":"draft/published",
    "country":"国家","city":"城市","university":"院校","degree_level":"Bachelor/Master/Certificate…","discipline":"学科门类",
    "country_cn":"国家（中文）","city_cn":"城市（中文）","university_cn":"院校（中文）",
    "duration":"1 semester / 2 years","start_terms":"Fall, Spring","tuition":"学费文本","credits":"学分（可空）",
    "cover_image":"封面图 URL","hero_image_url":"Hero 图 URL","intro_image_url":"引导图 URL","overview_image":"概览配图",
    "summary":"摘要（短）","overview_brief":"项目概览（短/富文本可空）","overview_md":"项目概览（Markdown/HTML）",
    "intro_md":"导语","advantages_md":"项目优势","highlights_md":"亮点（Markdown/HTML）",
    "key_dates_md":"关键日期","timeline_md":"时间线",
    "costs_md":"费用明细","scholarships_md":"奖学金说明","savings_md":"省钱策略",
    "destination_md":"目的地生活","faq_md":"常见问答",
    "gallery_images":"相册（JSON 数组或逗号分隔 URL）",
    "created_at":"创建时间（只读）","updated_at":"更新时间（只读）",
}
REQUIREMENT_FIELD_HELP = {
    "program_id":"Program.id（只读）","program_slug":"冗余导出方便看",
    "req_type":"GPA/IELTS/TOEFL/GRE/EXP/OTHER","min_value":"如 2.8/4.0、6.5","note":"备注",
}

# ===================== 工具函数 =====================
META_CANDIDATES = ["extra", "meta", "data", "attrs", "localized"]

def _gallery_to_text(g):
    """gallery_images -> 文本（JSON 优先；用于导出单元格）"""
    if g is None:
        return ""
    if isinstance(g, (list, tuple, dict)):
        return json.dumps(g, ensure_ascii=False)
    if isinstance(g, str):
        return g
    try:
        return json.dumps(g, ensure_ascii=False)
    except Exception:
        return str(g)

def _to_cell(v):
    """统一把值转成适合表格的文本"""
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            pass
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)

def _get_meta_value(p: Program, key: str):
    """从扩展 JSON 列尝试获取值（extra/meta/data/attrs/localized）"""
    for meta_name in META_CANDIDATES:
        if hasattr(p, meta_name):
            meta = getattr(p, meta_name) or {}
            if isinstance(meta, dict) and key in meta:
                return meta[key]
    return None

def _program_row_expanded(p: Program) -> dict:
    """
    组装一行数据：
    1) 先取常见显式列（getattr）
    2) 合并对象 __dict__ 可见字段（过滤 SQLA 内部前缀）
    3) 合并扩展 JSON（extra/meta/data/attrs/localized）
    4) 归一化常用字段为文本
    """
    # 1) 显式列
    d = {
        "id": p.id,
        "slug": p.slug,
        "title": p.title,
        "status": p.status,
        "country": p.country,
        "city": p.city,
        "university": p.university,
        "degree_level": p.degree_level,
        "discipline": p.discipline,
        "country_cn": getattr(p, "country_cn", None),
        "city_cn": getattr(p, "city_cn", None),
        "university_cn": getattr(p, "university_cn", None),
        "duration": p.duration,
        "start_terms": p.start_terms,
        "tuition": p.tuition,
        "credits": p.credits,
        "cover_image": getattr(p, "cover_image", None) or getattr(p, "hero_image_url", None) or getattr(p, "intro_image_url", None) or "",
        "hero_image_url": getattr(p, "hero_image_url", None),
        "intro_image_url": getattr(p, "intro_image_url", None),
        "overview_image": getattr(p, "overview_image", None),
        "summary": p.summary,
        "overview_brief": getattr(p, "overview_brief", None),
        "overview_md": getattr(p, "overview_md", None),
        "intro_md": getattr(p, "intro_md", None),
        "advantages_md": getattr(p, "advantages_md", None),
        "highlights_md": getattr(p, "highlights_md", None),
        "key_dates_md": getattr(p, "key_dates_md", None),
        "timeline_md": getattr(p, "timeline_md", None),
        "costs_md": getattr(p, "costs_md", None),
        "scholarships_md": getattr(p, "scholarships_md", None),
        "savings_md": getattr(p, "savings_md", None),
        "destination_md": getattr(p, "destination_md", None),
        "faq_md": getattr(p, "faq_md", None),
        "gallery_images": getattr(p, "gallery_images", None),
        "created_at": getattr(p, "created_at", None),
        "updated_at": getattr(p, "updated_at", None),
    }

    # 2) 合并对象 __dict__（避免漏掉后来加的 ORM 列）
    try:
        for k, v in vars(p).items():
            if k.startswith("_"):  # SQLAlchemy 内部属性
                continue
            if k not in d:
                d[k] = v
    except Exception:
        pass

    # 3) 合并扩展 JSON（不覆盖已有键）
    for meta_name in META_CANDIDATES:
        if hasattr(p, meta_name):
            meta = getattr(p, meta_name) or {}
            if isinstance(meta, dict):
                for k, v in meta.items():
                    if k not in d:
                        d[k] = v

    # 4) 规范化
    d["gallery_images"] = _gallery_to_text(d.get("gallery_images"))
    if d.get("created_at") is not None and hasattr(d["created_at"], "isoformat"):
        d["created_at"] = d["created_at"].isoformat()
    if d.get("updated_at") is not None and hasattr(d["updated_at"], "isoformat"):
        d["updated_at"] = d["updated_at"].isoformat()

    return d

def _req_row_expanded(p: Program, r: ProgramRequirement) -> dict:
    """requirements 行（这一张表通常字段比较固化）"""
    return {
        "program_id": p.id,
        "program_slug": p.slug,
        "req_type": r.req_type,
        "min_value": r.min_value,
        "note": r.note,
    }

def _apply_filters(query):
    """支持：id 精确、ids 列表、slug 精确、status、q 模糊"""
    pid = (request.args.get("id") or "").strip()
    if pid.isdigit():
        return query.filter(Program.id == int(pid))

    slug = (request.args.get("slug") or "").strip()
    if slug:
        query = query.filter(Program.slug == slug)

    status = (request.args.get("status") or "").strip()
    if status:
        query = query.filter(Program.status == status)

    qkw = (request.args.get("q") or "").strip()
    if qkw:
        like = f"%{qkw}%"
        from sqlalchemy import or_
        query = query.filter(or_(
            Program.title.ilike(like),
            Program.slug.ilike(like),
            Program.country.ilike(like),
            Program.city.ilike(like),
            Program.university.ilike(like),
            Program.discipline.ilike(like),
        ))

    ids = (request.args.get("ids") or "").strip()
    if ids:
        try:
            arr = [int(x) for x in ids.split(",") if x.strip().isdigit()]
            if arr:
                query = query.filter(Program.id.in_(arr))
        except Exception:
            pass

    return query

def _get_programs():
    q = _apply_filters(Program.query)
    # created_at 可能为空；使用 nullslast
    return q.order_by(Program.created_at.desc().nullslast(), Program.id.desc()).all()

# ===================== 路由 =====================

# 健康检查
@program_export_bp.get("/ping")
def export_ping():
    return jsonify({"ok": True, "where": "program_export"}), 200

# 空模板（XLSX）
@program_export_bp.get("/export-template")
@maybe_jwt()
def export_program_template():
    df_programs = pd.DataFrame(columns=PROGRAM_COLUMNS_BASE)
    df_require  = pd.DataFrame(columns=REQUIREMENT_COLUMNS_BASE)

    # 字段说明（第三个 sheet）
    help_rows = [["【Program 主表】字段","说明"]]
    for k in PROGRAM_COLUMNS_BASE:
        help_rows.append([k, PROGRAM_FIELD_HELP.get(k,"")])
    help_rows.append([])
    help_rows.append(["【Requirements 子表】字段","说明"])
    for k in REQUIREMENT_COLUMNS_BASE:
        help_rows.append([k, REQUIREMENT_FIELD_HELP.get(k,"")])
    df_help = pd.DataFrame(help_rows)

    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df_programs.to_excel(writer, sheet_name="programs", index=False)
        df_require.to_excel(writer, sheet_name="requirements", index=False)
        df_help.to_excel(writer, sheet_name="字段说明", header=False, index=False)
    bio.seek(0)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return send_file(
        bio,
        as_attachment=True,
        download_name=f"programs_template_{ts}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# 导出：XLSX（自动列头）
@program_export_bp.get("/export")
@maybe_jwt()
def export_program_data_xlsx():
    programs = _get_programs()

    # 主表行
    prog_rows = [_program_row_expanded(p) for p in programs]

    # 自动列头：基线 + 行里出现过的其它键
    prog_columns = list(PROGRAM_COLUMNS_BASE)
    seen_prog = set(prog_columns)
    for r in prog_rows:
        for k in r.keys():
            if k not in seen_prog:
                prog_columns.append(k)
                seen_prog.add(k)

    # requirements 行
    req_rows = []
    for p in programs:
        try:
            reqs = list(p.requirements or [])
        except Exception:
            reqs = ProgramRequirement.query.filter_by(program_id=p.id).all()
        for r in reqs:
            req_rows.append(_req_row_expanded(p, r))

    req_columns = list(REQUIREMENT_COLUMNS_BASE)  # 通常固定，如需扩展也可动态扫描

    # 写 XLSX
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df_programs = pd.DataFrame([{k: _to_cell(row.get(k)) for k in prog_columns} for row in prog_rows], columns=prog_columns)
        df_programs.to_excel(writer, sheet_name="programs", index=False)

        df_require = pd.DataFrame([{k: _to_cell(row.get(k)) for k in req_columns} for row in req_rows], columns=req_columns)
        df_require.to_excel(writer, sheet_name="requirements", index=False)

    bio.seek(0)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return send_file(
        bio,
        as_attachment=True,
        download_name=f"programs_export_{ts}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# 导出：CSV（两个“sheet”拼接；自动列头）
@program_export_bp.get("/export.csv")
@maybe_jwt()
def export_program_data_csv():
    programs = _get_programs()

    prog_rows = [_program_row_expanded(p) for p in programs]
    prog_columns = list(PROGRAM_COLUMNS_BASE)
    seen_prog = set(prog_columns)
    for r in prog_rows:
        for k in r.keys():
            if k not in seen_prog:
                prog_columns.append(k)
                seen_prog.add(k)

    # 需求表
    req_rows = []
    for p in programs:
        try:
            reqs = list(p.requirements or [])
        except Exception:
            reqs = ProgramRequirement.query.filter_by(program_id=p.id).all()
        for r in reqs:
            req_rows.append(_req_row_expanded(p, r))
    req_columns = list(REQUIREMENT_COLUMNS_BASE)

    def to_csv_line(vals):
        out = []
        for s in vals:
            s = "" if s is None else str(s)
            if any(c in s for c in [",", "\"", "\n", "\r"]):
                s = "\"" + s.replace("\"", "\"\"") + "\""
            out.append(s)
        return ",".join(out)

    lines = []

    # programs sheet
    lines.append(",".join(prog_columns))
    for row in prog_rows:
        vals = [_to_cell(row.get(k)) for k in prog_columns]
        lines.append(to_csv_line(vals))

    lines.append("")  # 空行分隔

    # requirements sheet
    lines.append(",".join(req_columns))
    for row in req_rows:
        vals = [_to_cell(row.get(k)) for k in req_columns]
        lines.append(to_csv_line(vals))

    csv_text = "\n".join(lines)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Response(
        ("\ufeff" + csv_text),  # BOM for Excel
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=programs_export_{ts}.csv"}
    )

# 单条 Inspect（JSON）
@program_export_bp.get("/inspect")
@maybe_jwt()
def export_program_inspect():
    pid  = (request.args.get("id") or "").strip()
    slug = (request.args.get("slug") or "").strip()

    p = None
    if pid.isdigit():
        p = Program.query.get(int(pid))
    if not p and slug:
        p = Program.query.filter_by(slug=slug).first()

    if not p:
        return jsonify({"msg": "not found"}), 404

    data = _program_row_expanded(p)

    # 附带 requirements
    try:
        reqs = list(p.requirements or [])
    except Exception:
        reqs = ProgramRequirement.query.filter_by(program_id=p.id).all()
    data["requirements"] = [
        {"req_type": r.req_type, "min_value": r.min_value, "note": r.note}
        for r in reqs
    ]
    return jsonify(data), 200
