#!/usr/bin/env python3
"""变异探针：证明回归测试的断言不是空的。

**为什么需要它。** 「测试通过」只说明脚本跑得动，不说明断言真的在断言。这一轮里
连着三次踩到同一类坑：

* 判分器里「有 hint 才检查」的分支，在推不出 hint 时静默短路 —— 判分器自己成了恒真式；
* 新增的比例校验器有 2 条断言从未被任何输入触发过（校验器自身的近零过滤、
  以及 `ratios` 是否同时给出边缘与中心两套），测试全绿但它们等于没写；
* 连探针本身也会骗人：`sed` 的锚点没匹配上、或 `bash` 相对路径解析不到 ——
  改动根本没落到源码里，而被读成「断言有效」；
* 还有一次是「红了，但红得不对」：探针删掉守卫后被测函数在空对象上取下标直接 KeyError
  掉栈，退出码非 0 被读成「断言有效」—— 其实要守的那条断言一次都没执行。所以崩栈单独判
  无效，并要求探针复刻**历史上真实的那段实现**，而不是删几行代码凑一个红；
* 第五种最隐蔽：**探针崩在中途**。`audit_fonts.py` 被裁撤后，指向它的探针仍留在列表里，
  读文件时 FileNotFoundError 掉栈 —— 排在它后面的探针（fixture 可移植性、文档锚点）
  从此一条都没跑过，而 README 里还写着「这两条就是这样验过的」。所以现在**目标不存在
  单列为一类「探针无效」**，会继续往下跑，而不是让崩点静默截断整个列表。

所以本脚本做两件必须一起做的事：

1. **先证明探针有效**：改动后要断言源码里确实出现了新内容（否则报「探针无效」，
   而不是「断言有效」）；
2. **再证明断言有效**：跑测试，要求它**变红**，且红必须来自断言（崩栈不算）。
   全绿就是空断言。

用法（**手动跑，不进 `run_all.sh`** —— 它会临时改写被测源码）：

    python3 scripts/tests/mutation_probe.py

退出码：0 = 所有探针都让测试变红；1 = 存在空断言或无效探针。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "scripts" / "check_layout_proportions.py"
PLAN = ROOT / "scripts" / "layout_proportions.py"
VALIDATE = ROOT / "scripts" / "validate_run.py"
LAYOUT_TEST = ROOT / "scripts" / "tests" / "test_layout_proportions.py"
VALIDATE_TEST = ROOT / "scripts" / "tests" / "test_validate_run.py"
AUDIT = ROOT / "scripts" / "audit_adaptive.py"
KIND_TEST = ROOT / "scripts" / "tests" / "test_kind_taxonomy.py"
SELFCHECK = ROOT / "evals" / "harness" / "selfcheck.py"
# 变异的目标不一定是被测源码，也可以是**素材**（fixture 本身就是要被检查的对象）。
# 目标文件必须存在 —— 脚本被裁撤后留着悬空引用，会让探针**崩在中途**，
# 而崩点之后的所有探针一条都不会跑（曾经如此：audit_fonts.py 被删后，排在它后面的
# fixture 可移植性与文档锚点两条探针再没执行过，README 里却还写着它们验过）。
GOLDEN_LAYOUT_REPORT = (ROOT / "evals" / "fixtures" / "golden"
                        / "layout-no-device-derived-coordinates" / "pass"
                        / "diff" / "layout-proportions.json")
# 文档也是被检查的对象：标题是锚点的来源，改标题不改引用就会产生断链。
CONTRACT_DOC = ROOT / "references" / "artifact-contract.md"
# 另一份被检查的文档：它承载两轴八类的正文表与关系示例。
SIZING_DOC = ROOT / "references" / "sizing-and-positioning.md"

# 测试要用带 Pillow 的解释器（test_validate_run 会造 PNG）。
#
# 注意**不能用** ``Path(...).resolve()``：那会把 venv 的 ``python3`` 符号链接解到真实
# 解释器，venv 的站点配置随之丢失，子进程 import PIL/PyYAML 直接失败 —— 于是「基线」
# 就已经不是基线，所有探针都会被误读成「断言有效」。这正是本脚本开头说的那类坑。
def test_python() -> str:
    venv = ROOT / ".runtime" / "venv" / "bin" / "python3"
    return os.path.abspath(venv if venv.exists() else Path(sys.executable))


# (说明, 被改文件, 测试文件, 原文, 改成)
PROBES = [
    ("关掉字面量检测", CHECK, LAYOUT_TEST,
     "    violations, ambiguous = [], []\n    for number, raw in enumerate(lines, start=1):",
     "    return [], []\n    for number, raw in enumerate(lines, start=1):"),
    ("不做注释剥离", CHECK, LAYOUT_TEST,
     "    code_lines = strip_comments(lines)",
     "    code_lines = list(lines)"),
    ("禁止项配回旧写法（边缘值配中心比例）", PLAN, LAYOUT_TEST,
     '("x", "centerX", device_center["x"], ratios["centerXRatio"],',
     '("x", "centerX", device_box.x, ratios["centerXRatio"],'),
    ("取消小数值待判", CHECK, LAYOUT_TEST,
     "            if abs(value) > DESIGN_SCALE_MAX_PT:",
     "            if True:"),
    ("取消近零过滤", CHECK, LAYOUT_TEST,
     '              and abs(item["deviceDerivedPt"]) >= MIN_MEANINGFUL_PT]',
     "]"),
    ("文字块判据退回只看 ownText", PLAN, LAYOUT_TEST,
     '    height = (element.get("rect") or {}).get("height") or 0\n'
     '    return bool(element.get("text")) and height <= TEXT_BLOCK_MAX_HEIGHT_PT',
     "    return False"),
    ("不区分位置轴（丢掉 xRatio/yRatio）", PLAN, LAYOUT_TEST,
     '            "ratios": ratios,',
     '            "ratios": {k: v for k, v in ratios.items()\n'
     '                        if k in ("centerXRatio", "centerYRatio",\n'
     '                                 "widthRatio", "heightRatio")},'),
    ("违规不再给出应使用的比例", CHECK, LAYOUT_TEST,
     '"expectedRatio": best.get("ratioInstead"),',
     '"expectedRatio": None,'),
    ("合规也算失败（恒挂）", CHECK, LAYOUT_TEST,
     '    proportional = [r for r in relations if r.get("kind") == "proportional"]',
     '    proportional = []'),
    # ---- 闭合契约的**新判据**：每一条都是「生成端与检查端必须一起改」的那种 ----
    #
    # 这一组探针是这一轮的重点。契约从「布局关系必须用比例表达」改成
    # 「尺寸按闭合方式声明、位置相对直接父视图」，再把 `fixed` 从默认值降级为特例
    # 之后，新增了八类关系、两条计划自洽判据（check_bases / check_forbidden_targets）、
    # 三条分类判据，以及**源码侧的逐类核对**（intrinsic 不得写等值常量 / bounded 必须有
    # >= <= 原语 / aspect-ratio 必须有比例约束 / fixed 必须带 why）。这些代码全都**新写**，
    # 而新写的代码最容易变成「跑得动但没人验过」：实测里 `unanchoredInset` 那条分支
    # 因为把自己算作「兄弟共享」而成了死代码，17 条 reviewHint 里它一条都没出过。
    # 所以每一条新判据都必须有一条探针证明它真的在判。
    ("尺寸轴不再认「两侧内边距闭合」", PLAN, LAYOUT_TEST,
     "    return all(0 <= value <= DESIGN_INSET_MAX_PT and is_design_value(value)\n"
     "               for value in (lead, trail))",
     "    return False"),
    ("兄弟共享把自己也算进去（自证）", PLAN, LAYOUT_TEST,
     "                          if index != own)",
     "                          if True)"),
    ("设计值容差放宽到 0.08", PLAN, LAYOUT_TEST,
     "INSET_ROUND_TOL_PT = 0.01",
     "INSET_ROUND_TOL_PT = 0.08"),
    ("页面外框不再按铺满处理", PLAN, LAYOUT_TEST,
     "OUTER_FRAME_AREA_RATIO = 0.9",
     "OUTER_FRAME_AREA_RATIO = 1.5"),
    ("第一层子视图不再强制按页面比例", PLAN, LAYOUT_TEST,
     "    if force_proportional:",
     "    if False:"),
    ("接近原点的比例照收进禁止清单", PLAN, LAYOUT_TEST,
     "            if abs(absolute) < MIN_MEANINGFUL_PT:",
     "            if False:"),
    ("不核对区域基准与父视图", CHECK, LAYOUT_TEST,
     '    for region in regions or []:\n        has_parent = "parentIndex" in region',
     '    for region in []:\n        has_parent = "parentIndex" in region'),
    ("禁止清单允许指向非比例关系", CHECK, LAYOUT_TEST,
     '            if kind is not None and kind != "proportional":',
     "            if False:"),
    ("禁止项缺 ratioInstead 也不报", CHECK, LAYOUT_TEST,
     '        if item.get("ratioInstead") is None:',
     "        if False:"),
    ("禁止项锚点不再校验", CHECK, LAYOUT_TEST,
     '        axis = ANCHOR_AXIS.get(anchor)\n        if axis is None:',
     '        axis = ANCHOR_AXIS.get(anchor) or "x"\n        if False:'),
    ("贴边关系允许带比例系数", CHECK, LAYOUT_TEST,
     '                    "kind": "pinned-with-ratio",',
     '                    "kind": "pinned-with-ratio-disabled",'),
    ("居中关系允许带比例系数", CHECK, LAYOUT_TEST,
     '                    "kind": "centered-with-ratio",',
     '                    "kind": "centered-with-ratio-disabled",'),
    ("fixed 不再要求给设计值", CHECK, LAYOUT_TEST,
     '            if isinstance(value, bool) or not isinstance(value, (int, float)):\n'
     '                problems.append({\n'
     '                    "kind": "fixed-missing-value",',
     '            if False:\n'
     '                problems.append({\n'
     '                    "kind": "fixed-missing-value",'),
    ("fixed 允许带比例系数", CHECK, LAYOUT_TEST,
     '                    "kind": "fixed-with-ratio",',
     '                    "kind": "fixed-with-ratio-disabled",'),
    ("比例关系不再要求基准", CHECK, LAYOUT_TEST,
     '        if not (rel.get("of") or "").strip():',
     "        if False:"),
    ("完全不核对布局比例", VALIDATE, VALIDATE_TEST,
     "    violations.extend(check_layout_proportions(\n"
     "        run_dir, source_roots, gate_status, warnings))",
     "    pass"),
    ("不给 --source 时不告警", VALIDATE, VALIDATE_TEST,
     "        if report is None:\n            relation_count",
     "        if False:\n            relation_count"),
    # 锚点只取到 ``warnings.append(`` 为止：告警文案经常随口径一起改，
    # 把文案写进锚点会让探针在「改了措辞」时静默失效（旧版就是这么失的效）。
    ("计划未声明时也不告警", VALIDATE, VALIDATE_TEST,
     "    if not declared:\n        warnings.append(",
     "    if not declared:\n        _unused = ("),
    ("不做「比例结论 vs 闸门」交叉校验", VALIDATE, VALIDATE_TEST,
     "    if report is not None and report.get('status') not in (None, 'pass'):",
     "    if False:"),
    ("跳过计划质量层（--plan-only）", VALIDATE, VALIDATE_TEST,
     "        proc = _run_checker(script, plan_path, [], scratch_report, plan_only=True)",
     "        proc = None"),
    # ---- 闭合契约的新判据：源码侧逐类核对 + fixed 必须给出 why ----
    #
    # 这一组是本轮（v3 两轴口径 → v4 闭合契约）新增的代码。按 repo 的规矩：
    # **新写的判据每一条都要有探针证明它真的在判**，因为新代码最容易变成
    # 「跑得动但没人验过」。下面三条各自盯住新契约最容易退化的三个点：
    ("fixed 不再要求给出 why（退回「设计稿写了就照抄」）", CHECK, LAYOUT_TEST,
     '            # fixed 是**特例**，不是默认值：它必须带 why，说明「固定性本身是设计意图」。\n'
     '            # 闭合契约下这条判据是必须的 —— 设计稿给了 bounds.width/height 是**事实**，\n'
     '            # 把它写成固定约束是**决策**。没有 why，两者在产物里长得一模一样，\n'
     '            # 于是「照抄设计稿尺寸」这个新契约要拦的头号问题就没有任何可核对的痕迹。\n'
     '            if not (rel.get("why") or "").strip():',
     '            # 探针：短路掉 why 守卫。锚点带上上下文，\n'
     '            # 否则会误改 intrinsic 分支里那条字面相同的守卫（replace 只换第一处）。\n'
     '            if False:'),
    ("生成端不再把 fixed 标成「候选」（去掉 needsReview）", PLAN, LAYOUT_TEST,
     '        "why": f"按设计稿原值 {size:g}pt（{evidence}），推为固定尺寸的**候选**",\n'
     '        "needsReview": True,',
     '        "why": f"按设计稿原值 {size:g}pt（{evidence}），推为固定尺寸的**候选**",'),
    ("源码侧不再核对 intrinsic/bounded 的轴被写成 == 常量", CHECK, LAYOUT_TEST,
     "                hits = size_constant_hits(text, axis)",
     "                hits = []"),
    # ---- deliveryReady 的三态推导 ----
    # 这里必须复刻**历史上真实的那段函数体**（`or {}` + `.get(...) == .get(...)`），
    # 而不是随手把守卫删掉：删守卫会让 `unsupported['count']` 在 `{}` 上取下标直接
    # KeyError 掉栈，测试同样变红 —— 但那是崩栈红，要守的断言一次都没执行。
    ("缺 unsupported 对象时又按「复核完毕」算（旧写法）", VALIDATE, VALIDATE_TEST,
     "    unsupported = gate.get('unsupported')\n"
     "    if not isinstance(unsupported, dict):\n"
     "        return None\n"
     "    if any(not isinstance(unsupported.get(key), int) for key in ('count', 'reviewedCount')):\n"
     "        return None\n"
     "    if any(statuses.get(key) != 'pass' for key in gate_keys):\n"
     "        return False\n"
     "    return unsupported['count'] == unsupported['reviewedCount']",
     "    unsupported = gate.get('unsupported') or {}\n"
     "    if any(statuses.get(key) != 'pass' for key in gate_keys):\n"
     "        return False\n"
     "    return unsupported.get('count') == unsupported.get('reviewedCount')"),
    ("推不出来时不留痕（静默跳过一致性核对）", VALIDATE, VALIDATE_TEST,
     "            if expected is None:",
     "            if False:"),
    # ---- fixture 的可移植性检查（被检查的对象是素材，所以变异改的是素材）----
    ("fixture 里又出现钉死机器的绝对路径", GOLDEN_LAYOUT_REPORT, SELFCHECK,
     '  "plan": "diff/layout-proportions-plan.json",',
     '  "plan": "/Users/probe/Desktop/somewhere/diff/layout-proportions-plan.json",'),
    # ---- 文档链接与锚点检查（变异改的是标题，被检查的是别处对它的引用）----
    #
    # 这条探针模拟的是**最容易被当成安全操作的那个动作**：改一个章节标题的用词。
    # 文件在、内容在、读起来毫无问题，只有照着链接点过去的人才发现跳不到 ——
    # 所以它必须由自检兜住，而不是靠人记得「刚才好像改过标题」。
    ("章节改名后引用锚点不跟着改", CONTRACT_DOC, SELFCHECK,
     "### 布局关系与控件尺寸的约束口径（强制）",
     "### 布局关系与控件尺寸的约束口径（原则）"),
    # ---- 类别表守卫本身（被检查的对象是守卫，所以变异改的是清单与文档）----
    #
    # 为什么守卫也要探针：`audit_adaptive.KIND_FALLBACK_ORDER` 在改到两轴八类时
    # 只补到五类，漏掉的三类（bounded / equal / aspect-ratio）会让只声明了那几类的
    # 区域拿不到类别、下游按类别分派的判据**静默跳过** —— 而 15 组回归全绿、闸门照过。
    # 这类缺陷没有任何现存测试能发现，全是靠人肉扫出来的；守卫若不配探针，
    # 它自己也会在下次改口径时悄悄退化。
    ("回退清单缩回修复前的五类（漏三类）", AUDIT, KIND_TEST,
     'KIND_FALLBACK_ORDER = ("fixed", "pinned", "intrinsic", "proportional", "centered",\n'
     '                       "bounded", "equal", "aspect-ratio")',
     'KIND_FALLBACK_ORDER = ("fixed", "pinned", "intrinsic", "proportional", "centered")'),
    ("真相源被缩回旧五类", CHECK, KIND_TEST,
     'RELATION_KINDS = ("fixed", "pinned", "proportional", "intrinsic", "bounded",\n'
     '                  "equal", "centered", "aspect-ratio")',
     'RELATION_KINDS = ("fixed", "pinned", "proportional", "intrinsic", "centered")'),
    # 这条模拟的是最容易发生的一种回退：改口径时只改了代码与正文，
    # 顺手在别处（注释/文档）又写下旧计数词，于是每次 grep 都在重新教旧口径。
    ("文档里又出现废弃的类别计数说法", CONTRACT_DOC, KIND_TEST,
     "2. **`fixed` 不是默认值，而且必须给 `why`。**",
     "2. **`fixed` 不是默认值。** 五类 kind 各自带齐必需字段。"),
    # 文档示例写成实现不认的形状，是本轮最贵的一处：示例用嵌套 relations + 不存在的
    # constant 字段，喂给校验器**判 pass** —— Agent 照抄会以为已经声明了内边距，
    # 而产物里什么都没有。所以「示例合规」这条断言必须自己也被验过。
    ("文档示例又写成嵌套 relations（实现根本不读）", SIZING_DOC, KIND_TEST,
     ' "kind": "pinned", "edges": ["leading", "trailing"],\n'
     ' "insets": {"leading": 16, "trailing": 16},',
     ' "kind": "bounded", "min": 280, "max": 600,\n'
     ' "relations": [{"kind": "pinned", "edge": "leading", "constant": 16}],'),
]


def run_test(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run([test_python(), str(path)], capture_output=True, text=True)


def first_message(stdout: str) -> str:
    """从测试输出里挑一行最说明问题的，用于探针日志。

    直接取首行会踩到表格类输出的表头与「✅ 如预期」行（`selfcheck.py` 就是这种形态），
    于是日志变成「测试变红：用例 fixture」—— 看不出红在哪，探针的价值就没了。
    所以先跳过装饰线、表头与如预期行，取第一条真正的结论行。
    """
    for line in (raw.strip() for raw in stdout.strip().splitlines()):
        if not line or set(line) <= set("- "):
            continue
        if "✅" in line or "样本" in line or ("用例" in line and "fixture" in line):
            continue
        return line
    return "(测试无输出)"


def main() -> int:
    failures = []
    originals = {}          # 每个被改动文件的基线内容，用于收尾的逐文件复原校验
    for name, target, test, old, new in PROBES:
        # 悬空引用必须先拦住：脚本被裁撤、探针没跟着删，读文件会直接 FileNotFoundError
        # 掉栈 —— 而崩点**之后**的探针一条都不会跑，它们的名字却还留在 PROBES 里，
        # 让人以为验过了。这是「探针本身也会骗人」的第五种形态（前四种见模块 docstring）。
        missing = [path for path in (target, test) if not path.exists()]
        if missing:
            failures.append(
                f"  ✗「{name}」目标不存在："
                f"{[str(path.relative_to(ROOT)) for path in missing]} —— 探针无效"
                "（脚本已裁撤？删掉这条探针，别让它把排在后面的探针一起藏掉）")
            continue
        original = target.read_text(encoding="utf-8")
        originals.setdefault(target, original)
        if old not in original:
            failures.append(f"  ✗「{name}」锚点没找到 —— 探针无效（这不等于断言有效）")
            continue
        mutated = original.replace(old, new, 1)
        target.write_text(mutated, encoding="utf-8")
        try:
            # 探针有效性：改动必须真的落到源码里。少了这一步，锚点写错、路径解析错
            # 都会被误读成「断言有效」—— 这一轮里已经发生过两次。
            if target.read_text(encoding="utf-8") == original:
                failures.append(f"  ✗「{name}」改动没有落到源码里 —— 探针无效")
                continue
            proc = run_test(test)
        finally:
            target.write_text(original, encoding="utf-8")
        if proc.returncode != 0:
            # 「变红」必须由断言触发。崩栈同样是退出码非 0，但它证明不了那条断言 ——
            # 这一轮又踩到一次：探针把守卫删掉后，被测函数在空对象上取下标直接 KeyError
            # 掉栈，输出显示「测试变红」，而要守的断言一次都没执行。所以崩栈单独判「无效」，
            # 并且要求探针复刻**历史上真实的那段实现**，而不是随手删代码凑一个红。
            if "Traceback (most recent call last)" in proc.stderr:
                last = (proc.stderr.strip().splitlines() or ["(无)"])[-1]
                failures.append(
                    f"  ✗「{name}」测试崩栈变红，不是断言触发 —— 断言仍未被验证：{last[:90]}")
                continue
            first = first_message(proc.stdout)
            print(f"  ✓「{name}」→ 测试变红：{first[:80]}")
        else:
            failures.append(f"  ✗「{name}」测试仍全绿 —— 这条断言是空的")

    # 复原校验分两路，缺一不可：
    #   1) **逐文件比对字节** —— 目标可能是素材（如 golden 样本），只复跑测试套件看不出它没还原；
    #   2) **复跑所有被用到的测试套件** —— 证明复原后行为也回到基线，而不只是字节相同。
    dirty = [str(path.relative_to(ROOT)) for path, text in originals.items()
             if path.read_text(encoding="utf-8") != text]
    if dirty:
        failures.append(f"  ✗ 探针流程污染了源码（内容未还原）：{dirty}")

    suites = []
    for _, _, test, _, _ in PROBES:
        if test not in suites:
            suites.append(test)
    for path in suites:
        proc = run_test(path)
        if proc.returncode != 0:
            failures.append(f"  ✗ 复原后 {path.name} 未通过，探针流程污染了源码")
    if not dirty:
        print(f"\n复原后复测：{len(suites)} 个测试套件均通过，"
              f"{len(originals)} 个被改文件内容已还原")
    for line in failures:
        print(line)
    if failures:
        print(f"变异探针未通过：{len(failures)} 项")
        return 1
    print(f"变异探针 {len(PROBES)} 项全部有效：每条断言都能抓到对应的实现回退，"
          "且没有一项是靠崩栈变红的")
    return 0


if __name__ == "__main__":
    sys.exit(main())
