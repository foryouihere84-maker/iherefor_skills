#!/usr/bin/env python3
"""回归：workspace 初始化必须产出契约要求的目录与索引，且不预创建 run 产物。"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "init_ui_workspace.py"


def main():
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        root = tmp / "proj"
        input_root = tmp / "design-code"
        (root / "src").mkdir(parents=True)

        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(root),
             "--project-id", "demo", "--page", "Plan Selection",
             "--input-root", str(input_root),
             "--target-mode", "ios-uikit-objective-c"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            print(f"初始化失败：{(proc.stderr or proc.stdout).strip()[:300]}")
            return 1

        ui = root / ".ihereforUI"
        page = ui / "pages" / "plan-selection"

        for rel in ("integration", "reports", "pages/plan-selection/source",
                    "pages/plan-selection/reference", "pages/plan-selection/plans",
                    "pages/plan-selection/runs"):
            if not (ui / rel).is_dir():
                problems.append(f"缺少目录：.ihereforUI/{rel}")

        for rel in ("project.json", "index.json", "reports/project-status.json",
                    "reports/delivery-gate.json", "pages/plan-selection/page.json",
                    "pages/plan-selection/status.json"):
            if not (ui / rel).is_file():
                problems.append(f"缺少索引文件：.ihereforUI/{rel}")

        project = json.loads((ui / "project.json").read_text())
        for key in ("schemaVersion", "projectId", "inputRoot", "targetModes", "pages"):
            if key not in project:
                problems.append(f"project.json 缺少字段：{key}")

        page_json = json.loads((page / "page.json").read_text())
        for key in ("schemaVersion", "id", "source", "referenceViewport", "implementationPaths", "runs"):
            if key not in page_json:
                problems.append(f"page.json 缺少字段：{key}")

        status = json.loads((page / "status.json").read_text())
        if status.get("deliveryReady") is not False:
            problems.append("新注册页面不得为 deliveryReady=true")

        leftovers = sorted(p.name for p in (page / "runs").iterdir())
        if leftovers:
            problems.append(f"不得预创建 run 产物（制造假合规）：{leftovers}")

    for p in problems:
        print(p)
    if problems:
        return 1
    print("workspace 初始化结构与契约一致，且未预创建 run 产物")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
