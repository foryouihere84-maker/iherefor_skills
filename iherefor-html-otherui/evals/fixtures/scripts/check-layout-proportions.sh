#!/usr/bin/env bash
# 判定脚本：布局不得照抄探针设备上的量取值 —— 位置要相对直接父视图表达，
# 尺寸要写清由什么闭合（fixed / intrinsic / bounded / aspect-ratio）；
# 同时必须分得清「设备推导出来的绝对坐标」与「报出来就是误报的那几类数字」。
# 退出码 0 = PASS，非 0 = FAIL。工作目录为用例工作区根目录。
#
# 这一条防的是：把设计稿量出来的值当绝对坐标写进约束。它看起来有出处、算过，
# review 时最容易被放过，而换台设备就是错的。
#
# 素材里故意混了三类**报出来就是误报**的值：
#   - 设计常量（圆角 12、发丝线 1、最小点击区 44）；
#   - fixed **候选**尺寸（卡片高 68、按钮高 48）—— 生成端标了 needsReview。
#     闭合契约下它们的问题是「闭合方式待复核」，**不是**「这个值不该出现」；
#   - pinned 的固定内边距（左起 23、右侧 25）—— 「贴父边 + 间距」写约束常量。
# 所以这里既查召回也查精度：两头都错 = 没通过。
#
# 闭合契约给判分带来的第二处变化：fixed 不再是「尺寸是常量」这种一句话豁免。
# 于是本脚本还要查 Agent 有没有把生成端的候选**接住**（reviewPending）——
# 没有这条，「豁免 68/48」可以靠退回旧口径蒙对，而旧口径正是这轮要废掉的东西。
set -uo pipefail

python3 - <<'PY'
import json
import re
import sys
from pathlib import Path

# 只在 402x874 探针设备上成立的绝对坐标：出现在源码里就是违规。
# 这五个值就是生成端 forbiddenLiterals 里那几条 **>48pt** 的 —— 只有被判成 proportional 的
# 位置/尺寸才会入清单，因为只有它们才「换台设备必然不对」。
DEVICE_DERIVED = {321, 495, 741, 83, 801}
# 这几类数值**进了 violations 就是误报**：
#   12 / 1 / 44  设计常量（圆角、发丝线、最小点击区）
#   68 / 48      生成端推的 fixed **候选**（卡片高、按钮高）。闭合契约下它们的问题是
#                「闭合方式待复核」，结论该写进 reviewPending，而不是「这个值不该出现」；
#   23 / 25      第一层子视图的水平位置（offers.x / cta.x）。它们按契约是
#                forced-proportional（按页面宽度比例），写死也是错 —— 但因为 ≤48pt，
#                检查端无法与设计常量自动区分，只能落 ambiguousLiterals 待人工判断，
#                而不是硬性 violation。判分同样不能把 23/25 报成**硬违规**：
#                Agent 若把它们与 83/801 一样判成 forbidden-literal-used，就是误报。
# 所以这里既查召回也查精度：两头都错 = 没通过。
MUST_NOT_BE_VIOLATION = {12, 1, 44, 68, 48, 23, 25}
# 至少要点名几条设备推导值。真实执行路径（跑校验器）会给出全部五条；
# 手工核对也至少该抓住最显眼的几个大数值。
MIN_DEVICE_DERIVED_NAMED = 3
# 生成端标了 needsReview 的候选关系（用于查 Agent 有没有把候选接住）。
REVIEW_CANDIDATES = ("offers.height", "cta.height")

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


