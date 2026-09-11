#!/usr/bin/env python3
"""回归：注册入口与本地 dist 不一致时，不得报告 ready。

用 PATH 注入一个假的 codex（fixtures/fakebin/codex），它返回一条指向不存在路径的
注册记录；本地 skill 目录则含一个已构建的 dist。两者不一致时 status 必须不是 ready。
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAKE_BIN = ROOT / "scripts" / "tests" / "fixtures" / "fakebin"


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        skill = tmp / "skill"
        (skill / "lanhu-mcp-server" / "dist").mkdir(parents=True)
        (skill / "lanhu-mcp-server" / "dist" / "index.js").write_text("// stub\n")
        out = tmp / "status.json"

        env = dict(os.environ)
        env["PATH"] = f"{FAKE_BIN}{os.pathsep}{env.get('PATH', '')}"

        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_lanhu_mcp.py"),
             "--skill-dir", str(skill), "--output", str(out)],
            capture_output=True, text=True, env=env,
        )
        if not out.exists():
            print(f"check_lanhu_mcp.py 未产出结果：{(proc.stderr or proc.stdout).strip()[:300]}")
            return 1

        data = json.loads(out.read_text())
        problems = []
        if data.get("status") == "ready":
            problems.append("注册入口指向不存在的路径，脚本仍报告 ready（假绿）")
        if data.get("entrypointMatches") is not False:
            problems.append("缺少 entrypointMatches=false 这一判定字段")
        if not data.get("registeredEntrypoint"):
            problems.append("未记录注册记录中的 args 路径，无法审计")

        for p in problems:
            print(p)
        if problems:
            return 1

    print("注册入口与本地 dist 不一致时正确拒绝 ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
