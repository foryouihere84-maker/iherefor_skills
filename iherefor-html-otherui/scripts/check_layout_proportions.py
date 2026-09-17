#!/usr/bin/env python3
"""核对原生源码是否按 ``layoutProportions`` 声明的**闭合契约**实现布局。

**这是计划驱动，不是正则扫描。** 判据是「计划声明了什么类别」：

* ``proportional`` —— 要求比例表达，源码里没有比例原语就是违规；
* ``fixed`` —— 要求**写字面量**（设计值不缩放）。所以它的值**不得**出现在
  禁止清单里：把「图标 24」当成违规，等于让正确写法被判错；
* ``pinned`` —— 要求贴边约束（+ 固定间距），**不得**带比例系数；
* ``intrinsic`` —— 不要求尺寸约束，但必须说明为什么；**源码里该轴不得出现等值常量约束**
  （那正是「声明了内容撑开、代码却写死宽高」这个头号漏洞）；
* ``bounded`` —— 必须给上下界，且源码里该轴要出现 ``>=`` / ``<=`` 原语；
* ``equal`` —— 用兄弟等值锚点表达；
* ``centered`` —— 用对齐锚点表达，不得带比例系数；
* ``aspect-ratio`` —— 必须给正数比例，且源码里要出现比例约束原语。

纯正则扫描会把合法的设计常量（圆角 12、标准边距 16）一起误报，训练出「看到告警就
忽略」的习惯，那样这条红线就废了。所以每一类都有它自己的、可解释的判据。

五类违规，各自对应一种真实的错法：

1. ``forbidden-literal-used`` —— 源码里出现了 ``forbiddenLiterals`` 记录的
   「探针设备推导值」。这是最典型的一种：把 ``lanhuY * 1.0229 = 135.02`` 算出来，
   然后原样敲进约束。数字看起来有出处、算过，review 时最容易被放过。
   **注意这张清单现在只收 ``proportional`` 的关系** —— ``fixed`` 的字面量与
   ``pinned`` 的内边距都是**应当写的**设计常量，列进去就把正确做法判成了错。
2. ``no-proportional-idiom`` —— 计划声明了比例，但源码里一个比例原语都没有。
   说明整页都是拿绝对值堆出来的。
3. ``unknown-relation-kind`` / ``fixed-missing-value`` / ``pinned-with-ratio`` 等
   —— 计划自身的形状问题。计划是 Agent 写的，类别写错、贴边关系带上比例系数，
   都是回不去的硬伤，必须在源码之前拦住。
4. ``forbidden-targets-non-proportional`` —— 禁止清单指向了一条 ``fixed``/``pinned``
   关系。这等于要求实现者**不要写**设计稿给的常量，正是「契约没改完」的形态：
   生成端改了、检查端没跟上，两边自相矛盾。
5. ``intrinsic-axis-pinned-to-constant`` —— 计划把某区域某轴声明为 ``intrinsic`` 或
   ``bounded``，源码里该区域的该轴却出现了**等值常量**约束。这是旧契约的直接残留：
   设计稿给了一个宽高，实现照抄成固定约束。``>=`` / ``<=`` 不算违规（那是 bounded
   的正确写法），只有 ``==`` 常量才是。

**关于精度。** 在真实工程上第一次跑，421 条字面量命中里：145 条是裸 ``0``、17 条在注释里
（``// (393 x 852, index.css .page)``、``// an iOS 26 scene``）、若干条是颜色的
``22 / 255.0`` 通道值，另外「一个字面量撞上 4 条同值关系」被记成 4 条。
这种量级的噪音会把真信号淹掉，而「看到告警就忽略」正是这条红线失效的方式。所以：

* 注释先去掉 —— 注释里写设计尺寸是在解释，不是违规；把注释当违规等于让人去改注释；
* ``100%``、``colorWithRed:22 / 255.0`` 这类非布局数字跳过：百分号本就是相对单位；
* ``|pt| < 1`` 的设备推导值不作证据：``0`` 在任何设备上都成立，与设备无关；
* 同一个字面量只记一条，命中的其它关系放进 ``alsoMatches``；
* ``≤ DESIGN_SCALE_MAX_PT``（48pt）的数值与常见设计常量无法区分，只进
  ``ambiguousLiterals`` 待判，**不计入违规** —— 闸门要准，不是要响；
* 计划可用 ``designConstants`` 声明设计常量（标准边距、圆角），或用 ``--allow-values``
  临时豁免 —— 豁免会被写进 JSON 结果，仍可复核。

本脚本做的是**行级**扫描，不做语法解析：它认的是各平台的布局原语与数字字面量。
因此结论的措辞是「找到了这些证据 / 这些违规」，而不是「代码是对的」—— 布局是否
真的正确仍由截图与对齐审计回答。

用法：

    python3 scripts/check_layout_proportions.py \\
        --plan <run>/ui-implementation-plan.json \\
        --source <工程源码目录或文件>... [--target-mode ios-uikit-objective-c]

退出码：0 = 通过；1 = 存在违规；2 = 用法或证据问题（计划读不到等）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 各平台表达「比例/相对」的原语。命中任意一个即认为该处用了比例。
#
# ``match_parent`` **不在**这一组里：它是「铺满」而不是「比例」——把它算作比例原语，
# 会让「计划声明了比例、源码其实一处比例都没有」这种情况溜过去。它属于 pinned。
PROPORTIONAL_IDIOMS = (
    (r"multiplier\s*[:=]", "iOS multiplier"),
    (r"UILayoutGuide", "UILayoutGuide 占位"),
    (r"GeometryReader", "SwiftUI GeometryReader"),
    (r"containerRelativeFrame", "SwiftUI containerRelativeFrame"),
    (r"BoxWithConstraints", "Compose BoxWithConstraints"),
    (r"fillMax(?:Width|Height|Size)\s*\(\s*[\d.]+\s*f?\s*\)", "Compose fillMax* 比例"),
    (r"max(?:Width|Height)\s*\*", "Compose max* 派生比例"),
    (r"\.weight\s*\(", "Compose weight"),
    (r"layout_constraintGuide_percent", "ConstraintLayout percent guide"),
    (r"layout_constraint(?:Horizontal|Vertical)_bias", "ConstraintLayout bias"),
    (r"layout_constraintDimensionRatio", "ConstraintLayout dimensionRatio"),
    (r"layout_weight", "LinearLayout layout_weight"),
)
PROPORTIONAL_RE = re.compile("|".join(f"(?:{p})" for p, _ in PROPORTIONAL_IDIOMS))

# 表达「贴边 / 铺满 / 对齐」的原语。**只用于告警**（见 main 里的 pinned 一致性提示）：
# 计划声明了 pinned 关系，源码里却一处贴边原语都没有，那它很可能被写成了绝对 frame。
PINNED_IDIOMS = (
    (r"match_parent|fill_parent", "父容器铺满"),
    (r"constraintEqualTo(?:Constant|Anchor)?\b", "iOS 约束闭合"),
    (r"safeAreaLayoutGuide|layoutMarginsGuide", "iOS 安全区/边距锚点"),
    (r"layout_constraint\w+_to\w+Of", "ConstraintLayout 边对边约束"),
    (r"fillMax(?:Width|Height|Size)\s*\(\s*\)", "Compose 铺满"),
    (r"frame\s*\(\s*maxWidth:\s*\.infinity", "SwiftUI 铺满"),
)
PINNED_RE = re.compile("|".join(f"(?:{p})" for p, _ in PINNED_IDIOMS))

# 「边界」原语：表达 >= / <= 或 min/max。声明了 bounded 的计划必须能在源码里找到它们 ——
# 找不到说明实现者仍按旧契约把尺寸写成了等值常量（或压根没有边界）。
BOUNDED_IDIOMS = (
    (r"greaterThanOrEqual(?:ToConstant|ToAnchor|To)?\b", "iOS >= 约束"),
    (r"lessThanOrEqual(?:ToConstant|ToAnchor|To)?\b", "iOS <= 约束"),
    (r"constraintGreaterThanOrEqualToConstant|constraintLessThanOrEqualToConstant", "iOS 边界约束"),
    (r"layout_constraint(?:Width|Height)_(?:min|max)", "ConstraintLayout min/max"),
    (r"\bmin(?:Width|Height)\b|\bmax(?:Width|Height)\b", "min/max 属性"),
    (r"widthIn\s*\(|heightIn\s*\(|sizeIn\s*\(", "Compose widthIn/heightIn"),
    (r"greaterThanOrEqualToConstant|lessThanOrEqualToConstant", "边界常量"),
)
BOUNDED_RE = re.compile("|".join(f"(?:{p})" for p, _ in BOUNDED_IDIOMS))

# 「兄弟等值 / 等分」原语：声明了 equal 的计划应当能在源码里找到它们。
# 只作**告警**：等宽等高可以用很多方式表达（UIStackView 的 fillEqually、
# HStack + maxWidth: .infinity、IntrinsicSize、layout_weight），清单不可能穷尽。
EQUAL_IDIOMS = (
    (r"fillEqually", "UIStackView fillEqually"),
    (r"distribution\s*[:=]\s*\.fillEqually", "分布等分"),
    (r"equalTo\w*Anchor|constraintEqualToAnchor", "iOS 等值锚点"),
    (r"layout_weight|layout_constraintHorizontal_weight|layout_constraintVertical_weight", "权重等分"),
    (r"IntrinsicSize", "Compose IntrinsicSize"),
    (r"\.weight\s*\(", "Compose weight"),
)
EQUAL_RE = re.compile("|".join(f"(?:{p})" for p, _ in EQUAL_IDIOMS))

# 「比例约束」原语：声明了 aspect-ratio 的计划应当能找到它们。
ASPECT_IDIOMS = (
    (r"aspectRatio\s*\(", "SwiftUI aspectRatio"),
    (r"layout_constraintDimensionRatio", "ConstraintLayout dimensionRatio"),
    (r"widthAnchor[\s\S]{0,80}?multiplier|heightAnchor[\s\S]{0,80}?multiplier", "iOS 比例约束"),
    (r"aspect_ratio|aspectRatio", "比例约束"),
)
ASPECT_RE = re.compile("|".join(f"(?:{p})" for p, _ in ASPECT_IDIOMS))

# 「内容自适应」支撑原语：Dynamic Type 与优先级。声明了 intrinsic/bounded 的计划
# 说明页面里有内容驱动的尺寸，那就应当看到这些原语。缺失只作**告警**：
# 有些页面确实没有文字（纯图形页），没有它们不算错。
CONTENT_ADAPTIVITY_IDIOMS = (
    (r"UIFontMetrics|preferredFont|scaledFont|adjustsFontForContentSizeCategory",
     "Dynamic Type 字号缩放"),
    (r"setContentHuggingPriority|contentHuggingPriority|huggingPriority",
     "content hugging 优先级"),
    (r"setContentCompressionResistancePriority|contentCompressionResistancePriority|compressionResistancePriority",
     "compression resistance 优先级"),
    (r"DynamicTypeSize|relativeTo\s*:|\.font\s*\(\s*\.(body|title|caption|headline|footnote|callout|subheadline|largeTitle)",
     "Dynamic Type 文本样式"),
)
CONTENT_ADAPTIVITY_RE = re.compile("|".join(f"(?:{p})" for p, _ in CONTENT_ADAPTIVITY_IDIOMS))

# 「等值常量」的尺寸原语，**按轴分开**。只认 ``==`` 常量，不认 ``>=`` / ``<=`` ——
# 后者是 bounded 的正确写法。命中即说明「计划说内容撑开、代码写死了」。
SIZE_CONSTANT_PATTERNS = {
    "width": (
        (r"widthAnchor\s*\]?\s*constraintEqualToConstant", "iOS 定宽约束"),
        (r"widthAnchor\s*\.\s*constraint\s*\(\s*equalToConstant", "Swift 定宽约束"),
        (r"\.frame\s*\([^)]*?\bwidth\s*:\s*[\d.]", "SwiftUI 定宽"),
        (r"\.width\s*\(\s*[\d.]+\s*(?:\.dp|\.pt)?\s*\)", "Compose 定宽"),
        (r"android:layout_width\s*=\s*\"[\d.]+", "XML 定宽"),
        (r"android:width\s*=\s*\"[\d.]+", "XML 定宽属性"),
    ),
    "height": (
        (r"heightAnchor\s*\]?\s*constraintEqualToConstant", "iOS 定高约束"),
        (r"heightAnchor\s*\.\s*constraint\s*\(\s*equalToConstant", "Swift 定高约束"),
        (r"\.frame\s*\([^)]*?\bheight\s*:\s*[\d.]", "SwiftUI 定高"),
        (r"\.height\s*\(\s*[\d.]+\s*(?:\.dp|\.pt)?\s*\)", "Compose 定高"),
        (r"android:layout_height\s*=\s*\"[\d.]+", "XML 定高"),
        (r"android:height\s*=\s*\"[\d.]+", "XML 定高属性"),
    ),
}
SIZE_CONSTANT_RES = {axis: [(re.compile(p, re.IGNORECASE), name) for p, name in table]
                     for axis, table in SIZE_CONSTANT_PATTERNS.items()}

# 计划里合法的关系类别（闭合契约，两轴八类）。见 references/sizing-and-positioning.md。
RELATION_KINDS = ("fixed", "pinned", "proportional", "intrinsic", "bounded",
                  "equal", "centered", "aspect-ratio")
# 带「比例系数」的字段名。两轴八类里**只有 proportional 与 aspect-ratio 带系数**，
# 其余六类带这些字段就是自相矛盾 —— 它们的意思分别是「写死设计值」「贴父边」
# 「对齐父视图中心」「内容撑开」「边界约束」「与同类相等」，都不需要系数。
# （不写成「fixed/pinned/centered 三类不带系数」：列一半的写法本文件与
# layout_proportions.py 各写过一份，第三项还对不上，正是漂移的入口。）
RATIO_FIELDS = ("ratio", "multiplier", "ratioInstead")
# fixed 是「设计稿给的封闭值」，量级上不可能是几百 pt —— 那更像漏了约束的容器。
FIXED_VALUE_MAX_PT = 1000.0
# forbiddenLiterals 的 relation 用锚点名（{region}.leading），relations 用轴名（{region}.x）。
ANCHOR_AXIS = {"centerX": "x", "leading": "x", "centerY": "y", "top": "y",
               "width": "width", "height": "height"}


# 数字字面量：整数/小数，可带常见单位后缀。用 lookaround 排除标识符内的数字。
NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])")

SOURCE_SUFFIXES = {".swift", ".m", ".mm", ".h", ".kt", ".kts", ".java", ".xml"}

DEFAULT_LITERAL_TOLERANCE = 0.05
# 与 layout_proportions.MIN_MEANINGFUL_PT 对齐：接近原点的绝对值不构成证据。
MIN_MEANINGFUL_PT = 1.0
# 数值高于这个量级时它不可能是一个手选的设计常量：没有人把 393pt 当圆角，
# 也没有人把 472pt 当标准边距。低于这个量级的数值（16/24/32）既可能是设计常量，
# 也可能是抄来的设备值，没有语法信息时无法区分 —— 因此降级为「待判」，
# 计入 warnings 而不计入违规。闸门要准，不是要响。
DESIGN_SCALE_MAX_PT = 48.0
MAX_REPORT_PER_FILE = 6


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"读取失败 {path}：{error}", file=sys.stderr)
        return None


def collect_sources(paths) -> list:
    """展开文件与目录；只收与该 skill 相关的源码后缀。"""
    files, missing = [], []
    for raw in paths or []:
        path = Path(raw)
        if path.is_dir():
            files.extend(p for p in sorted(path.rglob("*"))
                         if p.suffix.lower() in SOURCE_SUFFIXES and p.is_file())
        elif path.is_file():
            files.append(path)
        else:
            missing.append(raw)
    return files, missing


def idiom_hits(lines, table=PROPORTIONAL_IDIOMS, pattern=None) -> list:
    """扫出使用某类布局原语的行。

    默认扫比例原语。表与正则一起传（而不是在函数里写死）是为了让「比例」与「贴边」
    两套原语**各有各的清单**：把 ``match_parent`` 混进比例清单，会让「声明了比例、
    源码一处比例都没有」这种情况溜过去 —— 那是这条红线最容易失效的方式。
    """
    matcher = pattern or PROPORTIONAL_RE
    hits = []
    for number, text in enumerate(lines, start=1):
        if matcher.search(text):
            label = next((name for pattern, name in table
                          if re.search(pattern, text)), "相对布局原语")
            hits.append({"line": number, "idiom": label, "text": text.strip()[:120]})
    return hits


def strip_comments(lines) -> list:
    """去掉注释，再在剩下的代码里找数字。

    真实工程里注释必然会写明设计尺寸 —— 实测有 ``// (393 x 852, index.css .page)``、
    ``// an iOS 26 scene``。把这些当违规，等于让人去改注释：既没用又荒谬。
    只从注释起始处截断，注释之前的代码原样保留，所以不会漏掉同一行上的真实字面量。

    副作用是字符串里的 ``//``（如 URL）之后的内容也会被丢掉。方向上是**更少报**，
    而 URL 本来也不是布局，可以接受。
    """
    out, in_block = [], False
    for text in lines:
        if in_block:
            end = text.find("*/")
            if end < 0:
                out.append("")
                continue
            in_block = False
            text = text[end + 2:]
        while True:
            start = text.find("/*")
            if start < 0:
                break
            end = text.find("*/", start + 2)
            if end < 0:
                in_block = True
                text = text[:start]
                break
            text = text[:start] + " " + text[end + 2:]
        for opener, closer in (("//", None), ("<!--", "-->")):
            idx = text.find(opener)
            if idx < 0:
                continue
            if closer is None:
                text = text[:idx]
            else:
                end = text.find(closer, idx)
                text = text[:idx] + (" " + text[end + len(closer):] if end >= 0 else "")
        out.append(text)
    return out


def is_non_layout_number(text: str, match) -> bool:
    """这个数字是「非布局量」吗？

    两类各有理由：

    * ``100%`` —— 百分号本身就是相对单位，它是比例的另一种写法，正好是本红线鼓励
      的东西，绝不能当成「写死的绝对值」；
    * ``colorWithRed:22 / 255.0`` —— 颜色通道。它跟布局没有关系。
    """
    tail = text[match.end():]
    if tail.lstrip().startswith("%"):
        return True
    # 颜色通道：紧跟着 /255（或 / 255.0）的就是通道值。
    if re.match(r"\s*/\s*255(?:\.0*)?(?![.\d])", tail):
        return True
    return False


def literal_hits(lines, forbidden, tolerance: float, allow_values) -> tuple:
    """找出源码里等于「探针设备推导值」的字面量，返回 (违规, 待判)。

    降噪规则，每一条都是为了保住信噪比（理由见模块 docstring）：

    * 注释先去掉；``%`` 与 ``/255`` 这类非布局数字跳过；
    * 整行已经是比例表达时跳过：``multiplier: 0.87786`` 里的数字是比例本身，
      不是被误写的绝对值；
    * ``|pt| < MIN_MEANINGFUL_PT`` 的条目不作证据，``allow_values`` 里的值直接豁免；
    * 同一个字面量只记**一条**记录 —— 计划里多条关系可能恰好同值（实测如此），
      逐条记会让一个 ``23`` 变成 4 条；
    * 数值 ≤ ``DESIGN_SCALE_MAX_PT`` 时无法与设计常量区分，降级进「待判」。
    """
    usable = [item for item in forbidden
              if isinstance(item.get("deviceDerivedPt"), (int, float))
              and abs(item["deviceDerivedPt"]) >= MIN_MEANINGFUL_PT]
    code_lines = strip_comments(lines)
    violations, ambiguous = [], []
    for number, raw in enumerate(lines, start=1):
        text = code_lines[number - 1]
        if PROPORTIONAL_RE.search(text):
            continue
        for match in NUMBER_RE.finditer(text):
            value = float(match.group(1))
            if is_non_layout_number(text, match):
                continue
            if any(abs(value - allowed) <= tolerance for allowed in allow_values):
                continue
            candidates = [item for item in usable
                          if abs(value - item["deviceDerivedPt"]) <= tolerance]
            if not candidates:
                continue
            best = min(candidates, key=lambda i: abs(value - i["deviceDerivedPt"]))
            others = [c.get("relation") for c in candidates if c is not best]
            record = {
                "relation": best.get("relation"),
                "literal": value,
                "deviceDerivedPt": best["deviceDerivedPt"],
                "expectedRatio": best.get("ratioInstead"),
                "alsoMatches": others[:5],
                "candidateCount": len(candidates),
                "line": number,
                "text": raw.strip()[:120],
            }
            if abs(value) > DESIGN_SCALE_MAX_PT:
                violations.append({"kind": "forbidden-literal-used", **record})
            else:
                ambiguous.append({
                    "kind": "ambiguous-literal",
                    "detail": f"{value:g} 等于 {best.get('relation')} 在探针设备上的值，"
                              f"但也在常见设计常量范围内（≤{DESIGN_SCALE_MAX_PT:g}pt），"
                              "无法自动区分；请人工确认它是设计常量还是抄来的设备值",
                    **record})
    return violations, ambiguous


def _ratio_fields(rel) -> list:
    """关系里出现了哪些「比例系数」字段。"""
    return [key for key in RATIO_FIELDS if key in rel]


def check_relations(relations) -> list:
    """计划里每条关系的**类别与配套字段**是否自洽。

    每一类都有它必须带、且必须不带的东西 —— 判据来自类别本身的定义，不是格式偏好：

    * ``fixed`` 必须给 ``value``（设计稿的封闭值）。没有值，实现者无从下手；
      带了 ``ratio`` 就自相矛盾：那等于说「这个值既是设计常量又随容器缩放」。
    * ``pinned`` 必须给 ``edges``/``edge``（贴哪条边），且 **不得带比例系数** ——
      「左右各 16pt」写成本来就是约束，写成 ``width = parent.width * 0.9186``
      在探针设备上同样对得上，却在 430pt 宽的设备上给出 13.7pt 边距。
      这个错法最隐蔽：它在设计稿那一台设备上**永远**是对的。
    * ``centered`` 用对齐锚点表达，同样不带系数。
    * ``proportional`` 必须给 ``ratio``，并给 ``of``（基准）—— 基准缺失时
      实现者只能猜是相对整页还是相对父视图，而这两者在单页单设备上等价，
      换了父容器尺寸就分道扬镳。
    * ``intrinsic`` 必须给 ``why``：不给理由的「内容撑开」与「我懒得管」无从区分。
    """
    problems = []
    for rel in relations or []:
        kind = rel.get("kind")
        rid = rel.get("id")

        if kind not in RELATION_KINDS:
            problems.append({
                "kind": "unknown-relation-kind",
                "relation": rid,
                "detail": f'kind={kind!r}，只能是 {", ".join(RELATION_KINDS)} 之一'
                          "（闭合契约：尺寸轴 fixed/intrinsic/bounded/aspect-ratio，"
                          "关系轴 pinned/proportional/equal/centered。fixed 不是默认值）",
            })
            continue

        if kind == "intrinsic":
            if not (rel.get("why") or "").strip():
                problems.append({
                    "kind": "intrinsic-missing-why",
                    "relation": rid,
                    "detail": "声明为 intrinsic 的关系必须写明 why：为什么这个量不随容器缩放",
                })
            continue

        if kind == "bounded":
            minimum = rel.get("min")
            maximum = rel.get("max")
            if minimum is None and maximum is None:
                problems.append({"kind": "bounded-missing-limit", "relation": rid,
                                 "detail": "kind=bounded 至少需要 min 或 max"})
            for label, value in (("min", minimum), ("max", maximum)):
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0):
                    problems.append({"kind": "bounded-invalid-limit", "relation": rid,
                                     "detail": f"bounded 的 {label} 必须是 ≥ 0 的数字"})
            if minimum is not None and maximum is not None and minimum > maximum:
                problems.append({"kind": "bounded-inverted-limits", "relation": rid,
                                 "detail": "bounded 的 min 不能大于 max"})
            continue

        if kind == "equal":
            if not (rel.get("with") or rel.get("to")):
                problems.append({"kind": "equal-missing-peer", "relation": rid,
                                 "detail": "kind=equal 必须给 with 或 to，声明等宽/等高对象"})
            continue

        if kind == "aspect-ratio":
            ratio = rel.get("ratio")
            if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or ratio <= 0:
                problems.append({"kind": "aspect-ratio-invalid", "relation": rid,
                                 "detail": "kind=aspect-ratio 必须给正数 ratio"})
            continue

        if kind == "fixed":
            value = rel.get("value")
            # fixed 是**特例**，不是默认值：它必须带 why，说明「固定性本身是设计意图」。
            # 闭合契约下这条判据是必须的 —— 设计稿给了 bounds.width/height 是**事实**，
            # 把它写成固定约束是**决策**。没有 why，两者在产物里长得一模一样，
            # 于是「照抄设计稿尺寸」这个新契约要拦的头号问题就没有任何可核对的痕迹。
            if not (rel.get("why") or "").strip():
                problems.append({
                    "kind": "fixed-missing-why",
                    "relation": rid,
                    "detail": "kind=fixed 必须写明 why：为什么这个尺寸的**固定性本身是设计意图**"
                              "（图标、装饰、边框、明确固定高度的视觉控件）。"
                              "理由不能是「设计稿就写了这个数」——那是参考事实，不是决策依据。"
                              "文本、按钮、容器和内容区域默认优先 intrinsic / bounded；"
                              "生成端产出的 fixed 都是候选（带 needsReview），必须逐条复核。",
                })
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                problems.append({
                    "kind": "fixed-missing-value",
                    "relation": rid,
                    "detail": f"kind=fixed 必须给数字 value（设计稿的封闭值），"
                              f"收到 {value!r}；没有值实现者无从下手",
                })
            elif value <= 0:
                problems.append({
                    "kind": "fixed-missing-value",
                    "relation": rid,
                    "detail": f"fixed 的 value={value!r} 必须为正数",
                })
            elif value > FIXED_VALUE_MAX_PT:
                problems.append({
                    "kind": "fixed-value-implausible",
                    "relation": rid,
                    "detail": f"fixed 的 value={value:g}pt 超过 {FIXED_VALUE_MAX_PT:g}pt："
                              "这不像设计稿给的控件尺寸，更像一个漏了约束的容器。"
                              "请确认它应当是 pinned（贴父边闭合）还是 proportional",
                })
            if _ratio_fields(rel):
                problems.append({
                    "kind": "fixed-with-ratio",
                    "relation": rid,
                    "detail": f"kind=fixed 不得带比例系数（{_ratio_fields(rel)}）："
                              "fixed 的意思是「写设计稿给的字面量、不随容器缩放」，"
                              "带上系数就自相矛盾了",
                })
            continue

        if kind == "pinned":
            edges = rel.get("edges") or ([rel["edge"]] if rel.get("edge") else [])
            if not edges:
                problems.append({
                    "kind": "pinned-missing-edge",
                    "relation": rid,
                    "detail": "kind=pinned 必须给 edges（或 edge）：贴哪条父边",
                })
            if _ratio_fields(rel):
                problems.append({
                    "kind": "pinned-with-ratio",
                    "relation": rid,
                    "detail": f"贴边关系不得带比例系数（{_ratio_fields(rel)}）："
                              "贴父边的正确写法是约束闭合（leading = parent.leading + 16）。"
                              "写成 width = parent.width * 0.9186 在探针设备上同样对得上，"
                              "换台设备就是错的",
                })
            inset = rel.get("inset")
            if inset is not None and (isinstance(inset, bool)
                                      or not isinstance(inset, (int, float)) or inset < 0):
                problems.append({
                    "kind": "pinned-bad-inset",
                    "relation": rid,
                    "detail": f"pinned 的 inset={inset!r} 必须是 ≥ 0 的数字",
                })
            continue

        if kind == "centered":
            if _ratio_fields(rel):
                problems.append({
                    "kind": "centered-with-ratio",
                    "relation": rid,
                    "detail": f"kind=centered 不得带比例系数（{_ratio_fields(rel)}）："
                              "居中的正确写法是对齐父视图中心锚点，不要各自算数值凑相等",
                })
            continue

        # kind == "proportional"
        ratio = rel.get("ratio")
        if isinstance(ratio, bool) or not isinstance(ratio, (int, float)):
            problems.append({
                "kind": "proportional-missing-ratio",
                "relation": rid,
                "detail": f"kind=proportional 必须给数字 ratio，收到 {ratio!r}",
            })
        if not (rel.get("of") or "").strip():
            problems.append({
                "kind": "proportional-missing-basis",
                "relation": rid,
                "detail": "kind=proportional 必须给 of（比例基准，通常是直接父视图）："
                          "基准缺失时实现者只能猜是相对整页还是相对父视图，"
                          "而这两者在单页单设备上等价、换了父容器尺寸就分道扬镳",
            })
    return problems


def check_bases(regions) -> list:
    """每个区域的位置基准必须与它自己声明的父视图一致。

    这是「位置相对父视图」那条规范的可执行版本。两个字段说了同一件事，
    对不上就是层级信息在中途丢了：``parentIndex`` 说这个元素挂在某个父视图下，
    而关系却写 ``of: "root"`` —— 实现者会照 root 定位，嵌套组件的内部布局
    在父容器变尺寸时会一起漂移。

    只在本区域确实带了层级字段时才查：手写的精简计划没有这些字段，
    对它提要求只会制造假告警。
    """
    problems = []
    for region in regions or []:
        has_parent = "parentIndex" in region
        basis = region.get("basis")
        if not has_parent and basis is None:
            continue
        parent_index = region.get("parentIndex")
        if has_parent and basis is not None:
            expected = "parent" if parent_index is not None else "viewport"
            if basis != expected:
                problems.append({
                    "kind": "basis-mismatch",
                    "relation": f"{region.get('region')}（区域基准）",
                    "detail": f"parentIndex={parent_index!r} 与 basis={basis!r} 不一致："
                              f"存在父视图时 basis 应为 'parent'，父为整屏画布时才是 "
                              f"'viewport'（期望 {expected!r}）",
                })
        if basis != "parent":
            continue
        for rel in region.get("relations") or []:
            if rel.get("of") == "root":
                problems.append({
                    "kind": "basis-mismatch",
                    "relation": rel.get("id"),
                    "detail": "区域的基准是父视图，但这条关系的 of 写成了 'root'："
                              "位置必须相对直接父视图，只有父容器本身就是整屏画布时才用 root",
                })
    return problems


def check_forbidden_targets(plan) -> list:
    """禁止清单必须**只**指向 ``proportional`` 的关系。

    这条是「契约级变更必须一次改完」的可执行版本。旧版生成器对非文字元素的尺寸一律
    收录禁止项，于是「按钮高 44」这类**内容驱动的尺寸**被列为禁止 —— 实现者照契约做
    反而被判违规。生成端改了、检查端没跟上时，两边就是这样自相矛盾的，
    而症状是「照文档做却过不了闸门」，最难排查。

    注意口径的第二次变化：旧口径下这条是「fixed 尺寸不该被禁，因为尺寸是常量」；
    闭合契约下 fixed 不再是默认值，所以这条的正当性不再来自「它一定是设计常量」，
    而是来自**分工**：尺寸轴该不该用 fixed，由 ``check_relations`` 的 ``why`` 与
    下面的 ``sourceKindViolation`` 判据负责；禁止清单只管位置/尺寸里确实成比例的那些。

    顺带要求每条禁止项给出 ``ratioInstead``（应当改用的比例）：只说「这个数不行」
    而不说「该用什么」，等于把问题原样丢回给实现者。
    """
    problems = []
    regions = plan.get("regions") or []
    kind_by_id = {rel.get("id"): rel.get("kind")
                  for region in regions for rel in (region.get("relations") or [])}
    known_regions = {region.get("region") for region in regions}

    for item in plan.get("forbiddenLiterals") or []:
        target = item.get("relation") or ""
        region_name, _, anchor = target.rpartition(".")
        axis = ANCHOR_AXIS.get(anchor)
        if axis is None:
            problems.append({
                "kind": "forbidden-unknown-anchor",
                "relation": target,
                "detail": f"锚点 {anchor!r} 不认识：禁止项只能指向 "
                          f"{'/'.join(sorted(ANCHOR_AXIS))} 之一，"
                          "否则无法与计划里的关系对上",
            })
        elif region_name in known_regions:
            kind = kind_by_id.get(f"{region_name}.{axis}")
            if kind is not None and kind != "proportional":
                problems.append({
                    "kind": "forbidden-targets-non-proportional",
                    "relation": target,
                    "detail": f"禁止清单指向了一条 kind={kind} 的关系："
                              f"{kind} 的值是**设计稿给的字面量**（fixed）或"
                              "贴边闭合的内边距（pinned），本来就该原样写进代码。"
                              "把它列为禁止，等于要求实现者不要按设计稿做",
                })
        if item.get("ratioInstead") is None:
            problems.append({
                "kind": "forbidden-missing-ratio",
                "relation": target,
                "detail": "禁止项必须给 ratioInstead（应当改用的比例）："
                          "只说「这个数不行」而不说「该用什么」，问题原样退回给实现者",
            })
    return problems


def check_design_constants(plan) -> list:
    """``designConstants`` 是可复核的豁免，不是随手写个数字就放行。

    它必须是数字数组，并且每条豁免都应能被审阅者看懂「这是什么设计常量」；
    因此只接受数字，字符串/对象一律报错，避免有人把整段源码粘进来当豁免。
    """
    problems = []
    declared = plan.get("designConstants")
    if declared is None:
        return problems
    if not isinstance(declared, list):
        return [{"kind": "bad-design-constants",
                 "detail": f"designConstants 必须是数字数组，收到 {type(declared).__name__}"}]
    for value in declared:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            problems.append({
                "kind": "bad-design-constants",
                "detail": f"designConstants 只能放数字，收到 {value!r}；"
                          "设计常量是标准边距/圆角这类值，不是说明文字"})
    return problems


def check_type_facts(plan, page_facts) -> list:
    """样式恒量（字号/字体/颜色/描边/圆角）必须带 page-facts 元素溯源。

    这是「权威来自 DOM」的可执行版本。以前的漏洞是：布局门只盯几何关系（kind/of/basis），
    字号颜色这些值落在 Agent 写码的字面量上，没有任何门核对「它是不是从渲染 DOM 抄来的」。
    于是偷懒的形态是「编一个 fontSize=14 让四个门全绿」。``typeFacts`` 强制每条样式恒量
    声明它来自 ``page-facts.json`` 的哪个元素，门 0 在这里核它。

    分两层：

    1. **结构核**（不读 page-facts 也能做）：``typeFacts`` 是否存在、每条是否带整数
       ``elementIndex``、``kindSource`` 是否就是 ``"page-facts"``。
    2. **引用核**（给了 ``--page-facts`` 才做）：``elementIndex`` 是否落在元素下标范围内，
       以及该元素是否具备这条记录所声明的样式类型（文本记录要落在 ``ownsText`` 元素上、
       描边记录要落在 ``border.widthPx > 0`` 的元素上）。

    只对「应当有样式事实」的区域提要求：本函数无法知道哪条区域是文字/描边区域，所以
    结构核只罚「写了 typeFacts 但形状非法」，不罚「整页一条 typeFacts 都没有」——那一条
    由调用方（计划必需性检查）用 region 里的文本标记来决定是否需要警告。
    """
    problems = []
    facts = plan.get("typeFacts")
    if facts is None:
        # 计划里压根没有 typeFacts：这是「没做样式溯源」。
        # 是否算违规取决于计划里有没有文字/描边区域，调用方根据 region 里的
        # nativeIdiom/关系类型来判；这里先记一条可降级的告警（kind 前缀 fact-*）。
        return problems  # 缺失由上层 decide_typefacts_required 判，这里只查「有但非法」
    if not isinstance(facts, list):
        return [{"kind": "bad-type-facts",
                 "detail": f"typeFacts 必须是数组，收到 {type(facts).__name__}"}]
    element_indexes = None
    elements = None
    if page_facts is not None:
        elements = page_facts.get("elements") or []
        element_indexes = {e.get("index") for e in elements if isinstance(e, dict)}
    for item in facts:
        if not isinstance(item, dict):
            problems.append({"kind": "bad-type-facts",
                             "detail": f"typeFacts 条目必须是对象，收到 {type(item).__name__}"})
            continue
        region = item.get("region")
        if not (isinstance(region, str) and region.strip()):
            problems.append({"kind": "fact-missing-region",
                             "detail": f"typeFacts 条目缺 region：{item!r}"})
        kind_source = item.get("kindSource")
        if kind_source not in ("page-facts", "html-css"):
            problems.append({
                "kind": "fact-not-from-authority",
                "detail": f"region={region!r} 的 kindSource 必须是 \"html-css\"（样式来自官方 "
                          f"HTML/CSS）或 \"page-facts\"（样式来自渲染 DOM 实测），收到 {kind_source!r}；"
                          "写成别的一律视为「没有从权威来源抄值」，等于承认是拍脑袋编的"})
        idx = item.get("elementIndex")
        # elementIndex 只在 page-facts 溯源时强制（html-css 溯源用 styleSourceIndex）。
        if kind_source == "page-facts" and (isinstance(idx, bool) or not isinstance(idx, int)):
            problems.append({
                "kind": "fact-missing-element-index",
                "detail": f"region={region!r} 的 elementIndex 必须是整数（指向 page-facts "
                          f"elements[] 的下标），收到 {idx!r}；没有它就没法证明这个值来自渲染 DOM"})
        # 引用核：只在给了 page-facts 且 kindSource 是 page-facts 时做
        if element_indexes is not None and kind_source == "page-facts" and isinstance(idx, int):
            if idx not in element_indexes:
                problems.append({
                    "kind": "fact-element-index-out-of-range",
                    "detail": f"region={region!r} 的 elementIndex={idx} 不在 page-facts.elements"
                              f" 的下标范围内（0..{max(element_indexes) if element_indexes else -1}）："
                              "引用了一个不存在的元素，溯源无效"})
            else:
                el = next((e for e in (elements or [])
                           if isinstance(e, dict) and e.get("index") == idx), None)
                if el is not None:
                    has_text = bool(el.get("ownsText"))
                    border_px = (el.get("border") or {}).get("widthPx", 0)
                    declares_text = isinstance(item.get("fontSize"), (int, float))
                    declares_border = isinstance(item.get("borderWidth"), (int, float)) and item.get("borderWidth", 0) > 0
                    if declares_text and not has_text:
                        problems.append({
                            "kind": "fact-text-on-non-text-element",
                            "detail": f"region={region!r} 声明了 fontSize，但 elementIndex={idx} "
                                      "对应元素没有 ownText（不是文本元素）；「用空容器顶文本」"
                                      "说明溯源是拼凑的，不是真读到文字样式"})
                    if declares_border and not border_px:
                        problems.append({
                            "kind": "fact-border-on-unbordered-element",
                            "detail": f"region={region!r} 声明了 borderWidth>0，但 elementIndex={idx} "
                                      "对应元素 border.widthPx=0；描边值声明与 DOM 事实不符"})
    return problems


def _region_tokens(region_name: str) -> list:
    """把 region 名派生成可能出现在源码里的标识符片段。

    计划里的 region 是 ``offers`` / ``cta`` / ``hero`` 这种语义名，源码里可能是
    ``_offers`` / ``offersView`` / ``offersContainer`` / ``offers_card``。这里只做
    **保守**的派生：原始名、snake_case、以及连字符/空格替换 —— 宁可少认几个，
    也不要把无关行误认成该区域的实现（误报比漏报更伤这条红线）。
    """
    name = (region_name or "").strip()
    if not name:
        return []
    tokens = {name}
    # camelCase / PascalCase -> snake_case
    tokens.add(re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower())
    tokens.add(re.sub(r"[\s\-]+", "_", name))
    return sorted(t for t in tokens if t)


def _line_mentions_region(text: str, tokens) -> str:
    """这一行是否提到了该区域。返回命中的 token（没命中返回空串）。"""
    for token in tokens:
        if re.search(rf"(?<![A-Za-z0-9])_?{re.escape(token)}(?![A-Za-z0-9])",
                     text, re.IGNORECASE):
            return token
    return ""


def size_constant_hits(text: str, axis: str) -> list:
    """这一行在该轴上是否出现了**等值常量**（``==``）尺寸约束。

    只认 ``==``：``>=`` / ``<=`` 是 ``bounded`` 的正确写法，绝不能一起报。
    """
    return [name for pattern, name in SIZE_CONSTANT_RES.get(axis, ())
            if pattern.search(text)]


def check_source_kinds(relations, files, lines_by_file) -> tuple:
    """**源码侧**逐类核对闭合契约是否照计划实现。

    这是门 1 在闭合契约下的核心补丁。在此之前，源码侧只认三类原语
    （``proportional`` / ``pinned`` / ``fixed`` 的禁止字面量），
    ``intrinsic`` / ``bounded`` / ``equal`` / ``aspect-ratio`` 声明在源码里**没有任何判据** ——
    计划写了 ``intrinsic``、代码却写 ``widthAnchor constraintEqualToConstant`` 不会被拦。
    于是「把设计稿的 width/height 逐字写成固定约束」这个新契约要拦的头号问题，
    变成了一个只有计划层说、没有实现层查的口头约定。

    判据分两档（与全文一致：闸门要准，不是要响）：

    **违规** —— 计划与源码**直接矛盾**，且可静态判定：

    * ``intrinsic-axis-pinned-to-constant``：计划把 ``{region}.{axis}`` 声明为
      ``intrinsic``，源码里该区域的该轴出现了 ``==`` 常量约束。这是旧契约的直接残留。
    * ``bounded-axis-missing-limit``：声明了 ``bounded``，但整份源码里**一个边界原语都没有**。
    * ``aspect-ratio-idiom-missing``：声明了 ``aspect-ratio``，源码里没有任何比例约束原语。

    **告警** —— 可能是别的写法，也可能是真的漏了：

    * ``equal-idiom-missing``：声明了 ``equal``，但没找到等值/等分原语
      （等宽等高有多种表达方式，清单不可能穷尽，所以只告警）。
    * ``content-adaptivity-idioms-missing``：声明了 ``intrinsic`` / ``bounded``
      （说明页面有内容驱动的尺寸），却没找到 Dynamic Type 或优先级原语。
    * ``relation-not-locatable``：计划里的区域名在源码里一个都没出现，
      意味着这些声明无法与实现对应上（可能是命名不一致，也可能压根没按计划写）。
    """
    violations, warnings = [], []
    if not relations or not files:
        return violations, warnings

    # 注释先去掉：注释里写「// heightAnchor constraintEqualToConstant」是在解释，不是违规。
    code_by_file = {path: strip_comments(lines) for path, lines in lines_by_file.items()}

    by_axis = {}
    for rel in relations:
        by_axis.setdefault(rel.get("kind"), []).append(rel)

    # ---- 1. intrinsic / bounded 的区域轴被写成了 == 常量（最硬的漏洞） ----
    checkable = [r for r in relations
                 if r.get("kind") in ("intrinsic", "bounded") and r.get("axis")]
    unlocatable = []
    for rel in checkable:
        region = rel.get("id", "").rsplit(".", 1)[0]
        axis = rel.get("axis")
        tokens = _region_tokens(region)
        if not tokens:
            continue
        located = False
        for path in files:
            for number, text in enumerate(code_by_file.get(path, []), start=1):
                if not _line_mentions_region(text, tokens):
                    continue
                located = True
                hits = size_constant_hits(text, axis)
                if hits:
                    violations.append({
                        "kind": "intrinsic-axis-pinned-to-constant",
                        "relation": rel.get("id"),
                        "declaredKind": rel.get("kind"),
                        "axis": axis,
                        "file": str(path),
                        "line": number,
                        "detail": f"计划把 {rel.get('id')} 声明为 {rel.get('kind')}"
                                  f"（{'内容撑开' if rel.get('kind') == 'intrinsic' else '边界约束'}），"
                                  f"源码里该区域的 {axis} 轴却是**等值常量**约束（{hits[0]}）。"
                                  f"设计稿给的宽高只是参考事实：文本/按钮/容器应当由内容或边界闭合，"
                                  f"写成 == 常量会在窄屏、动态字体、长本地化文本下失守。"
                                  f"要么改成 {'不给该轴约束（intrinsic）' if rel.get('kind') == 'intrinsic' else '>= / <= 边界'}，"
                                  f"要么把计划改成 fixed 并给出 why。",
                        "text": text.strip()[:120],
                    })
        if not located:
            unlocatable.append(rel.get("id"))

    # ---- 2. bounded 必须在同一区域实现，不能用别处一条 >= 伪装 ----
    all_text = [line for path in files for line in code_by_file.get(path, [])]
    for rel in by_axis.get("bounded", []):
        region = rel.get("id", "").rsplit(".", 1)[0]
        axis = rel.get("axis")
        tokens = _region_tokens(region)
        matched = False
        for path in files:
            for number, text in enumerate(code_by_file.get(path, []), start=1):
                if tokens and _line_mentions_region(text, tokens) and BOUNDED_RE.search(text):
                    matched = True
                    break
            if matched:
                break
        if not matched:
            violations.append({
                "kind": "bounded-axis-missing-limit",
                "relation": rel.get("id", "?"),
                "axis": axis,
                "detail": f"计划声明了 {rel.get('id')} 为 bounded，但对应区域源码没有找到 >= / <= 或 min/max 原语；"
                          "不能用其他区域的边界约束代替本关系。",
            })

    # ---- 3. aspect-ratio 必须在同一区域实现，不能用别处一条比例伪装 ----
    for rel in by_axis.get("aspect-ratio", []):
        region = rel.get("id", "").rsplit(".", 1)[0]
        tokens = _region_tokens(region)
        matched = any(tokens and _line_mentions_region(text, tokens) and ASPECT_RE.search(text)
                      for path in files for text in code_by_file.get(path, []))
        if not matched:
            violations.append({
                "kind": "aspect-ratio-idiom-missing",
                "relation": rel.get("id", "?"),
                "detail": f"计划声明了 {rel.get('id')} 为 aspect-ratio，但对应区域源码没有找到比例约束原语；"
                          "不能用其他区域的比例约束代替本关系。",
            })

    # ---- 4. equal：只告警 ----
    if by_axis.get("equal") and not any(EQUAL_RE.search(l) for l in all_text):
        warnings.append(
            f"计划声明了 {len(by_axis['equal'])} 条 equal（兄弟等宽/等高/等基线），"
            f"但 {len(files)} 个源码文件里没找到等值锚点或等分原语。若确实是用 "
            "UIStackView 的 fillEqually、HStack + maxWidth: .infinity、IntrinsicSize "
            "这类方式表达的，忽略本条；否则这些关系很可能没有落实。")

    # ---- 5. 内容自适应支撑原语：只告警 ----
    content_driven = len(by_axis.get("intrinsic", [])) + len(by_axis.get("bounded", []))
    if content_driven:
        missing = [name for pattern, name in CONTENT_ADAPTIVITY_IDIOMS
                   if not any(re.search(pattern, l) for l in all_text)]
        if len(missing) == len(CONTENT_ADAPTIVITY_IDIOMS):
            warnings.append(
                f"计划声明了 {content_driven} 条 intrinsic/bounded（说明页面有内容驱动的尺寸），"
                f"但 {len(files)} 个源码文件里既没有 Dynamic Type 字号缩放，"
                "也没有 content hugging / compression resistance 优先级。"
                "内容驱动的布局必须同时声明「谁扩张、谁被压缩」，否则宽度不足时的截断行为是随机的。"
                "若本页确实没有文字（纯图形页），忽略本条。")

    # ---- 6. 区域名在源码里找不到 ----
    if unlocatable and len(unlocatable) == len(checkable):
        warnings.append(
            f"计划里 {len(checkable)} 条 intrinsic/bounded 关系的区域名在源码里一个都没出现，"
            "无法与实现对应上：请确认源码里的命名与计划的 region 名一致，"
            "否则「计划声明了什么」与「代码实现了什么」之间没有可核对的联系。")

    return violations, warnings


def decide_typefacts_required(regions, plan, page_facts) -> list:
    """给了 page-facts 时，计划里存在文本/描边区域却一条 typeFacts 都没有，判违规。

    这里只负责「漏整块」的必填性，且**只在权威数据已就绪（page-facts 已传）时判**。
    判据不靠区域名猜（那会误伤无文字的老计划），而是看**真实的文本元素**：page-facts
    里有多少元素 ``ownsText`` 或 ``border.widthPx > 0``。这些元素是「样式恒量该有溯源」
    的客观存在 —— 计划没给 typeFacts，等于权威数据明明在、却一条都不引用，这就是偷懒。

    没有 page-facts 时调用方不调用本函数（必填性无从可靠判断）。
    """
    facts = plan.get("typeFacts")
    if isinstance(facts, list) and len(facts) > 0:
        return []
    elements = (page_facts or {}).get("elements") or []
    texty = sum(1 for e in elements if isinstance(e, dict) and e.get("ownsText"))
    bordered = sum(1 for e in elements
                   if isinstance(e, dict) and (e.get("border") or {}).get("widthPx", 0) > 0)
    total = texty + bordered
    if total == 0:
        return []  # 页面上本就没有文本/描边元素，谈不上样式溯源
    return [{
        "kind": "fact-source-missing",
        "detail": f"page-facts 里有 {texty} 个文本元素、{bordered} 个描边元素，但计划 typeFacts "
                  "缺失或为空：样式恒量（字号/字体/颜色/描边）必须带 page-facts 元素溯源，"
                  "否则「权威来自 DOM」没有可执行抓手，Agent 编个 fontSize 也能过门。"
                  "权威数据已就绪却不引用，正是「跳过 DOM 解析」的形态。"
                  "详见 artifact-contract.md 的 typeFacts 一节。"
    }]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, help="含 layoutProportions 的实现计划")
    ap.add_argument("--page-facts", help="页面级 page-facts.json，用于核对 typeFacts 的 elementIndex 引用")
    ap.add_argument("--source", action="append",
                    help="原生源码文件或目录，可重复；--plan-only 时不需要")
    ap.add_argument("--plan-only", action="store_true",
                    help="只校验计划本身（结构、kind、why、designConstants），不扫源码。"
                         "run 校验器用它来复用同一套计划质量判定，避免两处各写一份")
    ap.add_argument("--target-mode", help="目标模式，仅用于报告")
    ap.add_argument("--literal-tolerance", type=float, default=DEFAULT_LITERAL_TOLERANCE,
                    help=f"字面量与该关系设备推导值的比对容差（默认 {DEFAULT_LITERAL_TOLERANCE}pt）")
    ap.add_argument("--allow-values", default="",
                    help="额外的设计常量豁免，逗号分隔（标准边距/圆角这类）。"
                         "与计划的 designConstants 取并集，并原样记入结果供复核")
    ap.add_argument("--output", help="把结果写入该 JSON 路径")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    plan_payload = load_json(args.plan)
    if plan_payload is None:
        return 2
    plan = plan_payload.get("layoutProportions", plan_payload)
    if not isinstance(plan, dict):
        print(f"计划结构不是对象：{args.plan}", file=sys.stderr)
        return 2

    violations, warnings = [], []
    if not plan.get("regions"):
        violations.append({
            "kind": "missing-layout-proportions",
            "detail": "实现计划里没有 layoutProportions.regions：组件之间的布局关系必须"
                      "逐条声明（每个尺寸声明闭合方式、位置相对父视图），否则无从核对。"
                      "用 scripts/layout_proportions.py 生成。",
        })

    relations = [rel for region in (plan.get("regions") or [])
                 for rel in (region.get("relations") or [])]
    violations.extend(check_relations(relations))
    violations.extend(check_bases(plan.get("regions") or []))
    violations.extend(check_forbidden_targets(plan))
    violations.extend(check_design_constants(plan))

    # 样式恒量（typeFacts）溯源：与 page-facts 交叉核对「权威来自 DOM」有没有可执行抓手。
    # typeFacts 在顶层 plan（plan_payload），不在内层 layoutProportions（plan）。
    page_facts = None
    if args.page_facts:
        page_facts = load_json(args.page_facts)
        if page_facts is None:
            print(f"--page-facts 读取失败，跳过 typeFacts 引用核（只做结构核）：{args.page_facts}",
                  file=sys.stderr)
    top = plan_payload if isinstance(plan_payload, dict) else {}
    violations.extend(check_type_facts(top, page_facts))
    # 必填性只判「给了 page-facts」的场景：那时权威数据已就绪、不引用=偷懒。
    # 没给 page-facts 时无法可靠判断哪些区域该有 typeFacts，判必填会误伤无文字的老计划。
    if page_facts is not None:
        violations.extend(decide_typefacts_required(plan.get("regions") or [], top, page_facts))

    allow_values = []
    for token in (args.allow_values or "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            allow_values.append(float(token))
        except ValueError:
            print(f"--allow-values 里的 {token!r} 不是数字", file=sys.stderr)
            return 2
    declared = plan.get("designConstants") or []
    allow_values.extend(v for v in declared if isinstance(v, (int, float))
                        and not isinstance(v, bool))
    allow_values = sorted(set(allow_values))

    forbidden = plan.get("forbiddenLiterals") or []
    if not forbidden:
        warnings.append("计划没有 forbiddenLiterals：本次无法核对「设备推导值被写成字面量」，"
                        "核对的只是有没有比例原语。用 scripts/layout_proportions.py 生成这一项。")
    ignorable = [f for f in forbidden
                 if isinstance(f.get("deviceDerivedPt"), (int, float))
                 and abs(f["deviceDerivedPt"]) < MIN_MEANINGFUL_PT]
    if ignorable:
        warnings.append(f"计划里有 {len(ignorable)} 条设备推导值接近原点（<{MIN_MEANINGFUL_PT}pt），"
                        "已不作为证据：这些值在任何设备上都成立")

    if not args.plan_only and not args.source:
        print("需要 --source（或 --plan-only）", file=sys.stderr)
        return 2
    files, missing = ([], []) if args.plan_only else collect_sources(args.source)
    for path in missing:
        warnings.append(f"源码路径不存在：{path}")
    if not args.plan_only and not files:
        print("没有找到可扫描的原生源码（--source 指向的文件/目录为空）", file=sys.stderr)
        return 2

    all_idioms, pinned_idioms, ambiguous = [], [], []
    lines_by_file = {}
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as error:
            warnings.append(f"读取源码失败 {path}：{error}")
            continue
        lines_by_file[path] = lines
        for hit in idiom_hits(lines):
            all_idioms.append({**hit, "file": str(path)})
        for hit in idiom_hits(lines, PINNED_IDIOMS, PINNED_RE):
            pinned_idioms.append({**hit, "file": str(path)})
        found, unclear = literal_hits(lines, forbidden, args.literal_tolerance, allow_values)
        for hit in found:
            violations.append({**hit, "file": str(path)})
        for hit in unclear:
            ambiguous.append({**hit, "file": str(path)})

    # 闭合契约在**源码侧**的逐类核对：intrinsic / bounded / equal / aspect-ratio。
    # 声明在计划里、实现却没跟上，是旧契约残留的主要形态，必须能在门 1 拦下。
    kind_violations, kind_warnings = check_source_kinds(relations, files, lines_by_file)
    violations.extend(kind_violations)
    warnings.extend(kind_warnings)

    proportional = [r for r in relations if r.get("kind") == "proportional"]
    pinned = [r for r in relations if r.get("kind") == "pinned"]
    fixed = [r for r in relations if r.get("kind") == "fixed"]
    centered = [r for r in relations if r.get("kind") == "centered"]
    kind_counts = {kind: len([r for r in relations if r.get("kind") == kind])
                   for kind in RELATION_KINDS}
    bounded = [r for r in relations if r.get("kind") == "bounded"]
    equal = [r for r in relations if r.get("kind") == "equal"]
    aspect = [r for r in relations if r.get("kind") == "aspect-ratio"]
    # plan-only 模式没有源码，谈不上「一个比例原语都没有」，不能报这一条。
    if not args.plan_only and proportional and not all_idioms:
        violations.append({
            "kind": "no-proportional-idiom",
            "detail": f"计划声明了 {len(proportional)} 条 proportional 关系，但 "
                      f"{len(files)} 个源码文件里一个比例原语都没有：整页很可能是拿"
                      "绝对值堆出来的。",
        })
    # 声明了 pinned 却一处贴边/铺满原语都没有，是**告警不是违规**：
    # 手写约束、辅助函数封装都能正确地表达贴边，行级扫描看不出来。
    # 但这条值得提示 —— 它最常见的成因是「整页都用绝对 frame 摆好了位置」。
    if not args.plan_only and pinned and not pinned_idioms:
        warnings.append(
            f"计划声明了 {len(pinned)} 条 pinned（贴边）关系，但 {len(files)} 个源码文件里"
            "没有出现铺满/约束闭合/边对边这类原语。如果确实是用绝对 frame 摆的位置，"
            "它在别的屏幕尺寸上会失守；如果真的用了约束（例如自己封装的辅助方法），"
            "忽略这条告警即可。")

    violations.sort(key=lambda v: (v.get("file") or "", v.get("line") or 0))
    ambiguous.sort(key=lambda v: (v.get("file") or "", v.get("line") or 0))
    literal_total = len([v for v in violations if v["kind"] == "forbidden-literal-used"])
    distinct_values = sorted({v["literal"] for v in violations
                              if v["kind"] == "forbidden-literal-used"})
    result = {
        "tool": "check_layout_proportions.py",
        # 4 = 闭合契约口径。三个版本的含义各不相同，读者必须能区分：
        # v2（一轴）：非文字元素一律 proportional，一处比例原语都没有就判整页有问题；
        # v3（两轴）：proportional 只占五类之一，贴边与固定值都是**正确写法**；
        # v4（闭合契约）：fixed 降级为特例，尺寸必须声明闭合方式，且源码侧开始逐类核对
        #     intrinsic / bounded / equal / aspect-ratio —— v3 的 violations 只覆盖了
        #     计划层是否有声明，v4 还会覆盖「声明了但没实现」。
        "schemaVersion": 4,
        "status": "fail" if violations else "pass",
        "planOnly": bool(args.plan_only),
        "targetMode": args.target_mode,
        "plan": str(args.plan),
        "sourceFiles": [str(p) for p in files],
        "regionCount": len(plan.get("regions") or []),
        "relationCount": len(relations),
        "relationKindCounts": kind_counts,
        "proportionalRelationCount": len(proportional),
        "pinnedRelationCount": len(pinned),
        "fixedRelationCount": len(fixed),
        "centeredRelationCount": len(centered),
        "intrinsicRelationCount": kind_counts.get("intrinsic", 0),
        "boundedRelationCount": len(bounded),
        "equalRelationCount": len(equal),
        "aspectRatioRelationCount": len(aspect),
        "boundedIdiomCount": len([1 for l in
                                  (line for path in files for line in lines_by_file.get(path, []))
                                  if BOUNDED_RE.search(l)]),
        "sourceKindViolationCount": len(kind_violations),
        "sourceKindWarnings": kind_warnings,
        "proportionalIdiomCount": len(all_idioms),
        "proportionalIdioms": all_idioms[:40],
        "pinnedIdiomCount": len(pinned_idioms),
        "pinnedIdioms": pinned_idioms[:20],
        "forbiddenLiteralCount": len(forbidden),
        "ignoredForbiddenCount": len(ignorable),
        "allowValues": allow_values,
        "designScaleMaxPt": DESIGN_SCALE_MAX_PT,
        "literalViolationCount": literal_total,
        "ambiguousLiteralCount": len(ambiguous),
        "ambiguousLiterals": ambiguous[:40],
        "distinctLiteralValues": distinct_values[:40],
        "violations": violations,
        "warnings": warnings,
        "scopeNote": ("只校验了计划本身，未扫源码。" if args.plan_only else
                      "本脚本做行级扫描，不解析语法树；结论是「找到了这些证据/违规」，"
                      "不等于「布局是正确的」——那由截图与对齐审计回答。"
                      f"另外，≤{DESIGN_SCALE_MAX_PT:g}pt 的数值与设计常量无法区分，"
                      "只列在 ambiguousLiterals 里待人工判断，不计入违规。"
                      "禁止清单只应指向 proportional 的关系：pinned 的内边距本就是设计常量，"
                      "fixed 候选的字面量在复核完成前也不该自动进清单（复核后若改判 "
                      "intrinsic/bounded，则改由 sourceKind 那条判据把关）。"
                      "sourceKindViolationCount 是「计划声明了 intrinsic/bounded/equal/"
                      "aspect-ratio，源码却没照做」的计数（见 ios-autolayout-practice.md）。"),
    }

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                     encoding="utf-8")

    if not args.quiet:
        dist = "  ".join(f"{kind}={count}" for kind, count in kind_counts.items())
        print(f"计划声明的关系 {len(relations)} 条（{dist}），"
              f"源码里的比例原语 {len(all_idioms)} 处、贴边原语 {len(pinned_idioms)} 处，"
              f"扫了 {len(files)} 个文件")
        if allow_values:
            print(f"已声明的设计常量豁免：{', '.join(f'{v:g}' for v in allow_values)}")
        if violations:
            print(f"\n违规 {len(violations)} 项"
                  + (f"（其中字面量命中 {literal_total} 处，涉及 {len(distinct_values)} 个值）"
                     if literal_total else "") + "：")
            # 按文件聚合：真实工程上一次能出几百条，逐条平铺等于没有报告。
            for item in violations:
                if item["kind"] != "forbidden-literal-used":
                    print(f"  [-] {item['kind']}: {item['detail']}")
            by_file = {}
            for item in violations:
                if item["kind"] == "forbidden-literal-used":
                    by_file.setdefault(item["file"], []).append(item)
            for path in sorted(by_file):
                hits = by_file[path]
                print(f"\n  {Path(path).name}  {len(hits)} 处")
                for item in hits[:MAX_REPORT_PER_FILE]:
                    more = (f"（另有 {item['candidateCount'] - 1} 条同值关系："
                            f"{', '.join(item['alsoMatches']) or '-'}）"
                            if item.get("candidateCount", 1) > 1 else "")
                    print(f"    :{item['line']}  {item['literal']:g} == "
                          f"{item['deviceDerivedPt']:g}pt（{item['relation']}）"
                          f" -> 应用比例 {item['expectedRatio']}{more}")
                    print(f"          {item['text']}")
                if len(hits) > MAX_REPORT_PER_FILE:
                    print(f"    ...该文件另有 {len(hits) - MAX_REPORT_PER_FILE} 处，"
                          f"完整清单见 --output 的 JSON")
        if ambiguous:
            print(f"\n待判 {len(ambiguous)} 处（数值 ≤{DESIGN_SCALE_MAX_PT:g}pt，"
                  "与设计常量无法自动区分；不计入违规，请人工确认）：")
            by_file = {}
            for item in ambiguous:
                by_file.setdefault(item["file"], []).append(item)
            for path in sorted(by_file):
                hits = by_file[path]
                sample = ", ".join(f"{i['literal']:g}" for i in hits[:8])
                print(f"  {Path(path).name}  {len(hits)} 处：{sample}")
        for line in warnings:
            print(f"\n[warn] {line}")
        if not violations:
            print("布局约束校验通过（尺寸按闭合方式声明、位置相对父视图）"
                  + (f"（另有 {len(ambiguous)} 处待判，见上）" if ambiguous else ""))

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
