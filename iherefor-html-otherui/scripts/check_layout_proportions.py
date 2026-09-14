#!/usr/bin/env python3
"""核对原生源码是否按 ``layoutProportions`` 声明用比例表达布局关系。

**这是计划驱动，不是正则扫描。** 只有被声明为 ``proportional`` 的关系才要求比例表达；
``intrinsic`` 的关系不要求。纯正则扫描会把合法的设计常量（圆角 12、标准边距 16）一起
误报，训练出「看到告警就忽略」的习惯，那样这条红线就废了。

两类违规，各自对应一种真实的错法：

1. ``forbidden-literal-used`` —— 源码里出现了 ``forbiddenLiterals`` 记录的
   「探针设备推导值」。这是最典型的一种：把 ``lanhuY * 1.0229 = 135.02`` 算出来，
   然后原样敲进约束。数字看起来有出处、算过，review 时最容易被放过。
2. ``no-proportional-idiom`` —— 计划声明了比例，但源码里一个比例原语都没有。
   说明整页都是拿绝对值堆出来的。

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

本脚本做的是**行级**扫描，不做语法解析：它认的是各平台的比例原语与数字字面量。
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

# 各平台表达「相对/比例」的原语。命中任意一个即认为该处用了比例。
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
    (r"match_parent|fill_parent", "父容器铺满"),
)
PROPORTIONAL_RE = re.compile("|".join(f"(?:{p})" for p, _ in PROPORTIONAL_IDIOMS))

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


def idiom_hits(lines) -> list:
    hits = []
    for number, text in enumerate(lines, start=1):
        match = PROPORTIONAL_RE.search(text)
        if match:
            label = next((name for pattern, name in PROPORTIONAL_IDIOMS
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


def check_relations(relations) -> list:
    """计划本身的质量：声明为 intrinsic 的必须给出 why。"""
    problems = []
    for rel in relations or []:
        if rel.get("kind") == "intrinsic" and not (rel.get("why") or "").strip():
            problems.append({
                "kind": "intrinsic-missing-why",
                "relation": rel.get("id"),
                "detail": "声明为 intrinsic 的关系必须写明 why：为什么这个量不随容器缩放",
            })
        if rel.get("kind") not in ("proportional", "intrinsic"):
            problems.append({
                "kind": "unknown-relation-kind",
                "relation": rel.get("id"),
                "detail": f'kind={rel.get("kind")!r}，只能是 "proportional" 或 "intrinsic"',
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, help="含 layoutProportions 的实现计划")
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
                      "用比例表达，并逐条声明。用 scripts/layout_proportions.py 生成。",
        })

    relations = [rel for region in (plan.get("regions") or [])
                 for rel in (region.get("relations") or [])]
    violations.extend(check_relations(relations))
    violations.extend(check_design_constants(plan))

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

    all_idioms, ambiguous = [], []
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as error:
            warnings.append(f"读取源码失败 {path}：{error}")
            continue
        for hit in idiom_hits(lines):
            all_idioms.append({**hit, "file": str(path)})
        found, unclear = literal_hits(lines, forbidden, args.literal_tolerance, allow_values)
        for hit in found:
            violations.append({**hit, "file": str(path)})
        for hit in unclear:
            ambiguous.append({**hit, "file": str(path)})

    proportional = [r for r in relations if r.get("kind") == "proportional"]
    # plan-only 模式没有源码，谈不上「一个比例原语都没有」，不能报这一条。
    if not args.plan_only and proportional and not all_idioms:
        violations.append({
            "kind": "no-proportional-idiom",
            "detail": f"计划声明了 {len(proportional)} 条 proportional 关系，但 "
                      f"{len(files)} 个源码文件里一个比例原语都没有：整页很可能是拿"
                      "绝对值堆出来的。",
        })

    violations.sort(key=lambda v: (v.get("file") or "", v.get("line") or 0))
    ambiguous.sort(key=lambda v: (v.get("file") or "", v.get("line") or 0))
    literal_total = len([v for v in violations if v["kind"] == "forbidden-literal-used"])
    distinct_values = sorted({v["literal"] for v in violations
                              if v["kind"] == "forbidden-literal-used"})
    result = {
        "tool": "check_layout_proportions.py",
        "schemaVersion": 1,
        "status": "fail" if violations else "pass",
        "planOnly": bool(args.plan_only),
        "targetMode": args.target_mode,
        "plan": str(args.plan),
        "sourceFiles": [str(p) for p in files],
        "regionCount": len(plan.get("regions") or []),
        "relationCount": len(relations),
        "proportionalRelationCount": len(proportional),
        "intrinsicRelationCount": len([r for r in relations if r.get("kind") == "intrinsic"]),
        "proportionalIdiomCount": len(all_idioms),
        "proportionalIdioms": all_idioms[:40],
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
                      "只列在 ambiguousLiterals 里待人工判断，不计入违规。"),
    }

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                     encoding="utf-8")

    if not args.quiet:
        print(f"计划声明的比例关系 {len(proportional)} 条，"
              f"源码里的比例原语 {len(all_idioms)} 处，扫了 {len(files)} 个文件")
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
            print("比例校验通过"
                  + (f"（另有 {len(ambiguous)} 处待判，见上）" if ambiguous else ""))

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
