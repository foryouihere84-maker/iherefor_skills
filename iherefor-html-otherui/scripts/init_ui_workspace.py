#!/usr/bin/env python3
"""Create a deterministic .ihereforUI multi-page workspace without touching production code.

只创建目录骨架、项目/页面索引和报告占位，**不预创建 run 产物**：契约要求 run 目录里
的每个文件都有真实内容与来源，预置空 JSON 只会制造「文件在、内容空」的假合规。

用法：
    python3 scripts/init_ui_workspace.py <project-root> \
        --project-id <id> --page <name> [--page <name> ...] \
        --input-root <dir> --target-mode <mode> [--target-mode <mode> ...]
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

PAGE_DIRS = ("source", "reference", "plans", "runs")


def page_id(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not value:
        raise SystemExit("page name must contain letters or digits")
    return value


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="project directory in which .ihereforUI is created")
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--page", action="append", required=True, help="page name or stable page-id")
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--target-mode", action="append", required=True)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    ui = root / ".ihereforUI"
    input_root = str(Path(args.input_root).resolve())
    created_at = datetime.now(timezone.utc).isoformat()

    pages = []
    for raw in args.page:
        pid = page_id(raw)
        base = ui / "pages" / pid
        for name in PAGE_DIRS:
            (base / name).mkdir(parents=True, exist_ok=True)
        write_json(base / "page.json", {
            "schemaVersion": 1,
            "id": pid,
            "aliases": [raw] if raw != pid else [],
            "source": {"inputRoot": input_root, "entry": None, "styles": [], "scripts": [], "assets": []},
            "referenceViewport": None,
            "implementationPaths": {},
            "runs": [],
            "status": "registered",
        })
        write_json(base / "status.json", {
            "schemaVersion": 1,
            "pageId": pid,
            "status": "registered",
            "latestRunId": None,
            "deliveryReady": False,
            "checks": {},
        })
        pages.append({"id": pid, "path": f"pages/{pid}", "status": "registered"})

    (ui / "integration").mkdir(parents=True, exist_ok=True)

    write_json(ui / "project.json", {
        "schemaVersion": 1,
        "projectId": args.project_id,
        "createdAt": created_at,
        "inputRoot": input_root,
        "targetModes": args.target_mode,
        "currentPage": pages[0]["id"],
        "pages": pages,
    })
    write_json(ui / "reports" / "project-status.json", {
        "schemaVersion": 1,
        "projectId": args.project_id,
        "generatedAt": created_at,
        "pages": pages,
        "status": "registered",
    })
    write_json(ui / "reports" / "delivery-gate.json", {
        "schemaVersion": 1,
        "projectId": args.project_id,
        "deliveryReady": False,
        "blockingReasons": ["尚未创建任何 run"],
    })
    write_json(ui / "index.json", {
        "schemaVersion": 1,
        "project": "project.json",
        "pages": [p["path"] for p in pages],
    })
    print(ui)


if __name__ == "__main__":
    main()
