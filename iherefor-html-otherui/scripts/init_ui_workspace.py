#!/usr/bin/env python3
"""Create a deterministic .ihereforUI multi-page workspace without touching production code."""
import argparse, json, re
from pathlib import Path
from datetime import datetime, timezone

def page_id(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not value: raise SystemExit("page name must contain letters or digits")
    return value

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")

ap = argparse.ArgumentParser()
ap.add_argument("root", help="project directory in which .ihereforUI is created")
ap.add_argument("--project-id", required=True)
ap.add_argument("--page", action="append", required=True, help="page name or stable page-id")
ap.add_argument("--input-root", required=True)
ap.add_argument("--target-mode", action="append", required=True)
args = ap.parse_args()
root = Path(args.root).resolve(); ui = root / ".ihereforUI"
pages = []
for raw in args.page:
    pid = page_id(raw); base = ui / "pages" / pid
    for d in ["source", "reference", "plans", "runs"]: (base / d).mkdir(parents=True, exist_ok=True)
    write_json(base / "page.json", {"schemaVersion":1,"id":pid,"aliases": [raw] if raw != pid else [],"source":{"inputRoot":str(Path(args.input_root).resolve())},"implementationPaths":{},"runs":[],"status":"registered"})
    write_json(base / "status.json", {"schemaVersion":1,"pageId":pid,"status":"registered","checks":{}})
    pages.append({"id":pid,"path":f"pages/{pid}","status":"registered"})
write_json(ui / "project.json", {"schemaVersion":1,"projectId":args.project_id,"createdAt":datetime.now(timezone.utc).isoformat(),"inputRoot":str(Path(args.input_root).resolve()),"targetModes":args.target_mode,"currentPage":pages[0]["id"],"pages":pages})
write_json(ui / "reports" / "project-status.json", {"schemaVersion":1,"projectId":args.project_id,"pages":pages,"status":"registered"})
write_json(ui / "reports" / "delivery-gate.json", {"schemaVersion":1,"projectId":args.project_id,"deliveryReady":False,"status":"not-run"})
write_json(ui / "index.json", {"schemaVersion":1,"project": "project.json","pages": [p["path"] for p in pages]})
print(ui)
