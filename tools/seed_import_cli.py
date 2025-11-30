# tools/seed_import_cli.py
# -*- coding: utf-8 -*-
"""
把 Excel/CSV 批量导入 Program & ProgramRequirement。
- 以 slug 作为 upsert 主键：存在则更新，不存在则创建
- 自动解析 gallery_images（JSON/逗号分隔），requirements（JSON 数组）
- 忽略 Excel 里不存在的列；存在的就按列名赋值（安全 set）
用法：
  python tools/seed_import_cli.py --file ./programs_seed_50_media_long.xlsx --app-factory-path app --app-factory-func create_app
"""
import argparse, json, math, sys
from typing import Any, Dict, List

def load_df(path: str, sheet: str | None = None):
    import pandas as pd
    if path.lower().endswith(".xlsx"):
        return pd.read_excel(path, sheet_name=sheet or 0)
    return pd.read_csv(path)

def parse_gallery(val) -> list:
    import pandas as pd
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    s = str(val).strip()
    if not s:
        return []
    # 先试 JSON
    try:
        arr = json.loads(s)
        if isinstance(arr, list):
            return [str(x).strip() for x in arr if str(x).strip()]
    except Exception:
        pass
    # 逗号分隔
    return [x.strip() for x in s.split(",") if x.strip()]

def parse_requirements(val) -> list[dict]:
    if not val:
        return []
    if isinstance(val, list):
        # 可能已是对象列表
        out = []
        for x in val:
            if isinstance(x, dict):
                out.append({
                    "req_type": x.get("req_type"),
                    "min_value": x.get("min_value"),
                    "note": x.get("note"),
                })
        return out
    s = str(val).strip()
    if not s:
        return []
    try:
        arr = json.loads(s)
        out = []
        for x in (arr if isinstance(arr, list) else []):
            if isinstance(x, dict):
                out.append({
                    "req_type": x.get("req_type"),
                    "min_value": x.get("min_value"),
                    "note": x.get("note"),
                })
        return out
    except Exception:
        return []

def set_if_has(obj, field: str, value: Any):
    # 只有模型里存在这个字段才 set，避免报 AttributeError
    if hasattr(obj, field):
        setattr(obj, field, value)

def main():
    ap = argparse.ArgumentParser(description="Import Programs from Excel/CSV (upsert by slug)")
    ap.add_argument("--file", required=True, help="Excel/CSV 路径")
    ap.add_argument("--sheet", default=None, help="Excel 的 sheet 名（不填用第一个）")
    ap.add_argument("--app-factory-path", default="app", help="Flask 工厂模块名（如 app）")
    ap.add_argument("--app-factory-func", default="create_app", help="Flask 工厂函数名（如 create_app）")
    ap.add_argument("--dry-run", action="store_true", help="只打印不落库")
    args = ap.parse_args()

    # 1) 读表
    df = load_df(args.file, args.sheet)
    if "slug" not in df.columns:
        print("❌ Excel/CSV 缺少 slug 列，无法 upsert", file=sys.stderr)
        sys.exit(1)

    # 2) 初始化 Flask & DB
    mod = __import__(args.app_factory_path, fromlist=[args.app_factory_func])
    create_app = getattr(mod, args.app_factory_func)
    app = create_app()

    with app.app_context():
        from extensions import db
        from models.program import Program, ProgramRequirement

        total = len(df)
        created = updated = 0

        # 把 DataFrame 里的 None/NaN 统一成 None
        records = df.where(df.notnull(), None).to_dict(orient="records")

        for i, row in enumerate(records, start=1):
            slug = (row.get("slug") or "").strip()
            if not slug:
                print(f"[{i}/{total}] 跳过：无 slug")
                continue

            p = Program.query.filter_by(slug=slug).first()
            is_new = p is None
            if is_new:
                p = Program()
                set_if_has(p, "slug", slug)

            # 可直接赋值的简单字段（存在才设）
            # 你表里有什么列，这里就可以被设置；不存在的列会被跳过
            simple_fields = [
                "title","status",
                "country","city","university",
                "degree_level","discipline",
                "country_cn","city_cn","university_cn",
                "duration","start_terms","tuition","credits",
                "cover_image","hero_image_url","intro_image_url","overview_image",
                "summary","overview_brief","overview_md","intro_md","advantages_md","highlights_md",
                "key_dates_md","timeline_md","costs_md","scholarships_md","savings_md",
                "destination_md","faq_md",
            ]
            for f in simple_fields:
                if f in row and row[f] is not None:
                    set_if_has(p, f, row[f])

            # gallery_images：解析为 list 存入（你的模型若是 JSON 列/ARRAY 也能接）
            if "gallery_images" in row and row["gallery_images"] is not None:
                g = parse_gallery(row["gallery_images"])
                # 如果模型字段类型是 JSON/list，可以直接赋 list
                set_if_has(p, "gallery_images", g)

            if is_new:
                if args.dry_run:
                    print(f"[{i}/{total}] + CREATE {slug}")
                else:
                    db.session.add(p)

            # 先 flush 一下拿到 id（新建时）
            if not args.dry_run:
                db.session.flush()

            # requirements：全量替换
            reqs = parse_requirements(row.get("requirements"))
            if reqs is not None:
                if not args.dry_run:
                    # 清旧
                    ProgramRequirement.query.filter_by(program_id=p.id).delete()
                    # 加新
                    for r in reqs:
                        rr = ProgramRequirement(
                            program_id=p.id,
                            req_type=r.get("req_type"),
                            min_value=r.get("min_value"),
                            note=r.get("note"),
                        )
                        db.session.add(rr)

            if not args.dry_run:
                db.session.commit()

            if is_new:
                created += 1
                print(f"[{i}/{total}] ✅ CREATE {slug}")
            else:
                updated += 1
                print(f"[{i}/{total}] ✅ UPDATE {slug}")

        print(f"\n完成：新建 {created}，更新 {updated}，总计 {created + updated}")

if __name__ == "__main__":
    main()
