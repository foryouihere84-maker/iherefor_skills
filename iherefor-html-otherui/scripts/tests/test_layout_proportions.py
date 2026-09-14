#!/usr/bin/env python3
"""回归：组件之间的布局关系必须用比例表达。

这条约束有两个可执行的部分，两边都要有「必须过 / 必须挂」：

1. ``layout_proportions.py`` 把事实表里的绝对位置转成比例规格，并且**必须**同时给出
   「探针设备上的绝对值」清单 —— 那张清单是给校验器用来抓「照抄绝对值」的。
2. ``check_layout_proportions.py`` 拿那份规格去核源码。**这个测试的核心是变异探针**：
   先把一份合规源码判为通过，只把其中一条比例换成它的设备推导值，再要求它被判为违规。
   没有这一步，测试只是「脚本跑得动」，而不是「脚本认得错」。

顺便固定住几条降噪规则 —— 它们是踩出来的，不是想出来的：注释里的 ``// (393 x 852)``、
颜色的 ``22 / 255.0``、``100%`` 都不是违规；小数值（≤48pt）与设计常量无法区分，
只能待判。把这几条写成断言，是为了防止以后有人「顺手放宽」把信噪比又弄坏。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN_SCRIPT = ROOT / "scripts" / "layout_proportions.py"
CHECK_SCRIPT = ROOT / "scripts" / "check_layout_proportions.py"

VIEWPORT = {"width": 402.0, "height": 874.0, "devicePixelRatio": 3.0,
            "scrollX": 0.0, "scrollY": 0.0}


def element(index, eid, rect, **extra):
    """按渲染器的真实字段造一个元素。

    ``rectInReference == rect * devicePixelRatio`` 是渲染器在设备视口上渲染的产物，
    也是 ``layout_proportions.py`` 用来判定坐标空间的唯一依据 —— 所以 fixture 必须
    如实构造这条恒等式，不能为了省事随手写个数。
    """
    dpr = VIEWPORT["devicePixelRatio"]
    payload = {
        "index": index, "id": eid, "className": eid, "tag": "div",
        "rect": rect,
        "rectInReference": {k: v * dpr for k, v in rect.items()},
        "ownText": "", "ownsText": False, "text": "", "src": None, "assets": None,
    }
    payload.update(extra)
    return payload


def page_facts(elements):
    return {"title": "fixture", "url": "file:///fixture/index.html",
            "viewport": dict(VIEWPORT), "elements": elements}


def standard_facts():
    """四个元素，各自固定一条判据：

    * ``page``：高 852 含文本 —— 大容器不能因为「有文本」就被判成文字块；
    * ``Card``：无文本无图 —— 全比例；
    * ``legal``：16pt 高且有文本 —— 判为文字块，高度 intrinsic；
    * ``hero``：有 assets —— 不因文本被判文字块。
    """
    return page_facts([
        element(0, "page", {"x": 0, "y": 0, "width": 393, "height": 852},
                text="Privacy Terms Restore", className="page"),
        element(1, "Card", {"x": 16, "y": 700, "width": 361, "height": 68}),
        element(2, "legal", {"x": 83, "y": 801, "width": 232, "height": 16},
                text="Privacy\nTerms\nRestore"),
        element(3, "hero", {"x": 0, "y": 0, "width": 393, "height": 321},
                assets=[{"path": "hero.png"}], text="hero"),
    ])


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return path


def run(script, *args):
    proc = subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True)
    return proc


def run_plan(tmp, facts_path, *extra, output_name="plan.json", expect=0):
    out = tmp / output_name
    proc = run(PLAN_SCRIPT, "--page-facts", str(facts_path),
               "--output", str(out), "--quiet", *extra)
    if proc.returncode != expect:
        raise AssertionError(f"layout_proportions 退出码 {proc.returncode}！= {expect}\n"
                             f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    if expect != 0:
        return None
    return json.loads(out.read_text())


def run_check(tmp, plan_path, source_dir, *extra):
    out = tmp / "check.json"
    proc = run(CHECK_SCRIPT, "--plan", str(plan_path), "--source", str(source_dir),
               "--output", str(out), *extra)
    data = json.loads(out.read_text()) if out.is_file() else None
    return proc, data


def compliant_source(plan):
    """按计划生成一份「合规」的 Objective-C 源码：位置与尺寸一律用 multiplier 表达。

    这是实现侧应有的样子 —— 没有任何一个数字来自「探针设备上的绝对值」。
    """
    lines = ["// 由 layoutProportions 生成：位置与尺寸一律用比例，不使用设备绝对值",
             "static void buildProportionalLayout(UIView *root) {",
             "  [root layoutIfNeeded];"]
    for region in plan["layoutProportions"]["regions"]:
        name = region["region"]
        for rel in region["relations"]:
            if rel["kind"] != "proportional":
                continue
            lines.append(
                f"  // {rel['id']} 比例 {rel['ratio']}")
            if rel["axis"] == "width":
                lines.append(f"  [[self {name}WidthAnchor] constraintEqualTo:"
                             f"root.widthAnchor multiplier:{rel['ratio']}];")
            elif rel["axis"] == "height":
                lines.append(f"  [[self {name}HeightAnchor] constraintEqualTo:"
                             f"root.heightAnchor multiplier:{rel['ratio']}];")
            else:
                anchor = "centerYAnchor" if rel["axis"] == "y" else "centerXAnchor"
                base = "heightAnchor" if rel["axis"] == "y" else "widthAnchor"
                lines.append(f"  [[self {name}{anchor[:1].upper()}{anchor[1:]}] "
                             f"constraintEqualTo:root.{base} multiplier:{rel['ratio']}];")
    lines.append("}")
    return "\n".join(lines) + "\n"


def mutation_target(plan):
    """挑一条**大数值**比例关系作为变异点：必须能被无歧义地判为设备推导值。"""
    from_check = plan["layoutProportions"]["forbiddenLiterals"]
    big = [item for item in from_check if abs(item["deviceDerivedPt"]) > 48]
    if not big:
        raise AssertionError("计划里没有可用于变异的大数值关系，测试前提不成立")
    return big[0]


def main():
    problems = []

    def check(condition, message):
        if not condition:
            problems.append(message)

    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        facts_path = write_json(tmp / "reference" / "page-facts.json", standard_facts())

        # ---------------------------------------------------------------- 计划推导
        plan = run_plan(tmp, facts_path)
        props = plan["layoutProportions"]
        diag = plan["diagnostics"]
        regions = {r["region"]: r for r in props["regions"]}

        # 用例 1：坐标空间必须由 rectInReference == rect*dpr 自动判定
        check(diag["rectSpace"] == "device",
              f"用例1：rect 坐标空间判定为 {diag['rectSpace']}，应为 device")
        check(props["basisSize"] == {"width": 402.0, "height": 874.0},
              f"用例1：比例基准应为探针视口 402x874，得到 {props['basisSize']}")

        # 用例 2：比例 = rect / basis，且**只过一层** scale。
        # 过两层是这类工具最容易犯的错，所以这里按 rect/basis 直接验算。
        card = {r["ratio"] for r in regions["Card"]["relations"] if r["id"] == "Card.width"}
        expected = round(361 / 402, 6)
        check(card == {expected},
              f"用例2：Card.width 比例应为 {expected}（361/402），得到 {card}")

        # 用例 3：大容器含文本不能判成文字块；16pt 文字块必须判成 intrinsic
        # （intrinsic 关系不带 axis，只能按 id 取，不能按 axis 过滤）
        page_height = next(r for r in regions["page"]["relations"] if r["id"] == "page.height")
        check(page_height["kind"] == "proportional",
              "用例3：852pt 高的整页容器含文本，仍应 proportional"
              "（高度阈值用来区分文字块与布局容器）")
        legal_height = next(r for r in regions["legal"]["relations"] if r["id"] == "legal.height")
        check(legal_height["kind"] == "intrinsic",
              f"用例3：16pt 且有文本的盒子应判 intrinsic，得到 {legal_height['kind']}")
        check(bool((legal_height.get("why") or "").strip()),
              "用例3：intrinsic 关系必须写明 why")
        hints = {h["region"] for h in diag.get("reviewHints") or []}
        check("legal" in hints,
              "用例3：由「短且有文本」推断出的文字块必须给出 reviewHint 让人复核")

        # 用例 4：禁止清单的绝对值与比例必须**同量纲**。
        # 早期版本把左边缘的绝对值配给了中心比例，等于让人拿 0 去换 0.4888。
        dims = {"centerX": "width", "leading": "width", "width": "width",
                "centerY": "height", "top": "height", "height": "height"}
        inconsistent = []
        for item in props["forbiddenLiterals"]:
            anchor = item["relation"].rsplit(".", 1)[1]
            if anchor not in dims:
                inconsistent.append(item)
                continue
            basis = props["basisSize"][dims[anchor]]
            if abs(item["deviceDerivedPt"] / basis - item["ratioInstead"]) > 1e-4:
                inconsistent.append(item)
        check(not inconsistent,
              f"用例4：{len(inconsistent)} 条禁止项的绝对值与比例不同量纲，例如 "
              f"{inconsistent[:2]}")

        # 用例 5：接近原点的绝对值不构成证据（0 在任何设备上都成立）
        check(not [f for f in props["forbiddenLiterals"] if abs(f["deviceDerivedPt"]) < 1],
              "用例5：禁止清单里不应有 |pt| < 1 的条目")
        check(diag["skippedForbiddenCount"] > 0,
              "用例5：page 在原点，应被记入 skippedForbidden 而不是禁止清单")

        # 用例 6：计划里不得给出任何「实现必需的绝对 pt」——只有比例。
        # 这条直接对应本 skill 的核心约束：布局关系必须按设计稿比例实现。
        leaked = []
        for region in props["regions"]:
            for rel in region["relations"]:
                if rel["kind"] != "proportional":
                    continue
                if "ratio" not in rel or "pt" in json.dumps(rel, ensure_ascii=False):
                    leaked.append(rel)
        check(not leaked, f"用例6：proportional 关系里出现了绝对 pt 值：{leaked[:2]}")

        # ------------------------------------------------------- 校验器：阳性对照
        source_dir = tmp / "src-pass"
        source_dir.mkdir()
        (source_dir / "ProportionalLayout.m").write_text(compliant_source(plan))

        proc, data = run_check(tmp, tmp / "plan.json", source_dir)
        check(proc.returncode == 0 and data and data["status"] == "pass",
              f"用例7：合规源码应通过，得到退出码 {proc.returncode}，"
              f"违规 {data and data['violations']}")
        check(data and data["proportionalIdiomCount"] > 0,
              "用例7：合规源码里应识别出比例原语")
        check(data and not any(v["kind"] == "no-proportional-idiom"
                               for v in data["violations"]),
              "用例7：合规源码不该被报「一个比例原语都没有」")

        # --------------------------------------------------- 校验器：变异探针（核心）
        # 只改一处：把一条比例换成它的设备推导值。这必须被抓到 ——
        # 否则上面的「合规通过」只是脚本跑得动，不是脚本认得错。
        target = mutation_target(plan)
        original = f"multiplier:{target['ratioInstead']}"
        mutated_source = compliant_source(plan).replace(
            original,
            f"constraintEqualToConstant:{target['deviceDerivedPt']:g}", 1)
        check(original in compliant_source(plan),
              f"用例8：探针前提不成立 —— 合规源码里找不到 {original}")
        check(mutated_source != compliant_source(plan),
              "用例8：变异没有生效，探针无效")

        mutated_dir = tmp / "src-fail"
        mutated_dir.mkdir()
        mutated_line = mutated_source.splitlines().index(
            next(l for l in mutated_source.splitlines() if "constraintEqualToConstant" in l)) + 1
        (mutated_dir / "ProportionalLayout.m").write_text(mutated_source)

        proc, data = run_check(tmp, tmp / "plan.json", mutated_dir)
        hits = [v for v in (data or {}).get("violations", [])
                if v["kind"] == "forbidden-literal-used"]
        check(proc.returncode == 1 and hits,
              f"用例8：把比例换成设备推导值 {target['deviceDerivedPt']:g}pt 未被拦下"
              f"（退出码 {proc.returncode}）")
        check(any(v["line"] == mutated_line and
                  abs((v.get("literal") or 0) - target["deviceDerivedPt"]) < 0.05 for v in hits),
              f"用例8：违规应精确定位到第 {mutated_line} 行的 "
              f"{target['deviceDerivedPt']:g}，得到 "
              f"{[(v.get('line'), v.get('literal')) for v in hits[:3]]}")
        check(hits and hits[0]["relation"] == target["relation"],
              f"用例8：应指向关系 {target['relation']}，得到 "
              f"{hits and hits[0]['relation']}")
        check(hits and hits[0]["expectedRatio"] == target["ratioInstead"],
              "用例8：违规必须同时给出「应当使用的比例」")

        # 用例 9：整页都是绝对值（一个比例原语都没有）必须被指出
        absolute_dir = tmp / "src-absolute"
        absolute_dir.mkdir()
        (absolute_dir / "HardCoded.m").write_text(
            "static const CGFloat kCanvasWidth = 393.0;\n"
            "static const CGFloat kCanvasHeight = 852.0;\n"
            "UIView *hero = [[UIView alloc] initWithFrame:CGRectMake(0, 0, 393, 472)];\n"
            "UIImageView *card = [[UIImageView alloc] initWithFrame:"
            "CGRectMake(16, 700, 361, 68)];\n")
        proc, data = run_check(tmp, tmp / "plan.json", absolute_dir)
        kinds = {v["kind"] for v in (data or {}).get("violations", [])}
        check(proc.returncode == 1 and "no-proportional-idiom" in kinds,
              f"用例9：整页绝对值应被报 no-proportional-idiom，得到 {kinds}")
        check(any(v.get("literal") == 393.0 for v in (data or {}).get("violations", [])),
              "用例9：393.0（画布宽）应被识别为设备推导值")

        # ------------------------------------------------------ 降噪规则（防回退）
        noise_dir = tmp / "src-noise"
        noise_dir.mkdir()
        (noise_dir / "Noise.m").write_text(
            "// (393 x 852, index.css `.page`) 是设计稿画布，不是布局值\n"
            "// an iOS 26 scene; keep <some> 26pt margin\n"
            "UIColor *ink = [UIColor colorWithRed:22 / 255.0 green:22 / 255.0 "
            "blue:22 / 255.0 alpha:1];\n"
            "/* 块注释里写 852 也不该算 */\n"
            "layer.backgroundSize = @\"100% 100%\";\n"
            "[[self view] widthAnchor].constant = 353.51;\n")
        proc, data = run_check(tmp, tmp / "plan.json", noise_dir)
        flagged = (data or {}).get("violations", [])
        check(not [v for v in flagged if v.get("literal") in (393.0, 852.0, 22.0)],
              f"用例10：注释/颜色通道/百分比里的数字被误报："
              f"{[(v.get('literal'), v.get('text', v.get('detail', ''))[:40]) for v in flagged][:3]}")
        # 393 与 852 出现在注释与颜色里，但 353.51 是真字面量且不在禁止清单里 ——
        # 于是这份文件应当「没有大数值违规」，只可能剩下缺少比例原语。
        check({v["kind"] for v in flagged} <= {"no-proportional-idiom"},
              f"用例10：噪声文件只应剩 no-proportional-idiom，得到 "
              f"{[v['kind'] for v in flagged]}")

        # 用例 11：小数值与设计常量无法区分 —— 待判，不计入违规。
        # 这一条是信噪比的关键：把 16/24/32 当违规会让报告被淹没。
        # 16 在这个 fixture 里确实是 Card.leading 的设备推导值，同时也正是最常见的
        # 标准边距 —— 两者在没有语法信息时无法区分。
        small_value = next(f["deviceDerivedPt"] for f in
                           plan["layoutProportions"]["forbiddenLiterals"]
                           if f["relation"] == "Card.leading")
        small = tmp / "src-small"
        small.mkdir()
        (small / "Spacing.m").write_text(
            f"// 故意用 {small_value:g}pt：它同时是某条关系的设备推导值，也是常见设计常量\n"
            f"[[self card] constraintEqualToConstant:{small_value:g}];\n"
            "[[self view] widthAnchor] multiplier:0.5;\n")
        proc, data = run_check(tmp, tmp / "plan.json", small)
        check(not [v for v in (data or {}).get("violations", [])
                   if v.get("literal") == small_value],
              f"用例11：{small_value:g}pt 与设计常量无法区分，不应计入违规")
        check(any(a["literal"] == small_value
                  for a in (data or {}).get("ambiguousLiterals", [])),
              f"用例11：{small_value:g}pt 应出现在 ambiguousLiterals 里待人工判断")

        # 用例 12：designConstants / --allow-values 是可复核的豁免
        allow_plan = json.loads((tmp / "plan.json").read_text())
        big_value = next(f["deviceDerivedPt"] for f in
                         allow_plan["layoutProportions"]["forbiddenLiterals"]
                         if f["deviceDerivedPt"] > 48)
        allow_dir = tmp / "src-allow"
        allow_dir.mkdir()
        (allow_dir / "Allowed.m").write_text(
            f"[[self view] widthAnchor] constant:{big_value:g};\n"
            "[[self view] widthAnchor] multiplier:0.5;\n")
        proc, data = run_check(tmp, tmp / "plan.json", allow_dir)
        check(any(v.get("literal") == big_value for v in (data or {}).get("violations", [])),
              f"用例12：未声明豁免时 {big_value:g} 应被记为违规（阳性前提）")

        allow_plan["layoutProportions"]["designConstants"] = [big_value]
        allow_path = write_json(tmp / "plan-allow.json", allow_plan)
        proc, data = run_check(tmp, allow_path, allow_dir)
        check(proc.returncode == 0,
              f"用例12：声明 designConstants 后应放行，退出码 {proc.returncode}")
        check(data and data["allowValues"] == [big_value],
              f"用例12：豁免值必须原样记入结果供复核，得到 {data and data['allowValues']}")

        # 用例 13：designConstants 只能是数字数组
        bad_plan = json.loads((tmp / "plan.json").read_text())
        bad_plan["layoutProportions"]["designConstants"] = ["standard 16pt margin"]
        bad_path = write_json(tmp / "plan-bad.json", bad_plan)
        proc, data = run_check(tmp, bad_path, allow_dir)
        check(proc.returncode != 0 and any(
            v["kind"] == "bad-design-constants" for v in (data or {}).get("violations", [])),
              "用例13：designConstants 放字符串必须被拒（避免把说明文字当豁免）")

        # --------------------------------------------------------- 计划的自身质量
        quality = json.loads((tmp / "plan.json").read_text())
        quality["layoutProportions"]["regions"][0]["relations"].append(
            {"id": "bad.kind", "kind": "absolute", "ratio": 0.5})
        quality["layoutProportions"]["regions"][1]["relations"].append(
            {"id": "bad.why", "kind": "intrinsic"})
        quality_path = write_json(tmp / "plan-quality.json", quality)
        proc, data = run_check(tmp, quality_path, source_dir)
        kinds = {v["kind"] for v in (data or {}).get("violations", [])}
        check("unknown-relation-kind" in kinds,
              f"用例14：非法 kind 必须被指出，得到 {kinds}")
        check("intrinsic-missing-why" in kinds,
              f"用例14：intrinsic 缺 why 必须被指出，得到 {kinds}")

        # 用例 15：计划里没有 layoutProportions 必须被指出
        empty_path = write_json(tmp / "plan-empty.json", {"schemaVersion": 1})
        proc, data = run_check(tmp, empty_path, source_dir)
        check(proc.returncode == 1 and any(
            v["kind"] == "missing-layout-proportions"
            for v in (data or {}).get("violations", [])),
              "用例15：计划缺 layoutProportions 必须被指出")

        # ---------------------------------------------------------------- 退出码
        proc = run(CHECK_SCRIPT, "--plan", str(tmp / "nope.json"), "--source", str(source_dir))
        check(proc.returncode == 2 and "Traceback" not in proc.stderr,
              f"用例16：计划文件缺失应干净退出 2，得到 {proc.returncode}：{proc.stderr[:200]}")

        empty_src = tmp / "src-empty"
        empty_src.mkdir()
        proc = run(CHECK_SCRIPT, "--plan", str(tmp / "plan.json"), "--source", str(empty_src))
        check(proc.returncode == 2, f"用例16：源码目录为空应退出 2，得到 {proc.returncode}")

        proc = run(PLAN_SCRIPT, "--page-facts", str(tmp / "nope.json"))
        check(proc.returncode == 2 and "Traceback" not in proc.stderr,
              f"用例16：事实表缺失应干净退出 2，得到 {proc.returncode}：{proc.stderr[:200]}")

        empty_elements = write_json(tmp / "empty-facts.json", {"elements": [], "viewport": VIEWPORT})
        proc = run(PLAN_SCRIPT, "--page-facts", str(empty_elements))
        check(proc.returncode == 2, f"用例16：事实表无 elements 应退出 2，得到 {proc.returncode}")

        # 用例 17：判不出坐标空间时**拒绝继续**，绝不猜。
        # 猜错就会把 scale 乘两遍，正是这条红线要防的系统性偏移。
        broken = standard_facts()
        for item in broken["elements"]:
            item["rectInReference"] = {k: v / 2 for k, v in item["rectInReference"].items()}
        broken_path = write_json(tmp / "broken-facts.json", broken)
        proc = run(PLAN_SCRIPT, "--page-facts", str(broken_path), "--output",
                   str(tmp / "broken.json"))
        check(proc.returncode == 2 and "坐标空间" in proc.stderr,
              f"用例17：坐标空间判不出来时应退出 2 并说明，得到 {proc.returncode}：{proc.stderr[:200]}")
        check(not (tmp / "broken.json").is_file(),
              "用例17：判不出来时不得写出计划文件（避免下游把它当成有效证据）")

        # 用例 18：显式指定与证据冲突时，继续但必须告警
        device_path = write_json(tmp / "runtime-device.json", {
            "screenBoundsPoints": {"width": 402, "height": 874},
            "screenshotPixels": {"width": 1206, "height": 2622}, "screenshotScale": 3,
        })
        proc = run(PLAN_SCRIPT, "--page-facts", str(facts_path), "--rect-space", "lanhu",
                   "--runtime-device", str(device_path), "--canvas", "393x852",
                   "--output", str(tmp / "lanhu.json"))
        check(proc.returncode == 0 and "证据指向" in proc.stderr,
              f"用例18：显式空间与证据冲突时应告警并继续，得到 {proc.returncode}："
              f"{proc.stderr[:200]}")

        # 用例 19：--rect-space lanhu 需要画布变换输入，缺了要干净退出
        proc = run(PLAN_SCRIPT, "--page-facts", str(facts_path), "--rect-space", "lanhu")
        check(proc.returncode == 2 and "Traceback" not in proc.stderr,
              f"用例19：lanhu 空间缺少变换输入应退出 2，得到 {proc.returncode}：{proc.stderr[:200]}")

        # 用例 20：区域必须同时给出「边缘」与「中心」两套比例。
        # 实现侧两种锚点都会用到（leading/top 与 centerX/centerY），只给中心比例
        # 会让「按左边缘对齐」这个最常见的写法没有可用的比例。
        #
        # 取比值时用 `.get` 而**不是下标**：键缺失要让上面那条断言报出「少了哪一套」，
        # 而不是让测试自己 KeyError 掉栈 —— 崩栈也是变红，但它把结论盖掉了，
        # 在变异探针里还会被误读成「断言有效」（见 mutation_probe.py）。
        expected_ratio_keys = {"xRatio", "yRatio", "centerXRatio", "centerYRatio",
                               "widthRatio", "heightRatio"}
        for region in props["regions"]:
            ratio_keys = set(region["ratios"])
            if ratio_keys != expected_ratio_keys:
                check(False, f"用例20：{region['region']} 的 ratios 缺键：{sorted(ratio_keys)}")
                break
        check(all(r["ratios"].get("xRatio") == round(
            next(e for e in standard_facts()["elements"] if e["id"] == r["region"])["rect"]["x"]
            / 402, 6) for r in props["regions"]),
              "用例20：xRatio 必须等于 rect.x / 视口宽")

        # 用例 21：校验器自己对「接近原点的绝对值」也要防一手。
        # 计划侧已经过滤，但如果计划是手写/旧版的，校验器不能因此把每个 0 都报成违规。
        raw_plan = json.loads((tmp / "plan.json").read_text())
        raw_plan["layoutProportions"]["forbiddenLiterals"].append(
            {"relation": "ghost.centerX", "deviceDerivedPt": 0.0,
             "why": "手工塞进来的原点值", "ratioInstead": 0.5})
        raw_path = write_json(tmp / "plan-rawzero.json", raw_plan)
        zero_dir = tmp / "src-zero"
        zero_dir.mkdir()
        (zero_dir / "Zeros.m").write_text(
            "[[self view] widthAnchor] multiplier:0.5;\n"
            "view.frame = CGRectMake(0, 0, 10, 20);\n"
            "self.alpha = 0;\n")
        proc, data = run_check(tmp, raw_path, zero_dir)
        check(proc.returncode == 0,
              f"用例21：计划里带 0 值禁止项时不应把每个 0 都报成违规，得到退出码 "
              f"{proc.returncode}：{data and data.get('violations')}")
        check(data and data["ignoredForbiddenCount"] == 1,
              "用例21：接近原点的禁止项应被记入 ignoredForbiddenCount 并给出告警")
        check(data and any("接近原点" in w for w in data["warnings"]),
              "用例21：忽略原点值必须留下告警，不能静默")
        # 光看退出码不够：0 会被「小数值待判」兜住，所以还要断言它连待判清单都不进。
        # 否则每个 0 都会以 ambiguousLiteral 的形式堆进报告，噪音照样成立。
        check(data and data["ambiguousLiteralCount"] == 0,
              f"用例21：0 值禁止项不应产生待判噪音，得到 "
              f"{data and [(a['literal'], a['relation']) for a in data['ambiguousLiterals'][:3]]}")

    for problem in problems:
        print(problem)
    if problems:
        print("比例布局契约未满足")
        return 1
    print("比例布局契约：坐标空间由证据判定、比例只过一层 scale、禁止项同量纲、"
          "文字块高度判 intrinsic、合规源码通过、把比例换成设备推导值被精确拦下、"
          "注释/颜色/百分比不误报、小数值待判、豁免可复核、用法错误干净退出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
