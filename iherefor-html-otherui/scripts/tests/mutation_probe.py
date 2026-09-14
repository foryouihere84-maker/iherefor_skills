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
  无效，并要求探针复刻**历史上真实的那段实现**，而不是删几行代码凑一个红。

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
FONTS = ROOT / "scripts" / "audit_fonts.py"
LAYOUT_TEST = ROOT / "scripts" / "tests" / "test_layout_proportions.py"
VALIDATE_TEST = ROOT / "scripts" / "tests" / "test_validate_run.py"
FONTS_TEST = ROOT / "scripts" / "tests" / "test_audit_fonts.py"
SELFCHECK = ROOT / "evals" / "harness" / "selfcheck.py"
# 变异的目标不一定是被测源码，也可以是**素材**（fixture 本身就是要被检查的对象）。
GOLDEN_COMPARISON = (ROOT / "evals" / "fixtures" / "golden"
                     / "same-size-needs-region-evidence" / "pass" / "diff" / "comparison.json")

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
     '("xRatio", "yRatio", "centerXRatio", "centerYRatio",\n'
     '                        "widthRatio", "heightRatio")},',
     '("centerXRatio", "centerYRatio", "widthRatio", "heightRatio")},'),
    ("违规不再给出应使用的比例", CHECK, LAYOUT_TEST,
     '"expectedRatio": best.get("ratioInstead"),',
     '"expectedRatio": None,'),
    ("合规也算失败（恒挂）", CHECK, LAYOUT_TEST,
     '    proportional = [r for r in relations if r.get("kind") == "proportional"]',
     '    proportional = []'),
    ("完全不核对布局比例", VALIDATE, VALIDATE_TEST,
     "    violations.extend(check_layout_proportions(\n"
     "        run_dir, source_roots, gate_status, warnings))",
     "    pass"),
    ("不给 --source 时不告警", VALIDATE, VALIDATE_TEST,
     "        if report is None:\n            relation_count",
     "        if False:\n            relation_count"),
    ("计划未声明时也不告警", VALIDATE, VALIDATE_TEST,
     "    if not declared:\n        warnings.append(\n"
     "            'ui-implementation-plan.json 未声明 layoutProportions：组件之间的布局关系'",
     "    if not declared:\n        _unused = (\n"
     "            'ui-implementation-plan.json 未声明 layoutProportions：组件之间的布局关系'"),
    ("不做「比例结论 vs 闸门」交叉校验", VALIDATE, VALIDATE_TEST,
     "    if report is not None and report.get('status') not in (None, 'pass'):",
     "    if False:"),
    ("跳过计划质量层（--plan-only）", VALIDATE, VALIDATE_TEST,
     "        proc = _run_checker(script, plan_path, [], scratch_report, plan_only=True)",
     "        proc = None"),
    # ---- 字体链（audit_fonts + validate_run 的字体层）----
    ("字体族名不做归一化", FONTS, FONTS_TEST,
     "    text = re.sub(r'[\\s_\\-]+', ' ', text).strip().lower()",
     "    return text"),
    ("系统/generic 关键字不按归一化形式匹配", FONTS, FONTS_TEST,
     "SYSTEM_KEYWORDS = {norm_family(name) for name in (",
     "SYSTEM_KEYWORDS = {name for name in ("),
    ("测量链路失败时不再硬拦（照样下结论）", FONTS, FONTS_TEST,
     "    if probe['measurementOk'] is False:\n        blocked = 'font-measurement-failed'",
     "    if False:\n        blocked = 'font-measurement-failed'"),
    ("未做字体测量时不再判证据不足", FONTS, FONTS_TEST,
     "    elif not judged:\n        result['reason'] = 'no-runtime-font'",
     "    elif False:\n        result['reason'] = 'no-runtime-font'"),
    ("完全不核对基准字体链", VALIDATE, VALIDATE_TEST,
     "    violations.extend(check_font_chain(run_dir, gate_status, warnings))",
     "    pass"),
    ("legacy run 顺带跳过字体链", VALIDATE, VALIDATE_TEST,
     "        check_font_chain(run_dir, {}, warnings, warn_only=True)",
     "        pass"),
    # ---- deliveryReady 的三态推导 ----
    # 这里必须复刻**历史上真实的那段函数体**（`or {}` + `.get(...) == .get(...)`），
    # 而不是随手把守卫删掉：删守卫会让 `unsupported['count']` 在 `{}` 上取下标直接
    # KeyError 掉栈，测试同样变红 —— 但那是崩栈红，要守的断言一次都没执行。
    ("缺 unsupported 对象时又按「复核完毕」算（旧写法）", VALIDATE, VALIDATE_TEST,
     "    if any(not isinstance(unsupported.get(key), int) for key in ('count', 'reviewedCount')):\n"
     "        return None\n"
     "    if any(statuses.get(key) != 'pass' for key in GATE_KEYS):\n"
     "        return False\n"
     "    return unsupported['count'] == unsupported['reviewedCount']",
     "    if any(statuses.get(key) != 'pass' for key in GATE_KEYS):\n"
     "        return False\n"
     "    return unsupported.get('count') == unsupported.get('reviewedCount')"),
    ("推不出来时不留痕（静默跳过一致性核对）", VALIDATE, VALIDATE_TEST,
     "            if expected is None:",
     "            if False:"),
    # ---- fixture 的可移植性检查（被检查的对象是素材，所以变异改的是素材）----
    ("fixture 里又出现钉死机器的绝对路径", GOLDEN_COMPARISON, SELFCHECK,
     '  "reference": "images/reference.png",',
     '  "reference": "/Users/probe/Desktop/somewhere/images/reference.png",'),
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
