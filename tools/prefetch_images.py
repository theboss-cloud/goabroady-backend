# tools/prefetch_images.py
# -*- coding: utf-8 -*-
import os, sys, time, json, math
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------- 可调参数 ----------
DEFAULT_KINDS = ["cover","hero","intro","overview","g1","g2","g3","g4","g5"]
DEFAULT_BASE  = "http://localhost:5000"   # 你的后端地址
TIMEOUT       = 20                         # 单次请求超时（秒）
RETRIES       = 3                          # 重试次数
CONCURRENCY   = 8                          # 并发数

def fetch(url: str, timeout=TIMEOUT, retries=RETRIES):
    for attempt in range(1, retries+1):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                return True, 200, None
            else:
                err = f"HTTP {r.status_code}"
        except Exception as e:
            err = str(e)
        # backoff
        time.sleep(min(2**attempt, 8))
    return False, None, err

def do_slug(base: str, slug: str, kinds: list[str]):
    base = base.rstrip("/")
    results = []
    for k in kinds:
        url = f"{base}/media/programs/{slug}/{k}.jpg"
        ok, code, err = fetch(url)
        results.append((k, ok, code, err))
    return slug, results

def iter_slugs_from_db(app_factory_path: str, app_factory_func: str) -> list[str]:
    """
    从 Flask 应用上下文读取数据库 slugs：
    - app_factory_path: 例如 'app'（表示 from app import create_app）
    - app_factory_func: 例如 'create_app'
    你的项目若不是工厂函数，可稍改为直接导入 app 对象。
    """
    mod = __import__(app_factory_path, fromlist=[app_factory_func])
    create_app = getattr(mod, app_factory_func)
    from extensions import db                     # 确保你的扩展路径正确
    from models.program import Program            # 确保模型路径正确
    app = create_app()
    slugs = []
    with app.app_context():
        for p in Program.query.with_entities(Program.slug).all():
            slugs.append(p.slug)
    return slugs

def iter_slugs_from_file(path: str):
    """
    支持两种格式：
    1) 纯文本：每行一个 slug（无逗号）
    2) CSV：必须包含一列 slug（大小写不敏感）
    """
    import csv, io, os

    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with open(path, "rb") as f:
        raw = f.read()

    # 去掉可能的 UTF-8 BOM
    text = raw.decode("utf-8-sig", errors="ignore")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # 判断是否是 CSV（出现逗号或分号的概率高）
    is_csv = False
    for ln in lines[:5]:
        if ("," in ln) or (";" in ln) or ("\t" in ln):
            is_csv = True
            break

    if not is_csv:
        # 纯文本：每行就是 slug
        return [ln for ln in lines if not ln.startswith("#")]

    # CSV 分支：找 slug 列
    sio = io.StringIO(text)
    reader = csv.DictReader(sio)
    fieldnames = [fn.strip() for fn in (reader.fieldnames or [])]
    # 尝试多种大小写 / 空格
    slug_key = None
    for name in fieldnames:
        if name.strip().lower() == "slug":
            slug_key = name
            break
    if not slug_key:
        raise ValueError(f"CSV 中找不到 slug 列。字段有：{fieldnames}")

    out = []
    for row in reader:
        v = (row.get(slug_key) or "").strip()
        if v:
            out.append(v)
    return out

def main():
    ap = argparse.ArgumentParser(description="Prefetch /media/programs/<slug>/<kind>.jpg 缓存")
    ap.add_argument("--base", default=DEFAULT_BASE, help="后端基地址, 默认 http://localhost:5000")
    ap.add_argument("--kinds", default=",".join(DEFAULT_KINDS), help="要预热的种类, 逗号分隔")
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY, help="并发数")
    ap.add_argument("--from-db", action="store_true", help="从数据库读取 slugs")
    ap.add_argument("--app-factory-path", default="app", help="Flask 工厂模块名, 如 app")
    ap.add_argument("--app-factory-func", default="create_app", help="Flask 工厂函数名, 如 create_app")
    ap.add_argument("--from-file", help="从 CSV/XLSX 读取 slugs（与 --from-db 互斥）")
    args = ap.parse_args()

    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    if not kinds:
        print("kinds 为空"); sys.exit(1)

    # 选择 slugs 来源
    if args.from_db:
        slugs = iter_slugs_from_db(args.app_factory_path, args.app_factory_func)
    elif args.from_file:
        slugs = iter_slugs_from_file(args.from_file)
    else:
        print("需要指定 --from-db 或 --from-file")
        sys.exit(1)

    if not slugs:
        print("没有可用 slug"); sys.exit(0)

    print(f"准备预热 {len(slugs)} 条 × {len(kinds)} 张 = {len(slugs)*len(kinds)} 请求")
    ok_cnt = fail_cnt = 0

    # 并发执行（每个 slug 串行抓 kinds，多个 slug 并发）
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [ex.submit(do_slug, args.base, s, kinds) for s in slugs]
        for fut in as_completed(futs):
            slug, results = fut.result()
            # 逐项打印精简日志
            line = [slug]
            for k, ok, code, err in results:
                if ok:
                    ok_cnt += 1
                    line.append(f"{k}:OK")
                else:
                    fail_cnt += 1
                    line.append(f"{k}:FAIL({code or err})")
            print(" | ".join(line))

    print(f"\n完成：OK {ok_cnt}，FAIL {fail_cnt}，总计 {ok_cnt + fail_cnt}")
    if fail_cnt > 0:
        sys.exit(2)

if __name__ == "__main__":
    main()
