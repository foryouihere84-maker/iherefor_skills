#!/usr/bin/env python3
"""回归：产物契约校验器必须能识别缺件、篡改，以及「基准与设备不同源」这类证据失效。

契约见 references/artifact-contract.md；本测试构造多组 run 目录来固定其行为。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate_run.py"

GATE_PASS = {
    "reference": "pass", "browser": "pass", "sourceAssets": "pass",
    "implementation": "pass", "build": "pass", "tests": "pass", "visualDiff": "pass",
}
BASELINE_SIZE = (100, 200)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def make_png(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (10, 20, 30)).save(path)


def make_run(tmp, run_id, target_mode="ios-uikit-objective-c", gate_status=None,
             delivery_ready=False, legacy=False, baseline_size=BASELINE_SIZE,
             device_size=BASELINE_SIZE, page="demo"):
    """造一个 run 目录。

    ``page`` 默认共用 ``pages/demo``；涉及**页面级**产物（page-facts.json、字体链）的用例
    必须各给一个页面名 —— 页面级文件被同目录下所有 run 共享，共用页面会让用例之间
    互相污染，且依赖执行顺序。
    """
    run_dir = tmp / "pages" / page / "runs" / run_id
    page_dir = run_dir.parent.parent
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "actual").mkdir(exist_ok=True)
    (run_dir / "diff").mkdir(exist_ok=True)

    baseline = page_dir / "reference" / "reference.png"
    make_png(baseline, baseline_size)
    write_json(page_dir / "reference" / "approved.json", {"schemaVersion": 1, "sha256": "0" * 64})

    write_json(run_dir / "run.json", {
        "schemaVersion": 1, "runId": run_id, "pageId": "demo",
        "targetMode": target_mode, "parentRunId": None,
        "referenceBaseline": {"approved": "reference/approved.json", "sha256": "0" * 64},
        "status": "needs-review", "legacy": legacy,
    })
    write_json(run_dir / "review.json", {"schemaVersion": 1, "runId": run_id, "decision": "pending"})
    write_json(run_dir / "delivery-gate.json", {
        "schemaVersion": 1, "runId": run_id,
        "status": gate_status or dict(GATE_PASS),
        "unsupported": {"count": 0, "reviewedCount": 0, "items": []},
        "deliveryReady": delivery_ready,
        "blockingReasons": [] if delivery_ready else ["demo"],
    })
    write_json(run_dir / "ui-implementation-plan.json", {"schemaVersion": 1})
    write_json(run_dir / "resource-policy.json", {"schemaVersion": 1})
    write_json(run_dir / "runtime-device.json", {
        "schemaVersion": 1,
        "screenshotPixels": {"width": device_size[0], "height": device_size[1]},
        "screenshotScale": 3,
    })
    if target_mode.startswith("ios-"):
        write_json(run_dir / "ios-environment.json", {"schemaVersion": 1})

    app_shot = run_dir / "actual" / "app.png"
    make_png(app_shot, BASELINE_SIZE)
    write_json(run_dir / "diff" / "full-page.json", {
        "schemaVersion": 1, "reference": str(baseline), "actual": str(app_shot),
        "status": "fail", "changedRatio": 0.4,
    })
    return run_dir


def run_validator(run_dir, source=None):
    out = run_dir / f"{run_dir.name}-validate.json"
    args = [sys.executable, str(SCRIPT), "--run", str(run_dir), "--json", str(out)]
    for root in source or []:
        args += ["--source", str(root)]
    proc = subprocess.run(args, capture_output=True, text=True)
    return proc.returncode, json.loads(out.read_text())


def layout_proportions_plan(relation_overrides=None):
    """一份声明了 layoutProportions 的实现计划（合规基线，**两轴口径**）。

    四条关系刻意各占一类 —— ``pinned``（贴父边闭合）、``proportional``（位置随父容器）、
    ``fixed``（设计稿给的封闭值）、``pinned``（尺寸两侧闭合）。run 级闸门要验的是
    「计划声明了什么、源码有没有照它声明的方式实现」这条链路；只摆一条比例会把另外
    三类整条放空，那才是这条红线最容易失效的地方。

    ``parentIndex`` 为 ``None`` 且 ``basis`` 为 ``viewport``：这个区域的直接父视图**就是**
    整屏画布，所以位置基准写 ``root`` 是对的（不是「层级信息丢了」）。
    """
    relations = [
        {"id": "Card.x", "kind": "pinned", "axis": "x", "of": "root",
         "edges": ["leading"], "inset": 16.0},
        {"id": "Card.y", "kind": "proportional", "axis": "y", "of": "root",
         "ratio": 0.839817},
        {"id": "Card.width", "kind": "pinned", "axis": "width", "of": "root",
         "edges": ["leading", "trailing"],
         "insets": {"leading": 16.0, "trailing": 16.0}},
        {"id": "Card.height", "kind": "fixed", "axis": "height", "of": "root",
         "value": 68.0},
    ]
    if relation_overrides:
        relations = relation_overrides(relations)
    region = {
        "region": "Card", "index": 1, "parentIndex": None, "parent": "root",
        "basis": "viewport", "kindSource": "proposed",
        "ratios": {"xRatio": 0.039801, "yRatio": 0.839817, "widthRatio": 0.898010,
                   "heightRatio": 0.077803, "centerXRatio": 0.488806,
                   "centerYRatio": 0.878720},
        "relations": relations, "nativeIdiom": [],
    }
    return {
        "schemaVersion": 1,
        "layoutProportions": {
            "model": "fixed-size-parent-relative-position",
            "basis": "viewport", "axisPolicy": "per-axis",
            "basisSize": {"width": 402, "height": 874},
            "regions": [region],
            # 734pt 是 Card.top 在探针设备（402x874）上的绝对坐标：只在那一台上成立。
            "forbiddenLiterals": [
                {"relation": "Card.top", "deviceDerivedPt": 734.0,
                 "why": "探针设备 402x874 上的绝对值，换台设备即失效",
                 "ratioInstead": 0.839817}],
        },
    }


ANCHOR_NAME = {"x": {"leading": "leadingAnchor", "trailing": "trailingAnchor"},
               "y": {"leading": "topAnchor", "trailing": "bottomAnchor"},
               # 尺寸轴的 pinned 同样是「两侧各自闭合」，锚点名与位置轴一致。
               "width": {"leading": "leadingAnchor", "trailing": "trailingAnchor"},
               "height": {"leading": "topAnchor", "trailing": "bottomAnchor"}}


def compliant_source(plan):
    """按计划生成一份合规的 Objective-C 源码：每一类按它自己的写法表达。

    **源码由计划生成，不是两处各手写一份。** 手写的那份迟早会和计划错开，而错开之后
    用例20 的绿灯就只剩「脚本跑得动」—— 正好验不到本文件要验的那条链路。每一行都以
    ``// <关系 id>`` 收尾，好让用例21 能精确定位到要变异的那一行。

    * ``proportional`` → ``multiplier``；
    * ``pinned`` → ``constraintEqualTo:<父视图锚点> constant:<内边距>``；
    * ``fixed`` → ``constraintEqualToConstant:<设计值>``；
    * ``centered`` → 对齐父视图中心锚点；
    * ``intrinsic`` → 不加尺寸约束（注释说明 why）。
    """
    lines = ["// 由 layoutProportions 生成：尺寸写设计常量、位置相对直接父视图",
             "static void buildLayout(UIView *root) {",
             "  [root layoutIfNeeded];"]
    for region in plan["layoutProportions"]["regions"]:
        name = region["region"]
        for rel in region["relations"]:
            base = rel.get("of") or "root"
            kind, axis = rel["kind"], rel["axis"]
            if kind == "proportional":
                anchor = {"width": "widthAnchor", "height": "heightAnchor",
                          "x": "leadingAnchor", "y": "topAnchor"}[axis]
                line = (f"  [[self {name}] {anchor} constraintEqualTo:{base}.{anchor} "
                        f"multiplier:{rel['ratio']}];  // {rel['id']}")
            elif kind == "pinned":
                for edge in rel.get("edges") or [rel.get("edge")]:
                    anchor = ANCHOR_NAME[axis][edge]
                    inset = (rel.get("insets") or {}).get(edge, rel.get("inset", 0.0))
                    lines.append(f"  [[self {name}] {anchor} constraintEqualTo:"
                                 f"{base}.{anchor} constant:{inset:g}];  // {rel['id']}")
                continue
            elif kind == "fixed":
                dim = "widthAnchor" if axis == "width" else "heightAnchor"
                line = (f"  [[self {name}] {dim} constraintEqualToConstant:"
                        f"{rel['value']:g}];  // {rel['id']}")
            elif kind == "centered":
                side = "X" if axis == "x" else "Y"
                line = (f"  [[self {name}] center{side}Anchor constraintEqualTo:"
                        f"{base}.center{side}Anchor];  // {rel['id']}")
            else:
                line = f"  // {rel['id']} 内容撑开，不加尺寸约束：{rel.get('why', '')}"
            lines.append(line)
    lines.append("}")
    return "\n".join(lines) + "\n"


def relation_line(source, relation_id):
    """合规源码里某个关系对应的行（返回 行号, 行文本）；找不到返回 ``(None, None)``。

    必须在**变异之前**取行号：变异后那一行的内容变了，再按内容去找只会落到另一条
    同类行上，报出来的位置是错的。找不到时返回 ``None`` 而不是抛异常 —— 测试里抛栈
    会以「崩栈」的形式变红，而那是退出码非 0 得到的红，要守的断言一次都没执行。
    """
    for number, line in enumerate(source.splitlines(), start=1):
        if line.rstrip().endswith(f"// {relation_id}"):
            return number, line
    return None, None


def write_source(tmp, name, body):
    source = tmp / name
    source.mkdir(parents=True, exist_ok=True)
    (source / "CardLayout.m").write_text(body)
    return source


def write_page_facts(run_dir, elements, browser_meta=None):
    """把页面级字体事实写进 reference/，并可选写入 browser-meta。"""
    reference = run_dir.parent.parent / "reference"
    write_json(reference / "page-facts.json", {"schemaVersion": 3, "elements": elements})
    if browser_meta is not None:
        write_json(reference / "browser-meta.json", browser_meta)


def text_element(index, declared, resolved, text="label"):
    """一个文本元素：CSS 声明的族 vs 运行时实际用上的族。"""
    return {
        "index": index, "tag": "span", "ownsText": True, "ownText": text,
        "fontFamily": declared,
        "primaryFont": {"family": resolved, "glyphCount": 8, "isCustomFont": False},
    }


JOIN_OK_META = {"fontMeasurement": {"ok": True},
                "fontJoin": {"ok": True, "textMarkMismatchCount": 0}}


def comparator_summary(run_dir, **overrides):
    """一份 schema v2 的像素比较结论，默认完全合规（供用例做阳性对照）。"""
    payload = {
        "schemaVersion": 2,
        "reference": str(run_dir.parent.parent / "reference" / "reference.png"),
        "actual": str(run_dir / "actual" / "app.png"),
        "status": "pass",
        "changedRatio": 0.021,
        "structuralRatio": 0.001,
        "textureRatio": 0.020,
        "fillRatio": 0.0,
        "warnStructuralRatio": 0.005,
        "maxStructuralRatio": 0.02,
        "maxFillRatio": 0.02,
        "regions": [{
            "row": 0, "col": 0, "pixels": 20000, "changedPixels": 420,
            "box": {"x": 0, "y": 0, "width": 100, "height": 200},
            "changedRatio": 0.021, "structuralRatio": 0.001,
            "textureRatio": 0.020, "fillRatio": 0.0,
        }],
    }
    payload.update(overrides)
    return payload


def reachability_plan(floor=0.05, unavoidable="default"):
    """一份声明了 ``gateReachability`` 的实现计划。

    文字密集页的结构差异存在物理下界（基准图在 scale(1.0229) 的画布上渲染，而尺寸契约
    禁止按比例缩放字号），所以计划要显式声明它。``unavoidable`` 是**可核性**的关键：
    下界必须说明「为什么不可消除」并给出实测占比，否则就是自己给自己发豁免。
    """
    if unavoidable == "default":
        unavoidable = [{
            "category": "typography",
            "cause": "baseline-scale-vs-fixed-font-size",
            "measuredShare": 0.01563,
            "why": "基准字形 = 设计字号 x 1.0229，而契约禁止按比例缩放字号",
        }]
    return {
        "schemaVersion": 1,
        "gateReachability": {"expectedStructuralFloor": floor,
                             "unavoidable": unavoidable},
    }


def reachability_summary(run_dir, **overrides):
    """一份「结构差异落在声明下界内」的放行结论。"""
    payload = comparator_summary(
        run_dir,
        status="pass-with-review",
        reason="structural-within-declared-floor",
        structuralRatio=0.03,
        maxStructuralRatio=0.02,
        expectedStructuralFloor=0.05,
        expectedStructuralFloorSource="plan",
        declaredStructuralFloor={"value": 0.05, "source": "plan",
                                 "maxStructuralRatio": 0.02, "withinFloor": True,
                                 "headroom": 0.02},
    )
    payload.update(overrides)
    return payload


def alignment_summary(run_dir, status="aligned", reason=None):
    """一份元素级对齐审计结论。"""
    payload = {
        "schemaVersion": 2,
        "runId": run_dir.name,
        "status": status,
        "comparisons": {
            "domVsReference": {"label": "domVsReference", "status": "aligned"},
            "referenceVsActual": {"label": "referenceVsActual",
                                  "status": status, "reason": reason},
        },
    }
    return payload


def adaptive_plan():
    """一份合规的宽度轴声明（四个采样覆盖三个宽度档）。"""
    return {
        "schemaVersion": 1,
        "adaptiveLayout": {
            "model": "continuous-window-width",
            "windowSamples": [
                {"id": "phone-compact", "widthClass": "compact",
                 "width": 393, "height": 852},
                {"id": "tablet-regular-portrait", "widthClass": "medium",
                 "width": 1024, "height": 1366},
                {"id": "tablet-regular-landscape", "widthClass": "expanded",
                 "width": 1366, "height": 1024},
                {"id": "phone-regular-landscape", "widthClass": "medium",
                 "width": 852, "height": 393, "required": False},
            ],
            "firstLevelWidthClass": "compact",
            "regions": [{"region": "form", "widthPolicy": "max-content-width",
                         "maxContentWidth": {"value": 600, "of": "root",
                                             "reason": "单列表单拉满会破坏阅读节奏"}}],
            "forbiddenAdaptations": ["uniform-scale", "stretch-full-width", "font-scale"],
        },
    }


def adaptive_targets():
    return {"schemaVersion": 1, "platform": "iOS Simulator", "deviceFamily": "1,2",
            "samples": [{"id": "phone-compact", "widthClass": "compact", "required": True,
                         "geometry": "actual/geometry-phone-compact.json"}]}


def adaptive_audit_report(status="pass"):
    return {"schemaVersion": 1, "model": "continuous-window-width", "status": status,
            "tolerancePt": 2.0, "checks": {}, "violations": [], "warnings": []}


def main():
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # 用例 1：完整合规的 run 必须通过
        code, data = run_validator(make_run(tmp, "20260101-000000-objc-001", delivery_ready=True))
        if code != 0 or not data["ok"]:
            problems.append(f"用例1：合规 run 被判不合规：{data['violations']}")

        # 用例 2：缺文件必须被指出
        missing = make_run(tmp, "20260101-000000-objc-002", delivery_ready=True)
        (missing / "runtime-device.json").unlink()
        code, data = run_validator(missing)
        if code == 0 or not any("runtime-device.json" in v for v in data["violations"]):
            problems.append("用例2：缺少 runtime-device.json 未被识别")

        # 用例 3：visualDiff=fail 却写 deliveryReady=true 必须被识别为篡改
        tampered = make_run(tmp, "20260101-000000-objc-003",
                            gate_status={**GATE_PASS, "visualDiff": "fail"}, delivery_ready=True)
        code, data = run_validator(tampered)
        if code == 0 or not any("deliveryReady" in v for v in data["violations"]):
            problems.append("用例3：deliveryReady 与闸门状态矛盾未被识别")

        # 用例 4：legacy run 跳过产物必需项
        legacy = tmp / "pages" / "demo" / "runs" / "20260101-000000-objc-004"
        legacy.mkdir(parents=True)
        write_json(legacy / "run.json", {
            "schemaVersion": 1, "runId": legacy.name, "pageId": "demo",
            "targetMode": "ios-uikit-objective-c", "parentRunId": None,
            "referenceBaseline": {"approved": None, "sha256": None},
            "status": "needs-review", "legacy": True,
        })
        code, data = run_validator(legacy)
        if code != 0 or not data.get("legacy"):
            problems.append(f"用例4：legacy run 未被豁免：{data.get('violations')}")

        # 用例 5：Android 模式不得要求 ios-environment.json
        code, data = run_validator(make_run(tmp, "20260101-000000-android-005",
                                            target_mode="android-compose-kotlin", delivery_ready=True))
        if code != 0:
            problems.append(f"用例5：Android run 被错误要求 iOS 产物：{data['violations']}")

        # 用例 6：基准图与设备截图尺寸不同源必须被识别
        mismatch = make_run(tmp, "20260101-000000-objc-006", delivery_ready=True,
                            baseline_size=(100, 200), device_size=(120, 260))
        code, data = run_validator(mismatch)
        if code == 0 or not any("不同源" in v for v in data["violations"]):
            problems.append("用例6：基准图与设备截图不同源未被识别")

        # 用例 7：diff 使用降采样派生图必须被识别
        derived = make_run(tmp, "20260101-000000-objc-007", delivery_ready=True)
        summary_path = derived / "diff" / "full-page.json"
        summary = json.loads(summary_path.read_text())
        summary["actual"] = str(derived / "actual" / "app-reference-size.png")
        write_json(summary_path, summary)
        code, data = run_validator(derived)
        if code == 0 or not any("派生图" in v for v in data["violations"]):
            problems.append("用例7：diff 使用派生图未被识别")

        # 用例 8：diff 的 reference 不是已批准基准必须被识别
        wrong_ref = make_run(tmp, "20260101-000000-objc-008", delivery_ready=True)
        summary_path = wrong_ref / "diff" / "full-page.json"
        summary = json.loads(summary_path.read_text())
        summary["reference"] = str(wrong_ref / "actual" / "app.png")
        write_json(summary_path, summary)
        code, data = run_validator(wrong_ref)
        if code == 0 or not any("不是已批准基准" in v for v in data["violations"]):
            problems.append("用例8：diff 未使用已批准基准未被识别")

        # 用例 9：比较结论判 pass 却不给结构差异/区域明细必须被识别。
        # 「整页数值在容差内」证明不了「各处都在容差内」—— 这正是那次事故的核心。
        thin = make_run(tmp, "20260101-000000-objc-009", delivery_ready=True)
        summary = comparator_summary(thin)
        summary.pop("structuralRatio")
        summary.pop("regions")
        write_json(thin / "diff" / "comparison.json", summary)
        code, data = run_validator(thin)
        if code == 0 or not any("structuralRatio" in v for v in data["violations"]):
            problems.append("用例9：pass 却没有结构差异证据未被识别")
        if not any("regions" in v for v in data["violations"]):
            problems.append("用例9：pass 却没有区域级明细未被识别")

        # 用例 10：整页达标、但某个区域的结构差异超上限必须被识别
        region = make_run(tmp, "20260101-000000-objc-010", delivery_ready=True)
        summary = comparator_summary(region)
        summary["regions"][0]["structuralRatio"] = 0.09   # 局部 9%，远超上限 2%
        write_json(region / "diff" / "comparison.json", summary)
        code, data = run_validator(region)
        if code == 0 or not any("区域" in v and "超过上限" in v for v in data["violations"]):
            problems.append("用例10：整页达标但区域超限未被识别")

        # 用例 11：对齐审计判 needs-review，闸门却是 pass 必须被识别
        conflict = make_run(tmp, "20260101-000000-objc-011", delivery_ready=True)
        write_json(conflict / "diff" / "comparison.json", comparator_summary(conflict))
        write_json(conflict / "diff" / "alignment.json",
                   alignment_summary(conflict, "needs-review", "constant-offset"))
        code, data = run_validator(conflict)
        if code == 0 or not any("needs-review" in v and "visualDiff" in v
                                for v in data["violations"]):
            problems.append("用例11：审计 needs-review 而闸门 pass 未被识别")

        # 用例 11b：闸门同时是 fail 时不该重复报错（避免误报）
        consistent = make_run(tmp, "20260101-000000-objc-012",
                              gate_status={**GATE_PASS, "visualDiff": "fail"})
        write_json(consistent / "diff" / "comparison.json", comparator_summary(consistent))
        write_json(consistent / "diff" / "alignment.json",
                   alignment_summary(consistent, "needs-review", "constant-offset"))
        code, data = run_validator(consistent)
        if any("needs-review" in v and "visualDiff" in v for v in data["violations"]):
            problems.append("用例11b：闸门已判 fail 时仍重复报错")

        # 用例 12：带区域证据的比较结论 + 对齐审计一致，必须判合规（阳性对照）
        ok_run = make_run(tmp, "20260101-000000-objc-013", delivery_ready=True)
        write_json(ok_run / "diff" / "comparison.json", comparator_summary(ok_run))
        write_json(ok_run / "diff" / "alignment.json", alignment_summary(ok_run))
        code, data = run_validator(ok_run)
        if code != 0 or not data["ok"]:
            problems.append(f"用例12：带区域证据与对齐审计的合规 run 被判不合规："
                            f"{data['violations']}")
        if any("alignment.json" in w for w in data["warnings"]):
            problems.append("用例12：已提供 alignment.json 却仍告警缺失")

        # 用例 13：缺 alignment.json 只应是告警（不阻塞），但必须提示
        no_audit = make_run(tmp, "20260101-000000-objc-014", delivery_ready=True)
        write_json(no_audit / "diff" / "comparison.json", comparator_summary(no_audit))
        code, data = run_validator(no_audit)
        if code != 0 or not any("alignment.json" in w for w in data["warnings"]):
            problems.append("用例13：缺少对齐审计未给出告警")

        # ---- 布局约束契约：尺寸是常量、位置相对直接父视图 ----
        plan_payload = layout_proportions_plan()
        ok_source = compliant_source(plan_payload)

        # 用例 20：计划声明的四类关系，源码逐条照做 → 合规（阳性对照）
        ok_layout = make_run(tmp, "20260101-000000-objc-015", delivery_ready=True)
        write_json(ok_layout / "ui-implementation-plan.json", plan_payload)
        write_json(ok_layout / "diff" / "comparison.json", comparator_summary(ok_layout))
        write_json(ok_layout / "diff" / "alignment.json", alignment_summary(ok_layout))
        compliant = write_source(tmp, "src-compliant", ok_source)
        code, data = run_validator(ok_layout, source=[compliant])
        if code != 0 or not data["ok"]:
            problems.append(f"用例20：照计划声明的方式实现的源码被判不合规：{data['violations']}")

        # 用例 21：同一份计划，把那条比例换成设备推导值 → 必须拦下。
        # 这是变异探针：没有它，「用例20 通过」只说明脚本跑得动。
        target_item = next((f for f in plan_payload["layoutProportions"]["forbiddenLiterals"]
                            if abs(f["deviceDerivedPt"]) > 48), None)
        line_number, target_line = relation_line(ok_source, "Card.y")
        if target_item is None or line_number is None:
            problems.append("用例21：探针前提不成立 —— 计划里应有一条可变异的大数值比例关系")
        else:
            # 把整条约束换成「写死探针设备上的绝对值」，位置仍留在同一行，
            # 好让违规的行号能对上。
            mutated_line = target_line.split("constraintEqualTo")[0] + (
                f"constraintEqualToConstant:{target_item['deviceDerivedPt']:g}];  // Card.y")
            mutated_source = ok_source.replace(target_line, mutated_line, 1)
            if mutated_source == ok_source:
                problems.append("用例21：变异没有生效，探针无效")
            else:
                bad_layout = make_run(tmp, "20260101-000000-objc-016", delivery_ready=True)
                write_json(bad_layout / "ui-implementation-plan.json", plan_payload)
                write_json(bad_layout / "diff" / "comparison.json", comparator_summary(bad_layout))
                write_json(bad_layout / "diff" / "alignment.json", alignment_summary(bad_layout))
                absolute = write_source(tmp, "src-absolute", mutated_source)
                code, data = run_validator(bad_layout, source=[absolute])
                if code == 0:
                    problems.append("用例21：把比例写成设备推导值未被拦下")
                if not any("布局约束" in v and "734" in v for v in data["violations"]):
                    problems.append(f"用例21：违规未指出是哪个设备推导值：{data['violations']}")
                if not any(f"[CardLayout.m:{line_number}]" in v
                           for v in data["violations"]):
                    problems.append(f"用例21：违规未定位到第 {line_number} 行："
                                    f"{data['violations']}")
                if not any("implementation" in v for v in data["violations"]):
                    problems.append("用例21：源码未按计划声明的方式实现时 "
                                    "implementation 闸门不得为 pass")

        # 用例 22：没给 --source 时只告警，不能假装验证过
        unverified = make_run(tmp, "20260101-000000-objc-017", delivery_ready=True)
        write_json(unverified / "ui-implementation-plan.json", plan_payload)
        write_json(unverified / "diff" / "comparison.json", comparator_summary(unverified))
        write_json(unverified / "diff" / "alignment.json", alignment_summary(unverified))
        code, data = run_validator(unverified)
        if code != 0:
            problems.append(f"用例22：未给 --source 不该硬判失败：{data['violations']}")
        if not any("--source" in w for w in data["warnings"]):
            problems.append("用例22：未提供源码时应告警说明「尚未验证」")

        # 用例 23：计划没声明 layoutProportions → 告警（legacy run 不能被判死）
        legacy_plan = make_run(tmp, "20260101-000000-objc-018", delivery_ready=True)
        write_json(legacy_plan / "diff" / "comparison.json", comparator_summary(legacy_plan))
        write_json(legacy_plan / "diff" / "alignment.json", alignment_summary(legacy_plan))
        code, data = run_validator(legacy_plan)
        if code != 0 or not any("layoutProportions" in w for w in data["warnings"]):
            problems.append(f"用例23：计划未声明布局约束应告警，得到 {code} / {data['warnings']}")

        # 用例 24：计划里 kind 非法 / intrinsic 缺 why → 必须硬判
        broken_plan = make_run(tmp, "20260101-000000-objc-019", delivery_ready=True)
        write_json(broken_plan / "ui-implementation-plan.json", layout_proportions_plan(
            relation_overrides=lambda rels: rels + [
                {"id": "Card.bad", "kind": "absolute", "ratio": 0.5},
                {"id": "Card.why", "kind": "intrinsic"}]))
        write_json(broken_plan / "diff" / "comparison.json", comparator_summary(broken_plan))
        code, data = run_validator(broken_plan)
        if code == 0 or not any("unknown-relation-kind" in v or "intrinsic-missing-why" in v
                                for v in data["violations"]):
            problems.append(f"用例24：计划本身不合规未被拦下：{data['violations']}")

        # 用例 25：已落盘的布局结论判 fail，闸门却是 pass → 自相矛盾（与对齐审计同类）
        contradicted = make_run(tmp, "20260101-000000-objc-020", delivery_ready=True)
        write_json(contradicted / "ui-implementation-plan.json", plan_payload)
        write_json(contradicted / "diff" / "comparison.json", comparator_summary(contradicted))
        write_json(contradicted / "diff" / "alignment.json", alignment_summary(contradicted))
        write_json(contradicted / "diff" / "layout-proportions.json",
                   {"status": "fail", "violations": [{"kind": "no-proportional-idiom"}]})
        code, data = run_validator(contradicted)
        if code == 0 or not any("layout-proportions.json" in v and "implementation" in v
                                for v in data["violations"]):
            problems.append(f"用例25：布局约束结论 fail 而闸门 pass 未被识别：{data['violations']}")

        # ---- 基准字体链：声明的字体族有没有真的用上 ----
        # 素材：声明 AvenirLT-Black、运行时回落到 Times，外加一个解析正确的对照组。
        # 注意每个用例一个独立页面（page=...）：页面级的 page-facts.json 被同页面下
        # 所有 run 共享，共用页面会让这些用例互相污染。
        def substituted_run(run_id, page, **kwargs):
            run = make_run(tmp, run_id, page=page, **kwargs)
            write_page_facts(run, [
                text_element(3, "AvenirLT-Black", "Times", "Choose Your Plan"),
                text_element(9, "PingFang SC", "PingFang SC", "Try For Free"),
            ], JOIN_OK_META)
            return run

        # 用例 26：基准字体被静默替换，reference 闸门却是 pass → 必须拦下
        bad_fonts = substituted_run("20260101-000000-objc-021", "fonts-substituted",
                                    delivery_ready=True)
        code, data = run_validator(bad_fonts)
        if code == 0:
            problems.append("用例26：基准字体链断了却仍判合规")
        if not any("AvenirLT-Black" in v and "Times" in v for v in data["violations"]):
            problems.append(f"用例26：违规未点名「声明的族 → 实际用上的族」：{data['violations']}")
        if not any("reference" in v for v in data["violations"]):
            problems.append("用例26：未指出 reference 闸门与字体链结论矛盾")

        # 用例 27：闸门已诚实记成非 pass → 不重复报错（避免误报）
        honest = substituted_run("20260101-000000-objc-022", "fonts-acknowledged",
                                 gate_status={**GATE_PASS, "reference": "fail"})
        code, data = run_validator(honest)
        if code != 0:
            problems.append(f"用例27：闸门已判 fail 时重复报错：{data['violations']}")
        if not any("AvenirLT-Black" in w for w in data["warnings"]):
            problems.append("用例27：闸门已判 fail 时缺少提示，字体问题被静默")

        # 用例 28：事实表没做过字体测量 → 只告警，不硬判（旧 schema 不能被判死）
        unmeasured = make_run(tmp, "20260101-000000-objc-023", page="fonts-unmeasured",
                              delivery_ready=True)
        write_page_facts(unmeasured, [
            {"index": 1, "tag": "span", "ownsText": True, "ownText": "x",
             "style": {"fontFamily": "AvenirLT-Black"}},
        ], JOIN_OK_META)
        code, data = run_validator(unmeasured)
        if code != 0:
            problems.append(f"用例28：证据不足却硬判失败：{data['violations']}")
        if not any("无法判定" in w for w in data["warnings"]):
            problems.append("用例28：未告警说明基准字体链无法判定")

        # 用例 29：完全没有页面级事实表 → 只告警
        no_facts = make_run(tmp, "20260101-000000-objc-024", page="fonts-missing",
                            delivery_ready=True)
        code, data = run_validator(no_facts)
        if code != 0:
            problems.append(f"用例29：缺少 page-facts 却硬判失败：{data['violations']}")
        if not any("page-facts" in w for w in data["warnings"]):
            problems.append("用例29：缺少页面级事实表时未告警")

        # 用例 30：落盘的 font-chain.json 与闸门矛盾 → 与现算同等地被识别
        disk_conflict = make_run(tmp, "20260101-000000-objc-025", page="fonts-disk",
                                 delivery_ready=True)
        write_json(disk_conflict / "diff" / "font-chain.json", {
            "status": "substituted", "substituted": True,
            "missingFamilies": ["AvenirLT-Black"], "landedFamilies": ["Times"],
            "affectedElements": [{"index": 3}],
        })
        code, data = run_validator(disk_conflict)
        if code == 0 or not any("Times" in v for v in data["violations"]):
            problems.append(f"用例30：落盘的字体链结论与闸门矛盾未被识别：{data['violations']}")

        # 用例 31：legacy run 跳过产物必需项，但**不得**顺带跳过字体链 ——
        # run 011 那次事故的 run.json 就是 legacy，漏掉它等于把这条红线放空。
        legacy_fonts = make_run(tmp, "20260101-000000-objc-026", page="fonts-legacy",
                                legacy=True)
        write_page_facts(legacy_fonts, [
            text_element(3, "AvenirLT-Black", "Times", "Choose Your Plan"),
        ], JOIN_OK_META)
        code, data = run_validator(legacy_fonts)
        if code != 0 or not data.get("legacy"):
            problems.append(f"用例31：legacy run 不该被硬判：{data['violations']}")
        if not any("AvenirLT-Black" in w and "Times" in w for w in data["warnings"]):
            problems.append("用例31：legacy run 跳过了字体链核对，基准字体问题被静默")

        # 用例 32：旧 schema 的 delivery-gate.status 是字符串 → 必须报结构不对，
        # 不得抛栈（真实 run 005 就是这种形态）。校验器崩掉等于什么都没校验。
        legacy_gate = make_run(tmp, "20260101-000000-objc-027", page="fonts-legacy-gate",
                               delivery_ready=False)
        write_json(legacy_gate / "delivery-gate.json", {
            "deliveryReady": False, "status": "pass-with-review",
            "build": "passed", "test": "not-run", "visual": "needs-review",
        })
        try:
            code, data = run_validator(legacy_gate)
        except Exception as exc:                      # noqa: BLE001 - 崩了就是失败
            problems.append(f"用例32：字符串 status 让校验器抛栈：{type(exc).__name__}: {exc}")
        else:
            if code == 0:
                problems.append("用例32：status 结构不对却判合规")
            if not any("delivery-gate.status" in v for v in data["violations"]):
                problems.append(f"用例32：未报出 status 结构不对：{data['violations'][:2]}")

        # 用例 33：unsupported 计数对象缺失时**不得**推导 delivery-ready。
        # 原先写的是 `gate.get('unsupported') or {}`，缺字段时 count 与 reviewedCount 同为
        # None、彼此相等，于是推导出 True —— 校验器接着报「记录 false，应为 true」，等于要求
        # Agent 把「没做人工复核」改写成「可以交付」。
        # 闸门这里如实记 false（不知情时不打包票），正是最容易被那条错误指正带偏的形态；
        # 若记 true，旧逻辑恰好与之一致，反而看不出问题。
        no_unsupported = make_run(tmp, "20260101-000000-objc-028",
                                  page="gate-no-unsupported", delivery_ready=False)
        write_json(no_unsupported / "delivery-gate.json",
                   {"deliveryReady": False, "status": dict(GATE_PASS),
                    "blockingReasons": ["unsupported 计数对象缺失"]})
        code, data = run_validator(no_unsupported)
        if code == 0:
            problems.append("用例33：unsupported 计数对象缺失却判合规")
        if not any("unsupported" in v for v in data["violations"]):
            problems.append(f"用例33：未报出 unsupported 缺失：{data['violations'][:2]}")
        if any("应为 True" in v for v in data["violations"]):
            problems.append("用例33：把「没做人工复核」推导成了可交付，还要求 Agent 照抄")
        if not any("跳过一致性核对" in w for w in data["warnings"]):
            problems.append("用例33：跳过一致性核对没留痕（静默即不可追溯）")

        # 用例 34：计数写成字符串同样推不出来 —— 「看起来有数」不是证据。
        # （'2' == '2' 为真，旧写法会把字符串计数判成复核完毕。）
        string_counts = make_run(tmp, "20260101-000000-objc-029",
                                 page="gate-string-counts", delivery_ready=False)
        write_json(string_counts / "delivery-gate.json",
                   {"deliveryReady": False, "status": dict(GATE_PASS),
                    "unsupported": {"count": "2", "reviewedCount": "2"},
                    "blockingReasons": ["unsupported 未复核完"]})
        code, data = run_validator(string_counts)
        if code == 0:
            problems.append("用例34：计数为字符串却判合规")
        if not any("必须是整数" in v for v in data["violations"]):
            problems.append(f"用例34：未报出计数类型不对：{data['violations'][:2]}")
        if any("deliveryReady 与契约推导不一致" in v for v in data["violations"]):
            problems.append("用例34：结构不可读时仍给出了推导值")

        # 用例 35：阳性对照 —— 复核真的做完时必须照旧判可交付，免得加固把正常路径一起拦掉
        # （拦过头的校验器会变成恒挂，同样没有价值）。
        reviewed = make_run(tmp, "20260101-000000-objc-030",
                            page="gate-reviewed", delivery_ready=True)
        write_json(reviewed / "delivery-gate.json",
                   {"deliveryReady": True, "status": dict(GATE_PASS),
                    "unsupported": {"count": 3, "reviewedCount": 3}})
        code, data = run_validator(reviewed)
        if code != 0:
            problems.append(f"用例35：复核做完的正常 run 被判不合规：{data['violations'][:2]}")
        # 同一份闸门，只漏一项复核 → 必须变红。否则上面那条绿灯证明不了什么。
        half = make_run(tmp, "20260101-000000-objc-031",
                        page="gate-half-reviewed", delivery_ready=True)
        write_json(half / "delivery-gate.json",
                   {"deliveryReady": True, "status": dict(GATE_PASS),
                    "unsupported": {"count": 3, "reviewedCount": 2}})
        code, data = run_validator(half)
        if code == 0 or not any("应为 False" in v for v in data["violations"]):
            problems.append(f"用例35：漏一项复核仍被判可交付：{data['violations'][:2]}")

        # 用例 36：声明的结构差异下界 —— 合规放行必须通过（阳性对照）。
        # 文字密集页的结构差异存在物理下界，把它声明出来并做量化归因是**正确**的交付形态；
        # 校验器如果把这条正常路径也拦下，就会逼着 Agent 去追一个不存在的 0。
        lifted = make_run(tmp, "20260101-000000-objc-032", page="reachability-ok",
                          delivery_ready=True)
        write_json(lifted / "ui-implementation-plan.json", reachability_plan())
        write_json(lifted / "diff" / "full-page.json", reachability_summary(lifted))
        code, data = run_validator(lifted)
        if code != 0:
            problems.append(f"用例36：下界内的合规放行被判不合规：{data['violations'][:2]}")

        # 用例 36b：下界放行时，区域级结构差异不得被死卡 0.02 误杀。
        # 下界声明的物理根源（emoji 栅格化 + 字重轮廓 + 2.29% 字号差）**遍布整页**，
        # 不是局部几何错位，所以只要整页落在下界内、reason 是 structural-within-declared-floor，
        # 区域级就不该逐格拿 0.02 复核（否则下界放行在整页成立、在区域级又被同一个
        # 物理原因推翻，自相矛盾）。真正需要区域级卡点的是 pass（整页压到 0.02 内却
        # 可能藏着局部错位）。
        region_lifted = make_run(tmp, "20260101-000000-objc-032b", page="reachability-region",
                                 delivery_ready=True)
        write_json(region_lifted / "ui-implementation-plan.json", reachability_plan())
        region_summary = reachability_summary(region_lifted)
        region_summary["regions"][0]["structuralRatio"] = 0.06  # 区域 6%，超 0.02
        write_json(region_lifted / "diff" / "full-page.json", region_summary)
        _code2, data2 = run_validator(region_lifted)
        if any("超过上限" in v and "区域" in v for v in data2["violations"]):
            problems.append("用例36b：下界放行却被区域级死卡 0.02 误杀")

        # 用例 37：下界必须可核 —— 七种形态各自必须变红。
        # 只做阳性对照是不够的：一个永远不报错的校验器同样能让用例 36 变绿。
        bad = make_run(tmp, "20260101-000000-objc-033", page="reachability-bad",
                       delivery_ready=True)
        bad_summary = bad / "diff" / "full-page.json"
        bad_plan = bad / "ui-implementation-plan.json"

        def violations_for(plan_doc, summary_doc):
            write_json(bad_plan, plan_doc)
            write_json(bad_summary, summary_doc)
            _code, payload = run_validator(bad)
            return payload["violations"]

        reachability_cases = [
            ("计划没声明 gateReachability 却以下界放行",
             {"schemaVersion": 1}, reachability_summary(bad), "没有 gateReachability"),
            ("gateReachability 的 unavoidable 为空",
             reachability_plan(unavoidable=[]), reachability_summary(bad), "unavoidable"),
            ("unavoidable 缺 measuredShare",
             reachability_plan(unavoidable=[{"category": "typography",
                                             "cause": "baseline-scale-vs-fixed-font-size"}]),
             reachability_summary(bad), "measuredShare"),
            # 下界要比对的是「比较结论实际用的那个下界」，所以 summary 必须带上计划里的值 ——
            # 只改计划、summary 仍写着 0.05，就不是这条用例要测的形态。
            ("实际值超过声明的下界却仍放行",
             reachability_plan(floor=0.02),
             reachability_summary(bad, expectedStructuralFloor=0.02), "超过声明的下界"),
            ("声明的下界低于上限",
             reachability_plan(floor=0.01),
             reachability_summary(bad, expectedStructuralFloor=0.01),
             "小于 maxStructuralRatio"),
            ("计划声明了下界却把下界内的值判 fail",
             reachability_plan(),
             reachability_summary(bad, status="fail", reason="structural-diff-exceeded"),
             "声明白写了"),
            ("计划声明了下界但比较结论没带 expectedStructuralFloor",
             reachability_plan(),
             reachability_summary(bad, expectedStructuralFloor=None,
                                  expectedStructuralFloorSource=None),
             "没有 expectedStructuralFloor"),
        ]
        for label, plan_doc, summary_doc, needle in reachability_cases:
            violations = violations_for(plan_doc, summary_doc)
            if not any(needle in v for v in violations):
                problems.append(
                    f"用例37/{label}：未报出（找 {needle!r}），实得 {violations[:2]}")

        # 用例 38：闸门记 pass 时，比较结论必须真的支持它 —— 两个方向都要拦。
        # 只拦「比较器判 fail 却记 pass」是不够的：那会让「下界内放行」变成把一切
        # pass-with-review 都吞掉的借口，deliveryReady 随之失去意义。
        gatecase = make_run(tmp, "20260101-000000-objc-034", page="visual-gate",
                            delivery_ready=True)
        gate_path = gatecase / "diff" / "full-page.json"
        gate_plan = gatecase / "ui-implementation-plan.json"

        def gate_violations(summary_doc, visual_diff="pass", plan_doc=None):
            write_json(gatecase / "delivery-gate.json", {
                "schemaVersion": 1, "runId": gatecase.name,
                "status": {**GATE_PASS, "visualDiff": visual_diff},
                "unsupported": {"count": 0, "reviewedCount": 0, "items": []},
                "deliveryReady": True, "blockingReasons": [],
            })
            if plan_doc is not None:
                write_json(gate_plan, plan_doc)
            write_json(gate_path, summary_doc)
            _code, payload = run_validator(gatecase)
            return payload["violations"]

        # 38a：比较器判 fail，闸门不得记 pass
        violations = gate_violations(
            comparator_summary(gatecase, status="fail", reason="structural-diff-exceeded"))
        if not any("闸门不得记成 pass" in v for v in violations):
            problems.append(f"用例38a：比较器判 fail 而闸门记 pass 未被拦下：{violations[:2]}")

        # 38b：其余 pass-with-review 不得升格为 pass
        violations = gate_violations(
            comparator_summary(gatecase, status="pass-with-review",
                               reason="structural-diff-above-warn"))
        if not any("必须原样记录" in v for v in violations):
            problems.append(f"用例38b：pass-with-review 被升格为 pass 未被拦下：{violations[:2]}")

        # 38c：下界内放行是唯一可升格的情形（阳性对照）
        violations = gate_violations(reachability_summary(gatecase),
                                     plan_doc=reachability_plan())
        if any("visualDiff" in v for v in violations):
            problems.append(f"用例38c：下界内放行被误拦：{violations[:2]}")

        # 38d：不带 structuralRatio 的占位件不是放行依据，不得误报
        violations = gate_violations({"schemaVersion": 1, "status": "fail",
                                      "changedRatio": 0.4})
        if any("visualDiff" in v for v in violations):
            problems.append(f"用例38d：占位件被误判：{violations[:2]}")

        # ---- 用例 39：第八项闸门是**条件必需**的 ----
        # 声明了宽度轴（adaptiveLayout）时多一项 adaptiveAudit；未声明时不要求。
        # 做成条件式是因为「未声明宽度轴」本身是合法状态 —— 它等于明确声明
        # 「本页只交付手机档」。强行要求会让所有手机档 run 凭空多一项 not-run。
        def adaptive_run(run_id, gate_status, delivery_ready, plan_doc, with_targets=True,
                         audit_status=None):
            run_dir = make_run(tmp, run_id, page=f"adaptive-{run_id[-3:]}",
                               gate_status=gate_status, delivery_ready=delivery_ready)
            write_json(run_dir / "ui-implementation-plan.json", plan_doc)
            if with_targets:
                write_json(run_dir / "adaptive-targets.json", adaptive_targets())
            if audit_status is not None:
                write_json(run_dir / "diff" / "adaptive-audit.json",
                           adaptive_audit_report(audit_status))
            return run_validator(run_dir)

        # 39a：声明了宽度轴却没写第八项闸门 —— 少一项最容易伪装成「全绿」
        _code, data = adaptive_run(
            "20260101-000000-objc-039a", dict(GATE_PASS), False, adaptive_plan())
        if not any("adaptiveAudit" in v for v in data["violations"]):
            problems.append(
                f"用例39a：声明宽度轴却缺 adaptiveAudit 未被拦下：{data['violations'][:3]}")

        # 39b：几何审计判 fail，闸门不得记 pass
        _code, data = adaptive_run(
            "20260101-000000-objc-039b",
            {**GATE_PASS, "adaptiveAudit": "pass"}, True, adaptive_plan(),
            audit_status="fail")
        if not any("adaptiveAudit" in v and "pass" in v for v in data["violations"]):
            problems.append(
                f"用例39b：审计判 fail 而闸门记 pass 未被拦下：{data['violations'][:3]}")

        # 39c：阳性对照 —— 声明齐、闸门齐、审计通过，不得误报
        _code, data = adaptive_run(
            "20260101-000000-objc-039c",
            {**GATE_PASS, "adaptiveAudit": "pass"}, True, adaptive_plan(),
            audit_status="pass")
        if any("adaptive" in v.lower() for v in data["violations"]):
            problems.append(f"用例39c：合规的自适应形态被误拦：{data['violations'][:3]}")

        # 39d：未声明宽度轴时不得要求第八项闸门（手机档 run 是合法状态）
        _code, data = adaptive_run(
            "20260101-000000-objc-039d", dict(GATE_PASS), True,
            {"schemaVersion": 1}, with_targets=False)
        if any("adaptiveAudit" in v for v in data["violations"]):
            problems.append(
                f"用例39d：未声明宽度轴却被要求 adaptiveAudit：{data['violations'][:3]}")
        if not any("adaptiveLayout" in w for w in data["warnings"]):
            problems.append("用例39d：未声明宽度轴必须留下告警，不能静默")

        # 39e：声明了宽度轴却没有采样清单 —— 采样只写在计划里就没有几何证据可采
        _code, data = adaptive_run(
            "20260101-000000-objc-039e",
            {**GATE_PASS, "adaptiveAudit": "not-run"}, False, adaptive_plan(),
            with_targets=False)
        if not any("adaptive-targets.json" in v for v in data["violations"]):
            problems.append(
                f"用例39e：缺 adaptive-targets.json 未被拦下：{data['violations'][:3]}")

        # 39f：计划硬伤（把「拉满」写成 policy）不得等到编译才发现
        broken = adaptive_plan()
        broken["adaptiveLayout"]["regions"].append(
            {"region": "list", "widthPolicy": "stretch-full-width"})
        _code, data = adaptive_run(
            "20260101-000000-objc-039f",
            {**GATE_PASS, "adaptiveAudit": "pass"}, True, broken, audit_status="pass")
        if not any("stretch-full-width" in v for v in data["violations"]):
            problems.append(
                f"用例39f：widthPolicy 写成 stretch-full-width 未被拦下：{data['violations'][:3]}")

    for p in problems:
        print(p)
    if problems:
        print("产物契约校验器未满足契约")
        return 1
    print("契约校验器：合规通过、缺件报错、篡改识别、legacy 豁免、模式区分、同源与派生图检查、"
          "区域级结构证据与对齐审计交叉校验、布局约束的计划质量/源码合规/闸门交叉三层均正确、"
          "基准字体链的替换检出与闸门交叉均正确、声明的结构差异下界既放行合规形态又拦下七种误用、"
          "视觉闸门记 pass 时比较结论必须支持它（下界内放行是唯一可升格的情形）、"
          "第八项闸门按宽度轴声明条件必需且与几何审计交叉核对、"
          "deliveryReady 在结构不全时判「不推导」而不是猜")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
