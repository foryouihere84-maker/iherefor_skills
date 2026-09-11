#!/usr/bin/env python3
"""Check local Lanhu MCP readiness without reading or printing credentials.

只读检查：不读取、不打印、不持久化任何凭据值。

关键判定：注册记录里的 ``args`` 入口必须与本地 skill 内的 ``dist/index.js``
指向同一个文件。否则即使「codex 已注册」与「本地已构建」同时成立，实际链路
依然是断的——codex 会在启动时加载到别的 checkout，或者根本加载不到。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

CREDENTIAL_KEYS = ('LANHU_COOKIE', 'LANHU_AUTHORIZATION')


def parse_registration(text):
    """从 ``codex mcp get`` 的输出中解析 args 入口与 env 行（只取键名匹配用）。"""
    entrypoint = None
    env_line = ''
    for line in (text or '').splitlines():
        stripped = line.strip()
        if stripped.startswith('args:'):
            entrypoint = stripped[len('args:'):].strip() or None
        elif stripped.startswith('env:'):
            env_line = stripped[len('env:'):].strip()
    return entrypoint, env_line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skill-dir', default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument('--output')
    args = ap.parse_args()

    root = Path(args.skill_dir).resolve()
    server = root / 'lanhu-mcp-server'
    dist = server / 'dist' / 'index.js'
    codex_cli = shutil.which('codex')

    try:
        proc = subprocess.run(['codex', 'mcp', 'get', 'lanhu-mcp'],
                              text=True, capture_output=True, timeout=15)
        registered = proc.returncode == 0
        registration_output = (proc.stdout if registered else proc.stderr) or ''
    except Exception as exc:  # codex 不存在、超时等
        registered = False
        registration_output = str(exc)

    registered_entry, env_line = parse_registration(registration_output)
    entrypoint_matches = bool(
        registered
        and registered_entry
        and dist.is_file()
        and os.path.realpath(registered_entry) == os.path.realpath(dist)
    )
    env_keys = set(re.findall(r'([A-Z][A-Z0-9_]*)=', env_line))

    blocking = []
    if not codex_cli:
        blocking.append('codex CLI 不可用')
    if not dist.is_file():
        blocking.append(f'本地未构建 lanhu-mcp-server：{dist}')
    if not registered:
        blocking.append('codex 未注册 lanhu-mcp')
    elif not registered_entry:
        blocking.append('注册记录中未解析到 args 入口')
    elif not entrypoint_matches:
        blocking.append(f'注册入口与本地 dist 不一致：{registered_entry}')

    result = {
        'schemaVersion': 1,
        'skillDirectory': str(root),
        'serverDirectory': str(server),
        'localCheckout': server.is_dir(),
        'builtEntrypoint': str(dist) if dist.is_file() else None,
        'built': dist.is_file(),
        'codexCli': codex_cli is not None,
        'registration': {
            'status': 'registered' if registered else 'not-registered',
            'detail': registration_output[-500:],
        },
        'registeredEntrypoint': registered_entry,
        'registeredEntrypointExists': bool(registered_entry and Path(registered_entry).is_file()),
        'entrypointMatches': entrypoint_matches,
        'registeredCredentials': {key: key in env_keys for key in CREDENTIAL_KEYS},
        'status': 'setup-required' if blocking else 'ready',
        'blockingReasons': blocking,
    }

    if blocking:
        result['suggestedCommand'] = (
            'codex mcp add lanhu-mcp '
            "--env LANHU_COOKIE='<从当前 Lanhu 浏览器会话复制>' "
            "--env LANHU_AUTHORIZATION='<从当前 Lanhu 浏览器会话复制>' "
            f"-- {shutil.which('node') or 'node'} {dist}"
        )

    out = Path(args.output) if args.output else root / '.lanhu-mcp-status.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
