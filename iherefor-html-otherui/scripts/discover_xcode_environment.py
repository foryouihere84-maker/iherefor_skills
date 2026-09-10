#!/usr/bin/env python3
"""Read-only discovery of Xcode entry points, schemes and connected devices."""
import argparse, json, subprocess
from pathlib import Path
def run(cmd):
    try:
        p=subprocess.run(cmd,text=True,capture_output=True,timeout=30)
        return {'status':'passed' if p.returncode==0 else 'failed','stdout':p.stdout,'stderr':p.stderr,'code':p.returncode}
    except Exception as e: return {'status':'failed','stdout':'','stderr':str(e),'code':-1}
ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); ap.add_argument('--output'); a=ap.parse_args()
root=Path(a.root).resolve(); ws=sorted(str(x) for x in root.rglob('*.xcworkspace') if 'Pods' not in x.parts and not any(part.endswith('.xcodeproj') for part in x.parts)); pr=sorted(str(x) for x in root.rglob('*.xcodeproj') if 'Pods' not in x.parts)
entries=[{'type':'workspace','path':p,'list':run(['xcodebuild','-list','-json','-workspace',p])} for p in ws]+[{'type':'project','path':p,'list':run(['xcodebuild','-list','-json','-project',p])} for p in pr]
result={'schemaVersion':1,'root':str(root),'entryPoints':entries,'devices':{'simulators':run(['xcrun','simctl','list','devices','available','-j']),'physical':run(['xcrun','devicectl','list','devices','--json'])},'selection':{'status':'needs-selection' if len(entries)!=1 else 'candidate','reason':'multiple entries require explicit choice'}}
out=Path(a.output) if a.output else root/'.ios-environment.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n'); print(out)
