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
             device_size=BASELINE_SIZE):
    run_dir = tmp / "pages" / "demo" / "runs" / run_id
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


def run_validator(run_dir):
    out = run_dir / f"{run_dir.name}-validate.json"
    proc = subprocess.run([sys.executable, str(SCRIPT), "--run", str(run_dir), "--json", str(out)],
                          capture_output=True, text=True)
    return proc.returncode, json.loads(out.read_text())


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

    for p in problems:
        print(p)
    if problems:
        print("产物契约校验器未满足契约")
        return 1
    print("契约校验器：合规通过、缺件报错、篡改识别、legacy 豁免、模式区分、同源与派生图检查均正确")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
