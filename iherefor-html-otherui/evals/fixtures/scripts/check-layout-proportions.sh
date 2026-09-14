#!/usr/bin/env bash
# 判定脚本：布局必须做到「尺寸是常量、位置相对直接父视图」，
# 且必须分得清「设备推导出来的绝对坐标」与「应当照原值写进代码的设计值」。
# 退出码 0 = PASS，非 0 = FAIL。工作目录为用例工作区根目录。
#
# 这一条防的是：把设计稿量出来的值当绝对坐标写进约束。它看起来有出处、算过，
# review 时最容易被放过，而换台设备就是错的。
#
# 素材里故意混了三种**应当照字面量写**的值：
#   - 设计常量（圆角 12、发丝线 1、最小点击区 44）；
#   - fixed 尺寸（卡片高 68、按钮高 48）—— 尺寸是常量，照原值写；
#   - pinned 的固定内边距（左起 23、右侧 25）—— 「贴父边 + 间距」写约束常量。
# 所以这里既查召回也查精度：两头都错 = 没通过。
set -uo pipefail

python3 - <<'PY'
import json
import re
import sys
from pathlib import Path

# 只在 402x874 探针设备上成立的绝对坐标：出现在源码里就是违规。
# 这五个值就是生成端 forbiddenLiterals 里那几条 —— 只有被判成 proportional 的
# 位置/尺寸才会入清单，因为只有它们才「换台设备必然不对」。
DEVICE_DERIVED = {321, 495, 741, 83, 801}
# 计划里 kind=fixed 或 kind=pinned 的那些值：**本来就该照原值写进代码**。
#   12 / 1 / 44  设计常量（圆角、发丝线、最小点击区）
#   68 / 48      fixed 尺寸（卡片高、按钮高）
#   23 / 25      pinned 固定内边距（offers 左起 23、cta 右侧 25；offers 两侧各 23 闭合）
# 把它们报成「依赖容器尺寸、应该比例化」正是这条红线最典型的错误理解，
# 所以判分要挡住 —— 漏报是错，误报也是错。
SHOULD_BE_LITERAL = {12, 1, 44, 68, 48, 23, 25}
# 至少要点名几条设备推导值。真实执行路径（跑校验器）会给出全部五条；
# 手工核对也至少该抓住最显眼的几个大数值。
MIN_DEVICE_DERIVED_NAMED = 3

problems = []

# 数值字段。行号、比例这类字段里也会出现数字，但它们是**元数据**，不是被判定的字面量。
# 曾经因为扫了全篇，把 ``line: 12`` 当成了「误报设计常量 12」—— 判分器必须
# 只认明确的数值字段，不能见数字就收。
VALUE_KEYS = ("literal", "deviceDerivedPt", "value", "pt", "number", "constant")
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


verdict_path = Path("diff/layout-verdict.json")
if not verdict_path.is_file():
    problems.append("缺少 diff/layout-verdict.json")
    verdict = None
else:
    try:
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"diff/layout-verdict.json 解析失败：{exc}")
        verdict = None

if isinstance(verdict, dict):
    if verdict.get("status") != "fail":
        problems.append(
            f"status={verdict.get('status')!r}；"
            "源码把布局写成了只在探针设备上成立的绝对坐标，必须判 fail")
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
        if len(named) < MIN_DEVICE_DERIVED_NAMED:
            problems.append(
                f"violations 只点到了 {named}；至少应指出 {MIN_DEVICE_DERIVED_NAMED} 条"
                "「只在 402x874 上成立」的设备推导坐标"
                f"（{sorted(DEVICE_DERIVED)}）")

        # 精度：应当照原值写的设计值不得被当成违规。
        misreported = sorted(hit & {float(v) for v in SHOULD_BE_LITERAL})
        if misreported:
            problems.append(
                f"把 {misreported} 报成了违规；这些是**应当照字面量写进代码**的值 —— "
                "12/1/44 是设计常量（圆角/描边/最小点击区），68/48 是设计稿给的控件尺寸"
                "（fixed），23/25 是贴父边的固定间距（pinned 内边距）。"
                "两轴口径下「贴父边 + 固定间距」要写成约束常量，不是写成比例")

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
        # 出处：这份结论必须来自**两轴口径**的生成端。旧口径的计划里只有
        # proportional，fixed / pinned 计数都是 0 —— 拿旧产物交差时这里会立刻暴露，
        # 而两条路（跑脚本 / 手工核对）都得自己走对。
        kinds = report.get("relationKindCounts")
        if not isinstance(kinds, dict) or not kinds:
            problems.append(
                "校验器原始结论缺少 relationKindCounts："
                "无法确认计划是按「尺寸是常量、位置相对直接父视图」生成的两轴计划")
        elif not (kinds.get("fixed") and kinds.get("pinned")):
            problems.append(
                f"校验器原始结论 relationKindCounts={kinds!r}："
                "一条 fixed 或 pinned 关系都没有，用的还是旧的一轴（全 proportional）计划")

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
