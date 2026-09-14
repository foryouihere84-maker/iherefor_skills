#!/usr/bin/env bash
# 判定脚本：基准渲染时的字体替换必须被查出来，且账要记在基准头上。
# 退出码 0 = PASS，非 0 = FAIL。工作目录为用例工作区根目录。
#
# 这一条防的是 run 011 的字体链事故：CSS 声明 AvenirLT-Black、@font-face 规则数为 0、
# 无 generic fallback ⇒ Chromium 静默回落到 Times。基准图于是「自洽地错」——
# domVsReference 判 aligned，对齐审计把不一致归给 App 侧。只读 CSS 声明、
# 或者只信 alignment.json 结论的 Agent，会照着坏基准去改 App，越改越远。
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


def as_list(value):
    """把字符串 / 列表 / {"family": ...} 列表统一压成小写字符串列表。"""
    if value is None:
        return []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        items = [value]
    out = []
    for item in items:
        if isinstance(item, dict):
            item = item.get("family") or item.get("name") or item.get("fontFamily")
        if isinstance(item, str):
            out.append(item.strip().lower())
    return out


def mentions(haystack, needle):
    return any(needle in entry for entry in haystack)


def read_optional(rel):
    """读一个可选文件；不存在或坏了都返回 None，不计入 problems。

    判分器只在工作区里判产物，不能反过来要求素材存在：跑判分器自检时样本目录里
    只有 Agent 的产物，没有 fixture。
    """
    path = Path(rel)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def fixture_expectation():
    """从素材里现算「声明了什么 / 实际回落成了什么」，避免把答案抄进判分器。

    素材在场时以素材为准：fixture 改了字体链，断言跟着改，不会留下一份过期的硬编码。
    素材不在场（判分器自检）时回落到本用例记录在案的常量。
    """
    facts = read_optional("reference/page-facts.json")
    if not facts:
        return {"declared": ["avenirlt-black", "avenirlt-medium"], "declared_hint": "avenirlt",
                "resolved": "times", "source": "builtin", "conclusive": True}
    declared, resolved = set(), set()
    for element in (facts.get("elements") or []):
        if not (element.get("ownsText") or element.get("ownText")):
            continue
        declared |= set(as_list(element.get("fontFamily")))
        resolved |= set(as_list(element.get("primaryFont")))
    # AvenirLT-* 是声明了但没落地的族：只在 declared 里出现，不在 resolved 里出现。
    drifted = sorted(f for f in declared if f and f not in resolved)
    landed = sorted({f for f in resolved if f and f not in declared})
    if not drifted or not landed:
        # 素材在场却推不出「声明过什么 / 回落成什么」⇒ 这份素材坏了。
        # 这里**不能**退化成「跳过前两条断言」：那会让一个照抄 CSS 声明的产物照样通过，
        # 正是本用例要防的恒真式。宁可判挂，把素材问题暴露出来。
        return {"declared": sorted(declared), "declared_hint": None,
                "resolved": None, "source": "fixture-inconclusive", "conclusive": False}
    return {"declared": sorted(declared), "declared_hint": drifted[0].split("-")[0],
            "resolved": landed[0], "source": "reference/page-facts.json", "conclusive": True}


expected = fixture_expectation()


payload = load("diff/font-substitution.json")
if payload is None:
    for problem in problems:
        print(problem)
    sys.exit(1)

probe = payload.get("fontSubstitution") if isinstance(payload.get("fontSubstitution"), dict) else payload

declared = as_list(probe.get("declaredFontFamily") if "declaredFontFamily" in probe
                   else probe.get("declaredFonts"))
resolved = as_list(probe.get("resolvedFontFamily") if "resolvedFontFamily" in probe
                   else probe.get("resolvedFonts") or probe.get("actualFontFamily"))

# ---- 0. 先确认素材本身可判 ----
# 素材在场却推不出「声明过什么 / 回落成什么」，前两条断言就会无处落笔。此时必须判挂：
# 否则一个照抄 CSS 声明的产物会照样通过 —— 判分器自己成了恒真式。
if not expected.get("conclusive", True):
    problems.append(
        f"素材 reference/page-facts.json 里找不到「声明了却没落地」的字体族"
        f"（declared={expected.get('declared')!r}）。本用例的素材必须含一次字体替换，"
        "否则它证明不了任何东西；请检查 fixture 是否被改动，或换一份素材。")

