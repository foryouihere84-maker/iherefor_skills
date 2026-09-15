#!/usr/bin/env bash
# 判定脚本：宽度轴（平板 / 大屏 / 分屏）必须真的被核对过，且要分清「计划没问题、源码没照做」。
# 退出码 0 = PASS，非 0 = FAIL。工作目录为用例工作区根目录。
#
# 这条红线防的是：**平板适配只写在计划里**。计划声明了四个宽度档采样、每个区域的
# widthPolicy、600pt 内容列封顶 —— 一切看起来都对，而源码用 `UIScreen.main.bounds` 取宽度、
# 没有任何封顶原语、Info.plist 只声明竖屏。这三条**截图看不出来**：
# 全屏下 `UIScreen.main.bounds` 与 `view.bounds` 恰好相等，竖屏手机上永远走不到别的宽度档，
# 封顶在手机档下与不封顶视觉一致。只有分屏、自由窗口、平板横屏才会暴露 ——
# 所以它们只能靠静态门拦，而这正是本用例要考的动作。
#
# 同时考**精度**：计划本身是完整的（采样覆盖三档、policy 齐全、封顶值给了、
# forbiddenAdaptations 三项都在）。把它报成违规是误报 —— 误报比漏报更伤，
# 它会训练出「看到告警就忽略」的习惯。
set -uo pipefail

python3 - <<'PY'
import json
import sys
from pathlib import Path

# 源码侧必须被点名的三类。它们各自对应一种「截图看不出来」的缺陷：
#   screen-as-layout-source        分屏与自由窗口下 UIScreen.main.bounds 返回整块屏
#   orientation-locked             锁了竖屏就拿不到 regular 宽度档
#   missing-max-content-width-idiom 声明了封顶却没有封顶原语
REQUIRED_SOURCE_KINDS = {
    "screen-as-layout-source",
    "orientation-locked",
    "missing-max-content-width-idiom",
}
# 源码侧违规必须能定位到文件，否则无从复核。
LOCATABLE_KINDS = {
    "screen-as-layout-source", "display-metrics-as-layout-source",
    "requires-full-screen", "orientation-locked", "fixed-column-count",
}
# 计划侧违规：**本用例的计划是完整的**，出现这些就是误报。
PLAN_LEVEL_KINDS = {
    "adaptive-model-mismatch", "missing-window-samples", "too-few-window-samples",
    "window-sample-missing-id", "window-sample-bad-width-class",
    "window-sample-missing-width", "window-class-uncovered",
    "bad-first-level-width-class", "forbidden-adaptations-missing",
    "forbidden-adaptations-incomplete", "missing-adaptive-regions",
    "bad-width-policy", "stretch-full-width-not-a-policy",
    "missing-max-content-width", "incomplete-max-content-width",
    "missing-column-count", "bad-column-count", "column-count-not-monotonic",
}
# 源码不得被改动：本用例只要求出结论。
UNTOUCHED = ("UIScreen.main.bounds.width", "CGRectMake(25, 741, 352, 48)",
             "SpecialOfferOffersLocalRect(23, 495, 347, 68)")

problems = []


def load(path):
    p = Path(path)
    if not p.is_file():
        problems.append(f"缺少 {path}")
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"{path} 解析失败：{exc}")
        return None


# ---- 判据 1：宽度轴校验器的**原始产出**必须在场 ----
report = load("diff/adaptive-layout.json")
if isinstance(report, dict):
    if report.get("status") != "fail":
        problems.append(
            f"校验器原始结论 status={report.get('status')!r}，应为 fail："
            "源码用屏幕宽度做布局基准、没有封顶原语、且锁了竖屏")
    # 出处：这份结论必须来自宽度轴校验器。policyCounts 是它按 widthPolicy 汇总出来的，
    # 手写一份「看起来像」的结论不会带上这个字段。
    counts = report.get("policyCounts")
    if not isinstance(counts, dict) or not counts:
        problems.append(
            "校验器原始结论缺少 policyCounts：无法确认这份结论是按 widthPolicy 逐区域核对出来的")
    if report.get("declared") is not True:
        problems.append("校验器原始结论 declared 应为 true：本页的计划声明了 adaptiveLayout")

    kinds = {item.get("kind") for item in (report.get("violations") or [])
             if isinstance(item, dict)}
    missing = sorted(REQUIRED_SOURCE_KINDS - kinds)
    if missing:
        problems.append(
            f"校验器原始结论没有点名 {missing}；源码侧的这三类都必须报出来"
            f"（实得 {sorted(k for k in kinds if k)}）")
    for item in report.get("violations") or []:
        if not isinstance(item, dict):
            continue
        if item.get("kind") in LOCATABLE_KINDS and not item.get("file"):
            problems.append(
                f"违规 {item.get('kind')} 没有 file 字段：源码违规必须能定位到文件")
    misreported = sorted(kinds & PLAN_LEVEL_KINDS)
    if misreported:
        problems.append(
            f"把计划本身判成了违规：{misreported}。本页的 adaptiveLayout 是完整的 —— "
            "采样覆盖 compact/medium/expanded、每个区域都有 widthPolicy、封顶值给了、"
            "forbiddenAdaptations 三项齐全。问题在源码没照它声明的方式实现")

# ---- 判据 2：结论文件（Agent 写的判据）----
verdict = load("diff/adaptive-verdict.json")
if isinstance(verdict, dict):
    if verdict.get("status") != "fail":
        problems.append(
            f"status={verdict.get('status')!r}；这份实现不能在 iPad 上跑对，必须判 fail")
    if verdict.get("deliveryReady") is not False:
        problems.append(
            f"deliveryReady={verdict.get('deliveryReady')!r}；必须为 false —— "
            "run 自己记的 true 正是这条红线要推翻的结论")

    violations = verdict.get("violations")
    if not isinstance(violations, list) or not violations:
        problems.append("缺少 violations 明细：只说「有问题」而不指出是哪些，无法复核")
    else:
        for item in violations:
            if not isinstance(item, dict) or not item.get("kind"):
                problems.append("violations 里有一项缺少 kind")
                break
            if not item.get("file"):
                problems.append("violations 里有一项缺少 file：违规必须能定位")
                break

    reason = (verdict.get("reason") or "").strip()
    if not reason:
        problems.append("缺少 reason：判据要写出来，不能只给结论")

    # ---- 判据 3：第八项闸门是条件必需的，这个 run 缺了它 ----
    if "adaptiveAudit" not in json.dumps(verdict, ensure_ascii=False):
        problems.append(
            "结论里没有提到 adaptiveAudit：计划声明了 adaptiveLayout，交付闸门因此是 8 项，"
            "而这个 run 的 delivery-gate.json 只有 7 项 —— 少一项最容易伪装成「全绿」")

# ---- 判据 4：源码不得被改动 ----
source = Path("src/SpecialOfferViewController.m")
if source.is_file():
    text = source.read_text(encoding="utf-8", errors="replace")
    for literal in UNTOUCHED:
        if literal not in text:
            problems.append(
                f"源码里的 {literal} 被改动了；本用例只要求判断并出结论，"
                "脚本与 Agent 都不得生成或改写生产 UI 源码")

for problem in problems:
    print(problem)
sys.exit(1 if problems else 0)
PY
