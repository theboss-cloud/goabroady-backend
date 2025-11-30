# fix_numpy.py  —— 安全把 numpy==2.0.0b1 改成 2.3.2，保留原编码（UTF-8/UTF-16）
import os

p = r"E:\dieprojekt\backend\requirements.txt"

with open(p, "rb") as f:
    raw = f.read()

enc = "utf-8"
bom = b""
# 检测 UTF-16（LE/BE）
if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
    enc = "utf-16"
    bom = raw[:2]

text = raw[len(bom):].decode(enc, errors="replace")
new = text.replace("numpy==2.0.0b1", "numpy==2.3.2")

if new == text:
    print("提示：没找到 'numpy==2.0.0b1'，可能已经改过。")
else:
    with open(p, "wb") as f:
        f.write(bom + new.encode(enc))
    print(f"已将 numpy 固定版本改为 2.3.2，并保持原文件编码：{enc}")
