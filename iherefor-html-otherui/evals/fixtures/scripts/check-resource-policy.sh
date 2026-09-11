#!/usr/bin/env bash
# 判定脚本：核对资源映射是否按 <screen>_<region>_<role> 语义命名。
# 退出码 0 = PASS，非 0 = FAIL。工作目录为用例工作区根目录。
set -uo pipefail

policy="resource-policy.json"
if [ ! -f "$policy" ]; then
  echo "缺少 $policy"
  exit 1
fi

python3 - "$policy" <<'PY'
import json
import re
import sys

raw = open(sys.argv[1], encoding="utf-8").read()
try:
    data = json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"resource-policy.json 不是合法 JSON：{exc}")
    sys.exit(1)


def collect(node, out):
    if isinstance(node, dict):
        for value in node.values():
            collect(value, out)
    elif isinstance(node, list):
        for item in node:
            collect(item, out)
    elif isinstance(node, str):
        out.append(node)


strings = []
collect(data, strings)
problems = []

for index in (0, 1, 2):
    if f"img_{index}" not in raw:
        problems.append(f"映射中未提及输入资源 img_{index}.png")

semantic = sorted({
    s for s in strings
    if re.fullmatch(r"[a-z][a-z0-9_]*", s) and s.count("_") >= 2
})
if len(semantic) < 3:
    problems.append(f"语义命名不足三个（应为 <screen>_<region>_<role>）：{semantic}")

joined = " ".join(semantic)
for label, pattern in (("主视觉", r"hero|collage|visual|banner"),
                       ("图标", r"icon|close|mark"),
                       ("卡片", r"card|background|bg|panel")):
    if not re.search(pattern, joined):
        problems.append(f"语义名中缺少「{label}」对应角色：{semantic}")

if any(name.startswith("img") for name in semantic):
    problems.append(f"仍以来源编号命名：{[n for n in semantic if n.startswith('img')]}")

for problem in problems:
    print(problem)
sys.exit(1 if problems else 0)
PY
