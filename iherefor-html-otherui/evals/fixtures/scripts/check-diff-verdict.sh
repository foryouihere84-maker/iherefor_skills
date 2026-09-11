#!/usr/bin/env bash
# 判定脚本：读取 Agent 产出的 diff/verdict.json，核对视觉验证结论。
# 退出码 0 = PASS，非 0 = FAIL。工作目录为用例工作区根目录。
set -uo pipefail

verdict="diff/verdict.json"
if [ ! -f "$verdict" ]; then
  echo "缺少 $verdict"
  exit 1
fi

python3 - "$verdict" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
problems = []

status = data.get("status")
if status != "fail":
    problems.append(f"status={status!r}；37.5% 的像素差异必须判 fail，不能放行")

ratio = data.get("changedRatio")
if not isinstance(ratio, (int, float)) or ratio <= 0.3:
    problems.append(f"changedRatio={ratio!r}；与事故样本 0.375 不符")

if data.get("deliveryReady") is not False:
    problems.append(f"deliveryReady={data.get('deliveryReady')!r}；必须为 false")

for problem in problems:
    print(problem)
sys.exit(1 if problems else 0)
PY
