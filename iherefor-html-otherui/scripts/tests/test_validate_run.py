#!/usr/bin/env python3
"""回归：产物契约校验器必须能识别缺件与 deliveryReady 篡改。

契约见 references/artifact-contract.md；本测试构造三种 run 目录来固定其行为。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate_run.py"

GATE_PASS = {
    "reference": "pass", "browser": "pass", "sourceAssets": "pass",
    "implementation": "pass", "build": "pass", "tests": "pass", "visualDiff": "pass",
}


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def make_run(run_dir, target_mode="ios-uikit-objective-c", gate_status=None, delivery_ready=False, legacy=False):
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "run.json", {
        "schemaVersion": 1, "runId": run_dir.name, "pageId": "demo",
        "targetMode": target_mode, "parentRunId": None,
        "referenceBaseline": {"approved": "reference/approved.json", "sha256": "0" * 64},
        "status": "needs-review", "legacy": legacy,
    })
    write_json(run_dir / "review.json", {"schemaVersion": 1, "runId": run_dir.name, "decision": "pending"})
    write_json(run_dir / "delivery-gate.json", {
        "schemaVersion": 1, "runId": run_dir.name,
        "status": gate_status or dict(GATE_PASS),
        "unsupported": {"count": 0, "reviewedCount": 0, "items": []},
        "deliveryReady": delivery_ready,
        "blockingReasons": [] if delivery_ready else ["demo"],
    })
    write_json(run_dir / "ui-implementation-plan.json", {"schemaVersion": 1})
    write_json(run_dir / "resource-policy.json", {"schemaVersion": 1})
    write_json(run_dir / "runtime-device.json", {"schemaVersion": 1})
    if target_mode.startswith("ios-"):
        write_json(run_dir / "ios-environment.json", {"schemaVersion": 1})
    (run_dir / "actual").mkdir(exist_ok=True)
    (run_dir / "diff").mkdir(exist_ok=True)


def run_validator(run_dir):
    out = run_dir.parent / f"{run_dir.name}-validate.json"
    proc = subprocess.run([sys.executable, str(SCRIPT), "--run", str(run_dir), "--json", str(out)],
                          capture_output=True, text=True)
    return proc.returncode, json.loads(out.read_text())


def main():
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # 用例 1：完整合规的 run 必须通过
        good = tmp / "20260101-000000-objc-001"
        make_run(good, delivery_ready=True)
        code, data = run_validator(good)
        if code != 0 or not data["ok"]:
            problems.append(f"用例1：合规 run 被判不合规：{data['violations']}")

        # 用例 2：缺文件必须被指出
        missing = tmp / "20260101-000000-objc-002"
        make_run(missing, delivery_ready=True)
        (missing / "runtime-device.json").unlink()
        code, data = run_validator(missing)
        if code == 0 or not any("runtime-device.json" in v for v in data["violations"]):
            problems.append("用例2：缺少 runtime-device.json 未被识别")

        # 用例 3：visualDiff=fail 却写 deliveryReady=true 必须被识别为篡改
        tampered = tmp / "20260101-000000-objc-003"
        make_run(tampered, gate_status={**GATE_PASS, "visualDiff": "fail"}, delivery_ready=True)
        code, data = run_validator(tampered)
        if code == 0 or not any("deliveryReady" in v for v in data["violations"]):
            problems.append("用例3：deliveryReady 与闸门状态矛盾未被识别")

        # 用例 4：legacy run 跳过产物必需项，但不得因此变成 ready
        legacy = tmp / "20260101-000000-objc-004"
        (legacy / "diff").mkdir(parents=True, exist_ok=True)
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
        android = tmp / "20260101-000000-android-005"
        make_run(android, target_mode="android-compose-kotlin", delivery_ready=True)
        code, data = run_validator(android)
        if code != 0:
            problems.append(f"用例5：Android run 被错误要求 iOS 产物：{data['violations']}")

    for p in problems:
        print(p)
    if problems:
        print("产物契约校验器未满足契约")
        return 1
    print("契约校验器：合规通过、缺件报错、篡改识别、legacy 豁免、模式区分均正确")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