def mentions(item, relation):
    """条目是否指向某条关系。用 json 串判，容忍 ``offers.height`` 写成 ``offers -> height``。"""
    text = json.dumps(item, ensure_ascii=False)
    if relation in text:
        return True
    region, _, axis = relation.partition(".")
    return region in text and axis in text


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

        # 精度：不该报成违规的那几类值不得出现在 violations 里。
        misreported = sorted(hit & {float(v) for v in MUST_NOT_BE_VIOLATION})
        if misreported:
            problems.append(
                f"把 {misreported} 报成了违规；这几类都**不该进 violations** —— "
                "12/1/44 是设计常量（圆角/描边/最小点击区），68/48 是生成端推的 fixed "
                "**候选**（问题是闭合方式待复核，结论该写进 reviewPending），"
                "23/25 是 ≤48pt、与设计常量无法自动区分的待判值（落 ambiguousLiterals）。"
                "把它们算成违规，等于要求实现者不要按设计稿做")

        # 每条违规要能指到文件，否则无法复核
        if not any(isinstance(i, dict) and i.get("file") for i in violations):
            problems.append("violations 里没有 file 字段：违规必须能定位到源码文件")

    if not (verdict.get("reason") or "").strip():
        problems.append("缺少 reason：判据要写出来，不能只给结论")

    # 闭合契约：fixed 只是生成端给的**候选**，Agent 必须逐条复核。
    # 这条断言就是「接住了候选」的可执行版本 —— 没有它，「豁免 68/48」可以靠
    # 退回旧口径（尺寸是常量）蒙对，而旧口径正是这轮要废掉的东西：判分器不能对
    # 「复核过」与「照信了旧结论」的差别无感。
    # 只要求点到 REVIEW_CANDIDATES 之一：生成端的候选集合会随 max-regions 等参数略变，
    # 卡死成两条会把「策略不同」误判成「没接住」。
    review = None
    for key in ("reviewPending", "needsReview", "pendingReview"):
        if isinstance(verdict.get(key), list):
            review = verdict[key]
            break
    if review is None:
        problems.append(
            "diff/layout-verdict.json 缺少 reviewPending 数组："
            "生成端把 offers.height / cta.height 推成 fixed 时标了 needsReview，"
            "Agent 必须把候选接住并给出复核结论")
    elif not review:
        problems.append("reviewPending 是空数组：生成端标了候选，不可能一条都不用复核")
    else:
        flagged = [item for item in review
                   if any(mentions(item, rel) for rel in REVIEW_CANDIDATES)]
        if not flagged:
            problems.append(
                "reviewPending 里没有 offers.height / cta.height："
                "生成端标了 needsReview 的正是这两条，候选没被接住")
        # 到此为止，不再要求「复核结论必须写得够长/含某个词」。理由：这条判据一旦
        # 去匹配措辞（「改判 intrinsic」「复核通过」…），就会开始惩罚写法不同但同样
        # 正确的回答 —— 判分器要么确定性，要么交给 agent_judge，不能靠关键词假装确定。
        # 「接住了候选」这件事本身（关系名被点名）已经足以区分新契约与旧口径的读法。

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
        # 出处：这份结论必须来自**闭合契约**版的校验器（schemaVersion >= 4）。
        # v3 及更早的产物里 kind=fixed 的含义是「尺寸是常量」——那是本轮废掉的口径，
        # 而它在 JSON 里长得和 v4 几乎一样（同样有 relationKindCounts），只能靠版本号区分。
        version = report.get("schemaVersion")
        if not isinstance(version, int) or version < 4:
            problems.append(
                f"校验器原始结论 schemaVersion={version!r}：应 ≥ 4（闭合契约）。"
                "v3 产物里的 fixed 是「尺寸是常量」的老结论，不能拿它交差")
        # 位置轴：这个页面的第一层子视图必须挂在父视图上，不能全是比例、也不能全写死。
        # 这里**故意不要求 kinds['fixed']** —— 闭合契约下 fixed 是候选，一个复核得对的
        # Agent 很可能把 offers.height / cta.height 改判成 intrinsic / bounded，于是
        # fixed 计数为 0。要求「fixed > 0」会把正确实现判挂，那正是本轮要修的病。
        kinds = report.get("relationKindCounts")
        if not isinstance(kinds, dict) or not kinds:
            problems.append(
                "校验器原始结论缺少 relationKindCounts："
                "无法确认计划是按闭合契约生成的多类关系计划")
        else:
            missing = [k for k in ("pinned", "proportional") if not kinds.get(k)]
            if missing:
                problems.append(
                    f"校验器原始结论 relationKindCounts={kinds!r}：缺少 {missing} —— "
                    "位置既没有贴父边的约束闭合、也没有成比例的关系，"
                    "用的还是旧的一轴（全 proportional 或全写死）计划")

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
