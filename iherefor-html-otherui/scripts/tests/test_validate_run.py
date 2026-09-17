#!/usr/bin/env python3
"""回归：产物契约校验器必须能识别缺件、篡改，以及布局约束/宽度轴的合规与否。

契约见 references/artifact-contract.md；本测试构造多组 run 目录来固定其行为。
渲染链（字体链 / 像素 diff / 对齐审计 / 基准同源）已整体裁撤，故不再有对应用例。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate_run.py"

GATE_PASS = {
    "source": "pass", "sourceAssets": "pass",
    "implementation": "pass", "build": "pass", "tests": "pass",
}


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def make_run(tmp, run_id, target_mode="ios-uikit-objective-c", gate_status=None,
             delivery_ready=False, legacy=False, page="demo"):
    """造一个 run 目录（产物契约必需项齐全的合规基线）。"""
    run_dir = tmp / "pages" / page / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

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
    # 两张页面分析表是**强制产物**（缺一即判不合规），合规基线必须带上，
    # 否则每个用例都会因为「缺少必需产物」而失败，把真正的判据淹没。
    (run_dir / "过程中页面分析表.md").write_text("# 过程中页面分析表\n\n| 元素 | bounds |\n|---|---|\n")
    (run_dir / "最终页面分析表.md").write_text("# 最终页面分析表\n\n| 元素 | 实测 |\n|---|---|\n")
    write_json(run_dir / "runtime-device.json", {
        "schemaVersion": 1,
        "screenBoundsPoints": {"width": 402, "height": 874},
    })
    if target_mode.startswith("ios-"):
        write_json(run_dir / "ios-environment.json", {"schemaVersion": 1})
    return run_dir


def run_validator(run_dir, source=None):
    out = run_dir / f"{run_dir.name}-validate.json"
    args = [sys.executable, str(SCRIPT), "--run", str(run_dir), "--json", str(out)]
    for root in source or []:
        args += ["--source", str(root)]
    proc = subprocess.run(args, capture_output=True, text=True)
    return proc.returncode, json.loads(out.read_text())


def layout_proportions_plan(relation_overrides=None):
    """一份声明了 layoutProportions 的实现计划（合规基线，闭合契约口径）。

    ``fixed`` 必须带 ``why``：闭合契约下它是特例（视觉常量），不是默认值 ——
    设计稿给了 bounds 是**事实**，写成固定约束是**决策**，没有 why 两者在产物里
    长得一模一样，于是「照抄设计稿尺寸」这个要拦的头号问题就没痕迹可查。
    """
    relations = [
        {"id": "Card.x", "kind": "pinned", "axis": "x", "of": "root",
         "edges": ["leading"], "inset": 16.0},
        {"id": "Card.y", "kind": "proportional", "axis": "y", "of": "root",
         "ratio": 0.839817},
        {"id": "Card.width", "kind": "pinned", "axis": "width", "of": "root",
         "edges": ["leading", "trailing"],
         "insets": {"leading": 16.0, "trailing": 16.0},
         "why": "两侧各留 16pt 内边距：值由内边距闭合，随父容器伸缩"},
        {"id": "Card.height", "kind": "fixed", "axis": "height", "of": "root",
         "value": 68.0,
         "why": "卡片底板是明确固定高度的视觉控件，高度不随容器变化"},
    ]
    if relation_overrides:
        relations = relation_overrides(relations)
    # region 不带 parentIndex/basis：精简计划不该被 basis 口径强查。
    region = {
        "region": "Card", "index": 1, "relations": relations,
    }
    return {
        "schemaVersion": 1,
        "targetMode": "ios-uikit-objective-c",
        "layoutProportions": {
            "basis": {"width": 393, "height": 852},
            "basisSize": {"width": 393, "height": 852},
            "regions": [region],
            "forbiddenLiterals": [
                {"relation": "Card.centerY", "deviceDerivedPt": 734.0,
                 "ratioInstead": "y = page.height * 0.839817"},
            ],
        },
    }


def compliant_source(plan_payload):
    """一份照 plan 四类关系逐条实现的（伪）原生源码，含真实比例原语 multiplier。"""
    return (
        "// CardLayout.m\n"
        "void layoutCard(UIView *card, UIView *page) {\n"
        "  [card.leadingAnchor constraintEqualToAnchor:page.leadingAnchor constant:16].active = YES; // Card.x\n"
        "  [card.topAnchor constraintEqualToAnchor:page.topAnchor].active = YES;\n"
        "  // proportional: multiplier\n"
        "  [NSLayoutConstraint constraintWithItem:card attribute:NSLayoutAttributeTop\n"
        "      relatedBy:NSLayoutRelationEqual toItem:page attribute:NSLayoutAttributeHeight\n"
        "     multiplier:0.839817 constant:0].active = YES; // Card.y\n"
        "  [card.trailingAnchor constraintEqualToAnchor:page.trailingAnchor constant:-16].active = YES; // Card.width\n"
        "  [card.heightAnchor constraintEqualToConstant:68].active = YES; // Card.height\n"
        "}\n"
    )


def write_source(tmp, name, text):
    src = tmp / name
    src.mkdir(parents=True, exist_ok=True)
    (src / "CardLayout.m").write_text(text)
    return src


def adaptive_plan():
    return {
        "schemaVersion": 1,
        "targetMode": "ios-uikit-objective-c",
        "adaptiveLayout": {
            "model": "continuous-window-width",
            "windowSamples": [
                {"id": "phone-compact", "widthClass": "compact", "width": 402, "height": 874,
                 "deviceClass": "phone"},
                {"id": "tablet-regular-portrait", "widthClass": "expanded", "width": 1024,
                 "height": 1366, "deviceClass": "tablet"},
                {"id": "tablet-regular-landscape", "widthClass": "expanded", "width": 1366,
                 "height": 1024, "deviceClass": "tablet"},
                {"id": "phone-regular-landscape", "widthClass": "medium", "width": 874,
                 "height": 402, "deviceClass": "phone"},
            ],
            "regions": [{"region": "list", "widthPolicy": "centered-column",
                         "maxContentWidth": {"value": 640, "reason": "可读宽度"}}],
            "firstLevelWidthClass": "compact",
            "forbiddenAdaptations": ["uniform-scale"],
        },
    }


def adaptive_targets():
    return {"schemaVersion": 1, "samples": [], "deviceFamily": "ios"}


def adaptive_audit_report(status):
    return {"status": status, "violations": []}


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

        # 用例 3：build=fail 却写 deliveryReady=true 必须被识别为篡改
        tampered = make_run(tmp, "20260101-000000-objc-003",
                            gate_status={**GATE_PASS, "build": "fail"}, delivery_ready=True)
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

        # ---- 布局约束契约：尺寸按闭合方式声明、位置相对直接父视图 ----
        plan_payload = layout_proportions_plan()
        ok_source = compliant_source(plan_payload)

        # 用例 20：计划声明的四类关系，源码逐条照做 → 合规（阳性对照）
        ok_layout = make_run(tmp, "20260101-000000-objc-015", delivery_ready=True)
        write_json(ok_layout / "ui-implementation-plan.json", plan_payload)
        compliant = write_source(tmp, "src-compliant", ok_source)
        code, data = run_validator(ok_layout, source=[compliant])
        if code != 0 or not data["ok"]:
            problems.append(f"用例20：照计划声明的方式实现的源码被判不合规：{data['violations']}")

        # 用例 21：同一份计划，把那条比例换成设备推导值 → 必须拦下（变异探针）。
        target_item = next((f for f in plan_payload["layoutProportions"]["forbiddenLiterals"]
                            if abs(f["deviceDerivedPt"]) > 48), None)
        if target_item is None:
            problems.append("用例21：探针前提不成立 —— 计划里应有一条可变异的大数值比例关系")
        else:
            # 把源码里的 multiplier 比例换成写死探针设备上的绝对值（734pt）。
            mutated_source = ok_source.replace(
                "multiplier:0.839817 constant:0", "constant:734")
            if mutated_source == ok_source:
                problems.append("用例21：变异没有生效，探针无效")
            else:
                bad_layout = make_run(tmp, "20260101-000000-objc-016", delivery_ready=True)
                write_json(bad_layout / "ui-implementation-plan.json", plan_payload)
                absolute = write_source(tmp, "src-absolute", mutated_source)
                code, data = run_validator(bad_layout, source=[absolute])
                if code == 0:
                    problems.append("用例21：把比例写成设备推导值未被拦下")
                if not any("734" in v for v in data["violations"]):
                    problems.append(f"用例21：违规未指出是哪个设备推导值：{data['violations']}")

        # 用例 22：没给 --source 时只告警，不能假装验证过
        unverified = make_run(tmp, "20260101-000000-objc-017", delivery_ready=True)
        write_json(unverified / "ui-implementation-plan.json", plan_payload)
        code, data = run_validator(unverified)
        if code != 0:
            problems.append(f"用例22：未给 --source 不该硬判失败：{data['violations']}")
        if not any("--source" in w for w in data["warnings"]):
            problems.append("用例22：未提供源码时应告警说明「尚未验证」")

        # 用例 23：计划没声明 layoutProportions → 告警
        legacy_plan = make_run(tmp, "20260101-000000-objc-018", delivery_ready=True)
        code, data = run_validator(legacy_plan)
        if code != 0 or not any("layoutProportions" in w for w in data["warnings"]):
            problems.append(f"用例23：计划未声明布局约束应告警，得到 {code} / {data['warnings']}")

        # 用例 24：计划里 kind 非法 / intrinsic 缺 why → 必须硬判
        broken_plan = make_run(tmp, "20260101-000000-objc-019", delivery_ready=True)
        write_json(broken_plan / "ui-implementation-plan.json", layout_proportions_plan(
            relation_overrides=lambda rels: rels + [
                {"id": "Card.bad", "kind": "absolute", "ratio": 0.5},
                {"id": "Card.why", "kind": "intrinsic"}]))
        code, data = run_validator(broken_plan)
        if code == 0 or not any("unknown-relation-kind" in v or "intrinsic-missing-why" in v
                                for v in data["violations"]):
            problems.append(f"用例24：计划本身不合规未被拦下：{data['violations']}")

        # 用例 25：已落盘的布局结论判 fail，闸门却是 pass → 自相矛盾
        contradicted = make_run(tmp, "20260101-000000-objc-020", delivery_ready=True)
        write_json(contradicted / "ui-implementation-plan.json", plan_payload)
        write_json(contradicted / "diff" / "layout-proportions.json",
                   {"status": "fail", "violations": [{"kind": "no-proportional-idiom"}]})
        code, data = run_validator(contradicted)
        if code == 0 or not any("layout-proportions.json" in v and "implementation" in v
                                for v in data["violations"]):
            problems.append(f"用例25：布局约束结论 fail 而闸门 pass 未被识别：{data['violations']}")

        # ---- delivery-gate 结构健壮性 ----
        # 用例 32：旧 schema 的 status 是字符串 → 必须报结构不对，不得抛栈
        legacy_gate = make_run(tmp, "20260101-000000-objc-027", delivery_ready=False)
        write_json(legacy_gate / "delivery-gate.json", {
            "deliveryReady": False, "status": "pass-with-review",
            "build": "passed", "test": "not-run", "visual": "needs-review",
        })
        try:
            code, data = run_validator(legacy_gate)
            if code == 0 or not any("delivery-gate.status" in v for v in data["violations"]):
                problems.append(f"用例32：未报出 status 结构不对：{data['violations'][:2]}")
        except Exception as exc:
            problems.append(f"用例32：字符串 status 让校验器抛栈：{type(exc).__name__}: {exc}")

        # 用例 33：unsupported 计数对象缺失时不得推导 delivery-ready
        no_unsupported = make_run(tmp, "20260101-000000-objc-028", delivery_ready=False)
        write_json(no_unsupported / "delivery-gate.json",
                   {"deliveryReady": False, "status": dict(GATE_PASS),
                    "blockingReasons": ["unsupported 计数对象缺失"]})
        code, data = run_validator(no_unsupported)
        if code == 0 or not any("unsupported" in v for v in data["violations"]):
            problems.append(f"用例33：未报出 unsupported 缺失：{data['violations'][:2]}")
        if not any("跳过一致性核对" in w for w in data["warnings"]):
            problems.append("用例33：跳过一致性核对没留痕")

        # 用例 34：计数写成字符串同样推不出来
        string_counts = make_run(tmp, "20260101-000000-objc-029", delivery_ready=False)
        write_json(string_counts / "delivery-gate.json",
                   {"deliveryReady": False, "status": dict(GATE_PASS),
                    "unsupported": {"count": "2", "reviewedCount": "2"},
                    "blockingReasons": ["unsupported 未复核完"]})
        code, data = run_validator(string_counts)
        if code == 0 or not any("必须是整数" in v for v in data["violations"]):
            problems.append(f"用例34：未报出计数类型不对：{data['violations'][:2]}")

        # 用例 35：阳性对照 —— 复核做完时照旧可交付；漏一项则变红
        reviewed = make_run(tmp, "20260101-000000-objc-030", delivery_ready=True)
        write_json(reviewed / "delivery-gate.json",
                   {"deliveryReady": True, "status": dict(GATE_PASS),
                    "unsupported": {"count": 3, "reviewedCount": 3}})
        code, data = run_validator(reviewed)
        if code != 0:
            problems.append(f"用例35：复核做完的正常 run 被判不合规：{data['violations'][:2]}")
        half = make_run(tmp, "20260101-000000-objc-031", delivery_ready=True)
        write_json(half / "delivery-gate.json",
                   {"deliveryReady": True, "status": dict(GATE_PASS),
                    "unsupported": {"count": 3, "reviewedCount": 2}})
        code, data = run_validator(half)
        if code == 0 or not any("应为 False" in v for v in data["violations"]):
            problems.append(f"用例35：漏一项复核仍被判可交付：{data['violations'][:2]}")

        # ---- 宽度轴：第七项闸门条件必需 ----
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

        # 39a：声明了宽度轴却没写第七项闸门
        _code, data = adaptive_run(
            "20260101-000000-objc-039a", dict(GATE_PASS), False, adaptive_plan())
        if not any("adaptiveAudit" in v for v in data["violations"]):
            problems.append(f"用例39a：声明宽度轴却缺 adaptiveAudit 未被拦下：{data['violations'][:3]}")

        # 39b：几何审计判 fail，闸门不得记 pass
        _code, data = adaptive_run(
            "20260101-000000-objc-039b",
            {**GATE_PASS, "adaptiveAudit": "pass"}, True, adaptive_plan(),
            audit_status="fail")
        if not any("adaptiveAudit" in v and "pass" in v for v in data["violations"]):
            problems.append(f"用例39b：审计判 fail 而闸门记 pass 未被拦下：{data['violations'][:3]}")

        # 39c：阳性对照
        _code, data = adaptive_run(
            "20260101-000000-objc-039c",
            {**GATE_PASS, "adaptiveAudit": "pass"}, True, adaptive_plan(),
            audit_status="pass")
        if any("adaptive" in v.lower() for v in data["violations"]):
            problems.append(f"用例39c：合规的自适应形态被误拦：{data['violations'][:3]}")

        # 39d：未声明宽度轴时不得要求第七项闸门
        _code, data = adaptive_run(
            "20260101-000000-objc-039d", dict(GATE_PASS), True,
            {"schemaVersion": 1}, with_targets=False)
        if any("adaptiveAudit" in v for v in data["violations"]):
            problems.append(f"用例39d：未声明宽度轴却被要求 adaptiveAudit：{data['violations'][:3]}")
        if not any("adaptiveLayout" in w for w in data["warnings"]):
            problems.append("用例39d：未声明宽度轴必须留下告警，不能静默")

        # 39e：声明了宽度轴却没有采样清单
        _code, data = adaptive_run(
            "20260101-000000-objc-039e",
            {**GATE_PASS, "adaptiveAudit": "not-run"}, False, adaptive_plan(),
            with_targets=False)
        if not any("adaptive-targets.json" in v for v in data["violations"]):
            problems.append(f"用例39e：缺 adaptive-targets.json 未被拦下：{data['violations'][:3]}")

        # 39f：计划硬伤（把「拉满」写成 policy）
        broken = adaptive_plan()
        broken["adaptiveLayout"]["regions"].append(
            {"region": "list", "widthPolicy": "stretch-full-width"})
        _code, data = adaptive_run(
            "20260101-000000-objc-039f",
            {**GATE_PASS, "adaptiveAudit": "pass"}, True, broken, audit_status="pass")
        if not any("stretch-full-width" in v for v in data["violations"]):
            problems.append(f"用例39f：widthPolicy 写成 stretch-full-width 未被拦下：{data['violations'][:3]}")

    for p in problems:
        print(p)
    if problems:
        print("产物契约校验器未满足契约")
        return 1
    print("契约校验器：合规通过、缺件报错、篡改识别、legacy 豁免、模式区分、"
          "布局约束的计划质量/源码合规/闸门交叉三层均正确、"
          "deliveryReady 结构健壮、第七项闸门按宽度轴声明条件必需且与几何审计交叉核对")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
