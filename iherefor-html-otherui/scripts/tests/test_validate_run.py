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


def layout_proportions_plan(region_overrides=None, relation_overrides=None):
    """一份声明了 layoutProportions 的实现计划（合规基线）。"""
    relations = [
        {"id": "Card.x", "kind": "proportional", "axis": "x",
         "ratio": 0.488806, "of": "root"},
        {"id": "Card.y", "kind": "proportional", "axis": "y",
         "ratio": 0.839817, "of": "root"},
        {"id": "Card.width", "kind": "proportional", "axis": "width",
         "ratio": 0.898010, "of": "root"},
        {"id": "Card.height", "kind": "proportional", "axis": "height",
         "ratio": 0.077803, "of": "root"},
    ]
    if relation_overrides:
        relations = relation_overrides(relations)
    region = {
        "region": "Card", "index": 1, "kindSource": "proposed",
        "ratios": {"xRatio": 0.039801, "yRatio": 0.800915, "widthRatio": 0.898010,
                   "heightRatio": 0.077803, "centerXRatio": 0.488806,
                   "centerYRatio": 0.839817},
        "relations": relations, "nativeIdiom": [],
    }
    if region_overrides:
        region = region_overrides(region) or region
    return {
        "schemaVersion": 1,
        "layoutProportions": {
            "model": "proportional", "basis": "viewport", "axisPolicy": "per-axis",
            "basisSize": {"width": 402, "height": 874},
            "regions": [region],
            # 734pt 是 Card.centerY 在探针设备上的值：只在 402x874 上成立。
            "forbiddenLiterals": [
                {"relation": "Card.centerY", "deviceDerivedPt": 734.0,
                 "why": "探针设备 402x874 上的绝对值，换台设备即失效",
                 "ratioInstead": 0.839817}],
        },
    }


COMPLIANT_SOURCE = """\
// 位置与尺寸一律用比例：没有任何数字来自探针设备的绝对值
[[self card] centerXAnchor].constraint(equalTo: root.widthAnchor, multiplier: 0.488806);
[[self card] centerYAnchor].constraint(equalTo: root.heightAnchor, multiplier: 0.839817);
[[self card] widthAnchor].constraint(equalTo: root.widthAnchor, multiplier: 0.898010);
[[self card] heightAnchor].constraint(equalTo: root.heightAnchor, multiplier: 0.077803);
"""

ABSOLUTE_SOURCE = """\
// 把探针设备上的中心 y 直接敲进约束：看起来有出处、算过，换台设备就错
[[self card] centerYAnchor].constraint(equalToConstant: 734.0];
[[self card] widthAnchor].constraint(equalTo: root.widthAnchor, multiplier: 0.898010);
"""


def write_source(tmp, name, body):
    source = tmp / name
    source.mkdir(parents=True, exist_ok=True)
    (source / "CardLayout.m").write_text(body)
    return source


def write_page_facts(run_dir, elements, browser_meta=None):
    """把页面级字体事实写进 reference/，并可选写入 browser-meta。"""
    reference = run_dir.parent.parent / "reference"
    write_json(reference / "page-facts.json", {"schemaVersion": 2, "elements": elements})
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

        # ---- 布局比例契约：组件之间的布局关系必须按比例实现 ----
        compliant = write_source(tmp, "src-compliant", COMPLIANT_SOURCE)
        absolute = write_source(tmp, "src-absolute", ABSOLUTE_SOURCE)

        # 用例 20：计划声明了比例、源码按比例写 → 合规（阳性对照）
        ok_layout = make_run(tmp, "20260101-000000-objc-015", delivery_ready=True)
        write_json(ok_layout / "ui-implementation-plan.json", layout_proportions_plan())
        write_json(ok_layout / "diff" / "comparison.json", comparator_summary(ok_layout))
        write_json(ok_layout / "diff" / "alignment.json", alignment_summary(ok_layout))
        code, data = run_validator(ok_layout, source=[compliant])
        if code != 0 or not data["ok"]:
            problems.append(f"用例20：合规的比例实现被判不合规：{data['violations']}")

        # 用例 21：同一份计划，把一条比例换成设备推导值 → 必须拦下。
        # 这是变异探针：没有它，「用例20 通过」只说明脚本跑得动。
        bad_layout = make_run(tmp, "20260101-000000-objc-016", delivery_ready=True)
        write_json(bad_layout / "ui-implementation-plan.json", layout_proportions_plan())
        write_json(bad_layout / "diff" / "comparison.json", comparator_summary(bad_layout))
        write_json(bad_layout / "diff" / "alignment.json", alignment_summary(bad_layout))
        code, data = run_validator(bad_layout, source=[absolute])
        if code == 0:
            problems.append("用例21：把比例写成设备推导值未被拦下")
        if not any("布局比例" in v and "734" in v for v in data["violations"]):
            problems.append(f"用例21：违规未指出是哪个设备推导值：{data['violations']}")
        if not any("implementation" in v for v in data["violations"]):
            problems.append("用例21：源码未按比例实现时 implementation 闸门不得为 pass")

        # 用例 22：没给 --source 时只告警，不能假装验证过
        unverified = make_run(tmp, "20260101-000000-objc-017", delivery_ready=True)
        write_json(unverified / "ui-implementation-plan.json", layout_proportions_plan())
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
            problems.append(f"用例23：计划未声明比例关系应告警，得到 {code} / {data['warnings']}")

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

        # 用例 25：已落盘的比例结论判 fail，闸门却是 pass → 自相矛盾（与对齐审计同类）
        contradicted = make_run(tmp, "20260101-000000-objc-020", delivery_ready=True)
        write_json(contradicted / "ui-implementation-plan.json", layout_proportions_plan())
        write_json(contradicted / "diff" / "comparison.json", comparator_summary(contradicted))
        write_json(contradicted / "diff" / "alignment.json", alignment_summary(contradicted))
        write_json(contradicted / "diff" / "layout-proportions.json",
                   {"status": "fail", "violations": [{"kind": "no-proportional-idiom"}]})
        code, data = run_validator(contradicted)
        if code == 0 or not any("layout-proportions.json" in v or "比例校验判" in v
                                for v in data["violations"]):
            problems.append(f"用例25：比例结论 fail 而闸门 pass 未被识别：{data['violations']}")

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

    for p in problems:
        print(p)
    if problems:
        print("产物契约校验器未满足契约")
        return 1
    print("契约校验器：合规通过、缺件报错、篡改识别、legacy 豁免、模式区分、同源与派生图检查、"
          "区域级结构证据与对齐审计交叉校验、布局比例的计划质量/源码合规/闸门交叉三层均正确、"
          "基准字体链的替换检出与闸门交叉均正确、"
          "deliveryReady 在结构不全时判「不推导」而不是猜")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