# ---- 1. 声明的族必须如实记录（来源是 CSS，不是猜测） ----
declared_hint = expected.get("declared_hint")
if not declared:
    problems.append("缺少 declaredFontFamily：必须如实记录 CSS 里声明的字体族")
elif declared_hint and not mentions(declared, declared_hint):
    problems.append(
        f"declaredFontFamily={declared!r}；本页 CSS 声明的是 {expected['declared']} 系列，"
        "声明值记错说明没有真去读样式表")

# ---- 2. 实际参与排版的族必须是运行时解析出来的那个，不是 CSS 里那个 ----
claims_missing_family = bool(declared_hint) and mentions(resolved, declared_hint)
if not resolved:
    problems.append(
        "缺少 resolvedFontFamily：字体链的关键证据是**运行时实际用上**的字体，"
        "不是 CSS 声明的那个")
elif claims_missing_family:
    problems.append(
        f"resolvedFontFamily={resolved!r} 直接照抄了 CSS 声明的 {expected.get('declared')}。"
        "本页 @font-face 规则数为 0、没有字体文件，运行时不可能用上这些族；"
        "这个值只能来自读声明而不是读运行时事实（page-facts.json 的 primaryFont / "
        "browser-meta.json 的 fontProbe）")
elif expected.get("resolved") and not mentions(resolved, expected["resolved"]):
    problems.append(
        f"resolvedFontFamily={resolved!r}；基准渲染实际回落到的是 {expected['resolved']}，"
        "请对照 page-facts.json 里各元素的 primaryFont.family")

# ---- 3. 必须明确承认发生了替换 ----
substituted = probe.get("substituted")
if isinstance(substituted, str):
    substituted = substituted.strip().lower() in ("true", "yes", "1")
if substituted is not True:
    problems.append(
        f"substituted={probe.get('substituted')!r}；运行时解析出的族与声明不符，"
        "这就是一次字体替换，必须记为 true")

# ---- 4. 替换必须落到具体元素上，不能只有一个全局结论 ----
affected = probe.get("affectedElements") or probe.get("affected") or []
if not isinstance(affected, (list, tuple)) or len(affected) == 0:
    problems.append("affectedElements 为空：必须指出哪些文本元素受这次替换影响")
else:
    blob = json.dumps(affected, ensure_ascii=False).lower()
    # 至少要覆盖到一个真的被替换的元素：标题 / 徽标 / 价格。
    hints = ("choose your plan", "alpha", "59.99", "header__title", "badge__title",
             "card__price", "avenirlt")
    if not any(hint in blob for hint in hints):
        problems.append(
            f"affectedElements={affected!r} 没有被替换的元素：标题 / 徽标 / 价格这三个"
            "声明 AvenirLT-* 的元素都受影响了")

# ---- 5. evidence 不能是空话 ----
evidence = probe.get("evidence")
if isinstance(evidence, str):
    evidence = [evidence] if evidence.strip() else []
if not isinstance(evidence, (list, tuple)) or len(evidence) == 0:
    problems.append("缺少 evidence：结论必须给出判断依据，不能只有一个断言")

# ---- 6. 核心：账要记在基准头上 ----
fix_side = probe.get("fixSide") or probe.get("responsibleSide") or probe.get("blame")
if not isinstance(fix_side, str):
    problems.append(
        "缺少 fixSide：本用例的核心就是判断该改哪一侧（\"baseline\" 或 \"app\"）")
else:
    normalized = fix_side.strip().lower()
    if normalized in ("app", "application", "implementation", "native"):
        problems.append(
            f"fixSide={fix_side!r}。基准图是「自洽地错」的：DOM 与基准图都用了回落后的 "
            "Times，所以 alignment.json 的 domVsReference 必然判 aligned，"
            "工具会顺着说「问题在 App 实现侧」。这个结论建立在一个坏基准上——"
            "先补字体（@font-face 或换成系统真实存在的族）重渲染基准，再谈 App 改不改")
    elif normalized not in ("baseline", "reference", "html", "render", "lanhu"):
        problems.append(
            f"fixSide={fix_side!r} 不是可识别的取值，应为 \"baseline\" 或 \"app\"")

# ---- 7. 反向恒真式护栏：不能既说没替换又说要改基准 ----
if substituted is not True and isinstance(fix_side, str) and fix_side.strip().lower() == "baseline":
    problems.append("结论自相矛盾：substituted 为 false 却说该改基准")

for problem in problems:
    print(problem)
sys.exit(1 if problems else 0)
PY
