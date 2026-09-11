#!/usr/bin/env python3
"""回归：物理设备探测必须成功。

devicectl 没有 --json 选项，JSON 只能通过 --json-output <path> 落盘。此前脚本使用
--json 导致命令以 exit 64 失败，而该步骤是 iOS 任务的强制前置。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        root = tmp / "proj"
        (root / "App.xcodeproj").mkdir(parents=True)
        out = tmp / "ios-environment.json"

        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "discover_xcode_environment.py"),
             "--root", str(root), "--output", str(out)],
            capture_output=True, text=True, timeout=180,
        )
        if not out.exists():
            print(f"discover_xcode_environment.py 未产出结果：{(proc.stderr or proc.stdout).strip()[:300]}")
            return 1

        data = json.loads(out.read_text())
        physical = (data.get("devices") or {}).get("physical") or {}
        if physical.get("status") != "passed":
            detail = (physical.get("stderr") or physical.get("detail") or "")[:300]
            print(f"物理设备探测失败：{detail.strip()}")
            return 1

    print("物理设备探测命令执行成功")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
