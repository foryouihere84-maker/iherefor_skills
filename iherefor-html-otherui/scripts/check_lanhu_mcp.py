#!/usr/bin/env python3
"""Check local Lanhu MCP readiness without reading or printing credentials."""
import argparse, json, shutil, subprocess, os
from pathlib import Path
ap=argparse.ArgumentParser(); ap.add_argument('--skill-dir',default=str(Path(__file__).resolve().parents[1])); ap.add_argument('--output'); a=ap.parse_args()
root=Path(a.skill_dir).resolve(); server=root/'lanhu-mcp-server'; dist=server/'dist'/'index.js'
try:
 p=subprocess.run(['codex','mcp','get','lanhu-mcp'],text=True,capture_output=True,timeout=15); registered=p.returncode==0; registration={'status':'registered' if registered else 'not-registered','detail':(p.stdout if registered else p.stderr)[-500:]}
except Exception as e: registered=False; registration={'status':'unavailable','detail':str(e)}
result={'schemaVersion':1,'serverDirectory':str(server),'localCheckout':server.is_dir(),'builtEntrypoint':str(dist) if dist.is_file() else None,'built':dist.is_file(),'codexCli':shutil.which('codex') is not None,'registration':registration,'credentialsConfigured':{'LANHU_COOKIE':bool(os.environ.get('LANHU_COOKIE')),'LANHU_AUTHORIZATION':bool(os.environ.get('LANHU_AUTHORIZATION'))},'status':'ready' if dist.is_file() and registered else 'setup-required'}
out=Path(a.output) if a.output else root/'.lanhu-mcp-status.json'; out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n'); print(out)
