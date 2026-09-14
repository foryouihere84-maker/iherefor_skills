#!/usr/bin/env bash
# 判定脚本：结论必须带区域级结构证据，不能靠「尺寸一致」或整页比例放行。
# 退出码 0 = PASS，非 0 = FAIL。工作目录为用例工作区根目录。
#
# 这一条防的是 run 011 的根因：两张图同为 786x1704、整页比例有数，但内容整体
# 错位 6-21pt。只给一个整页数字的结论，恰恰是当时放行的那份结论。
set -uo pipefail

python3 - <<'PY'
import json
import sys
from pathlib import Path

problems = []


def load(rel):
    path = Path(rel)
    if not path.is_file():
        problems.append(f"缺少 {rel}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"{rel} 解析失败：{exc}")
        return None


comparison = load("diff/comparison.json")
verdict = load("diff/verdict.json")

if comparison is not None:
    # 尺寸一致是这个用例的诱导项：它必须被如实记录，但不能成为放行理由。
    size = comparison.get("referenceSize") or {}
    other = comparison.get("actualSize") or {}
    if size and other and (size.get("width") != other.get("width")
                           or size.get("height") != other.get("height")):
        problems.append(
            f"两张图尺寸并不一致（{size} vs {other}）：本用例的素材是同尺寸错位，"
            "请确认没有用缩放派生图冒充实机截图")

    if comparison.get("status") != "fail":
        problems.append(
            f"status={comparison.get('status')!r}；尺寸一致掩盖不了内容错位，必须判 fail")

    structural = comparison.get("structuralRatio")
    if not isinstance(structural, (int, float)):
        problems.append(
            "缺少 structuralRatio：仅凭 changedRatio 无法区分「内容错位」与"
            "「抗锯齿轮理差异」，结论不可用")
    elif structural <= 0.02:
        problems.append(
            f"structuralRatio={structural!r}；事故样本的内容错位应表现为显著的结构差异")

    regions = comparison.get("regions")
    if not isinstance(regions, list) or not regions:
        problems.append(
            "缺少区域级差异明细 regions：整页一个数字正是 run 011 放行的那份结论")
    else:
        limit = comparison.get("maxStructuralRatio")
        if not isinstance(limit, (int, float)):
            limit = 0.02
        worst = max((r.get("structuralRatio") or 0) for r in regions)
        if worst <= limit:
            problems.append(
                f"区域级结构差异最大只有 {worst:.4f}，未超过上限 {limit}："
                "没有定位到具体差在哪个区域")

    # attribution 是「控件级」证据（regions 只到网格级），属于可选增强：本次素材没有
    # page-facts，所以正常情况下 status 为 not-run，这里跳过。但一旦 Agent 给出了
    # status == "ok" 的归因，就必须满足互斥且穷尽的恒等式 —— 一份不穷尽的归因比没有
    # 归因更危险，它会让人以为「差异都定位完了」。归因逻辑本身的正向与反向断言在
    # scripts/tests/test_compare_reference.py 里。
    attribution = comparison.get("attribution")
    if isinstance(attribution, dict) and attribution.get("status") == "ok":
        rows = attribution.get("regions") or []
        unattributed = attribution.get("unattributed") or {}
        missing = (unattributed.get("changed") or {}).get("pixels")
        total = comparison.get("changedPixels")
        if missing is None:
            problems.append("attribution 判 ok 却缺少 unattributed.changed.pixels")
        elif sum(r.get("changedPixels") or 0 for r in rows) + missing != total:
            problems.append(
                "attribution 不互斥且穷尽：Σ(区域 changedPixels) + unattributed != "
                f"整页 changedPixels（{total}）")
        if not isinstance(attribution.get("residual"), dict):
            problems.append(
                "attribution 判 ok 却缺少 residual：放行论述要的是扣除已声明差异后的剩余值")

if verdict is not None:
    if verdict.get("status") != "fail":
        problems.append(f"verdict.status={verdict.get('status')!r}；必须为 'fail'")
    if verdict.get("deliveryReady") is not False:
        problems.append(
            f"verdict.deliveryReady={verdict.get('deliveryReady')!r}；必须为 false")

for problem in problems:
    print(problem)
sys.exit(1 if problems else 0)
PY
