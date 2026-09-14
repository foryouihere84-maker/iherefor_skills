#!/usr/bin/env bash
# 判定脚本：布局关系必须按设计稿比例实现，且必须分得清「设备推导值」与「设计常量」。
# 退出码 0 = PASS，非 0 = FAIL。工作目录为用例工作区根目录。
#
# 这一条防的是：把 `lanhuY * scale` 的结果写成字面量。它看起来有出处、算过，
# review 时最容易被放过，而换台设备就是错的。
#
# 素材里故意混了真设计常量（圆角 12、发丝线 1、最小点击区 44），
# 所以这里既查召回也查精度：两头都错 = 没通过。
set -uo pipefail

python3 - <<'PY'
import json
import re
import sys
from pathlib import Path

# 只在 402x874 探针设备上成立的大数值：出现在源码里就是违规。
DEVICE_DERIVED = {393, 852, 321, 495, 347, 68, 352, 741, 232, 495}
# 真设计常量：缩放它们才是错的，报成违规就是误报。
DESIGN_CONSTANTS = {12, 1, 44}
# 小数值：与设计常量无法区分，报或不报都不扣分（判分侧不作要求）。
AMBIGUOUS_OK = {16, 23, 24, 25, 48, 0}

problems = []


VALUE_KEYS = ("literal", "deviceDerivedPt", "value", "pt", "number", "constant")
# 行号、比例这类字段里也会出现数字，但它们是**元数据**，不是被判定的字面量。
# 曾经因为扫了全篇，把 ``line: 12`` 当成了「误报设计常量 12」—— 判分器必须
# 只认明确的数值字段，不能见数字就收。
NUMBER_IN_TEXT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:pt|px|dp)")


def literal_values(value, found):
    """只从明确的数值字段里取值，外加形如 ``393pt`` 的带单位写法。"""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in VALUE_KEYS and isinstance(item, (int, float)) and not isinstance(item, bool):
                found.add(float(item))
            elif key in VALUE_KEYS and isinstance(item, str):
                for token in NUMBER_IN_TEXT.findall(item):
                    found.add(float(token))
    elif isinstance(value, list):
        for item in value:
            literal_values(item, found)


def numbers_in(value, found):
    """把结论里所有数值抠出来，不看它写成什么形状。"""
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        found.add(float(value))
    elif isinstance(value, str):
        for token in re.findall(r"\d+(?:\.\d+)?", value):
            found.add(float(token))
    elif isinstance(value, dict):
        for item in value.values():
            numbers_in(item, found)
    elif isinstance(value, list):
        for item in value:
            numbers_in(item, found)


verdict_path = Path("diff/proportion-verdict.json")
if not verdict_path.is_file():
    problems.append("缺少 diff/proportion-verdict.json")
    verdict = None
else:
    try:
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"diff/proportion-verdict.json 解析失败：{exc}")
        verdict = None

if isinstance(verdict, dict):
    if verdict.get("status") != "fail":
        problems.append(
            f"status={verdict.get('status')!r}；"
            "源码把布局关系写成了只在探针设备上成立的绝对值，必须判 fail")
    if verdict.get("deliveryReady") is not False:
        problems.append(
            f"deliveryReady={verdict.get('deliveryReady')!r}；必须为 false —— "
            "run 自己记的 true 正是这条红线要推翻的结论")

    violations = verdict.get("violations")
    if not isinstance(violations, list) or not violations:
        problems.append("缺少 violations 明细：只说「有违规」而不指出是哪些数值，无法复核")
    else:
        # 召回与精度**只看 violations 这一项**。
        # 不能扫整份结论：Agent 在 reason 或专门的说明字段里写「圆角 12 不是违规」是
        # 正确行为，扫全篇会把它当成误报 —— 那就变成惩罚正确的解释。
        hit = set()
        literal_values(violations, hit)
        named = sorted(hit & {float(v) for v in DEVICE_DERIVED})
        if len(named) < 2:
            problems.append(
                f"violations 只点到了 {named}；至少应指出两条「只在 402x874 上成立」的"
                f"设备推导值（如 {sorted(DEVICE_DERIVED)[:5]}）")

        # 精度：设计常量不得被当成违规
        misreported = sorted(hit & {float(v) for v in DESIGN_CONSTANTS})
        if misreported:
            problems.append(
                f"把设计常量 {misreported} 报成了违规；字号/圆角/描边/最小点击区是设计值，"
                "保持原值不缩放，缩放它们才是错的")

        # 每条违规要能指到文件，否则无法复核
        if not any(isinstance(i, dict) and i.get("file") for i in violations):
            problems.append("violations 里没有 file 字段：违规必须能定位到源码文件")

    if not (verdict.get("reason") or "").strip():
        problems.append("缺少 reason：判据要写出来，不能只给结论")

# 产出物必须来自脚本，而不是手写：校验器的原始结论应当在场。
evidence = Path("diff/layout-proportions.json")
if not evidence.is_file():
    problems.append(
        "缺少 diff/layout-proportions.json：结论应是校验器的原始产出，"
        "而不是手工总结的段落")
else:
    try:
        report = json.loads(evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"diff/layout-proportions.json 解析失败：{exc}")
        report = None
    if isinstance(report, dict):
        if report.get("status") != "fail":
            problems.append(f"校验器原始结论 status={report.get('status')!r}，应为 fail")
        if report.get("proportionalIdiomCount") == 0:
            pass  # 这正是本用例的前提：一处比例原语都没有
        elif report.get("proportionalIdiomCount") is None:
            problems.append("校验器原始结论缺少 proportionalIdiomCount")

# 源码不得被改动：本用例只要求出结论。
source = Path("src/SpecialOfferViewController.m")
if source.is_file():
    text = source.read_text(encoding="utf-8", errors="replace")
    for literal in ("393, 321", "495, 347", "741, 352"):
        if literal not in text:
            problems.append(
                f"源码里的 {literal} 被改动了；本用例只要求判断并出结论，"
                "脚本与 Agent 都不得生成或改写生产 UI 源码")

for problem in problems:
    print(problem)
sys.exit(1 if problems else 0)
PY
