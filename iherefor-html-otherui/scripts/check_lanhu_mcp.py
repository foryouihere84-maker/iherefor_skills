#!/usr/bin/env python3
"""Check Lanhu MCP readiness without reading or printing credentials.

只读检查：不读取、不打印、不持久化任何凭据值。

本脚本**不假设任何特定 coding agent**。它只认识两种通用形态：

1. **MCP 配置文件**——JSON 的 ``mcpServers`` 映射（``kind: mcp-json``），
   或 TOML 的 ``[mcp_servers.*]`` 表（``kind: mcp-toml``）；
2. **命令行注册**——能打印注册信息的命令（``kind: cli``）。

「去哪里找」由数据表描述，不由代码决定：默认读 ``scripts/mcp-registries.json``，
可用 ``--registries`` 或环境变量 ``LANHU_MCP_REGISTRIES`` 整体替换，
也可用 ``--mcp-config`` / ``--registry-cmd`` 直接指定单个来源。
因此接入表里没有的客户端不需要改动本脚本。

核心判定（与客户端无关）：找到的入口必须与本地 ``lanhu-mcp-server/dist/index.js``
指向同一文件。否则「已注册」与「本地已构建」会同时成立、链路却是断的——运行时
加载的是别的 checkout，或者根本加载不到。只要有一条来源真正指向本 checkout，
就算就绪；一条都对不上才算阻塞。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

# 入口必须是脚本文件：args 里除入口外还可能带参数（如 ``--flag``）。
ENTRYPOINT_SUFFIXES = ('.js', '.mjs', '.cjs')

CREDENTIAL_KEYS = ('LANHU_COOKIE', 'LANHU_AUTHORIZATION')

DEFAULT_SERVER_NAME = 'lanhu-mcp'

COMMAND_TIMEOUT = 15

# kind: cli 的输出里，键名形如 ``ENV_NAME=value``；只取键名判断存在性。
ENV_KEY_PATTERN = re.compile(r'([A-Z][A-Z0-9_]*)=')
# TOML 回退解析用：``[mcp_servers.foo]`` 段头。
TOML_TABLE_PATTERN = re.compile(r'^\s*\[([^\[\]]+)\]\s*$', re.MULTILINE)


def expand_location(spec, skill_dir, server_dir):
    """把表里的位置模板展开成绝对路径。

    支持 ``~``、``%VAR%``（Windows）、以及 ``{skillDir}`` / ``{serverDir}`` / ``{cwd}``
    三个占位符（后者按当前工作目录展开）。识别不了的模板原样保留，最终表现为
    「该文件不存在」，而不是异常。
    """
    text = str(spec)
    for token, value in (('{skillDir}', skill_dir), ('{serverDir}', server_dir), ('{cwd}', os.getcwd())):
        text = text.replace(token, str(value))
    text = os.path.expandvars(text)
    return Path(os.path.expanduser(text))


def entrypoint_from_args(args, base_dir):
    """从 args 里挑出入口脚本，并相对配置文件所在目录解析。

    只认后缀，不认「第几个参数」，因此 ``["dist/index.js"]``、
    ``["-y", "pkg", "/abs/path/server.js"]`` 这类写法都能取到。
    """
    if isinstance(args, str):
        args = [args]
    for item in args or []:
        token = str(item)
        if token.lower().endswith(ENTRYPOINT_SUFFIXES):
            path = Path(os.path.expanduser(token))
            if not path.is_absolute():
                path = base_dir / path
            return str(path)
    return None


def entrypoint_from_text(text):
    """从命令行输出里取第一个形如 ``*.js`` 的 token。"""
    for token in re.split(r'[\s,]+', text or ''):
        cleaned = token.strip('"\'[]()')
        if cleaned.lower().endswith(ENTRYPOINT_SUFFIXES):
            return cleaned
    return None


def iter_table(container, table_path):
    """按 ``table_path`` 逐层取子表，中途类型不符则返回 None。"""
    current = container
    for key in table_path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current if isinstance(current, dict) else None


def pick_server_entry(server_map, server_name):
    """在 server 映射里找目标条目；键名不同但 env 带 LANHU_COOKIE 的也算命中。"""
    entry = server_map.get(server_name)
    if isinstance(entry, dict):
        return server_name, entry
    for key, value in server_map.items():
        if isinstance(value, dict) and (value.get('env') or {}).get('LANHU_COOKIE'):
            return key, value
    return None, None


def blank_result(kind, location):
    return {
        'kind': kind,
        'location': str(location) if location else None,
        'available': False,
        'serverFound': False,
        'serverKey': None,
        'entrypoint': None,
        'command': None,
        'envKeys': [],
        'error': None,
    }


def probe_mcp_json(location, server_map_path, server_name):
    """探测一个 JSON MCP 配置文件。"""
    result = blank_result('mcp-json', location)
    if not location.is_file():
        result['error'] = 'file-missing'
        return result
    result['available'] = True
    try:
        data = json.loads(location.read_text(encoding='utf-8'))
    except Exception as exc:
        result['error'] = f'parse-error:{exc.__class__.__name__}'
        return result
    server_map = iter_table(data, server_map_path)
    if server_map is None:
        result['error'] = 'server-map-not-found'
        return result
    key, entry = pick_server_entry(server_map, server_name)
    if entry is None:
        result['error'] = 'server-not-registered'
        return result
    result['serverFound'] = True
    result['serverKey'] = key
    result['command'] = entry.get('command')
    result['entrypoint'] = entrypoint_from_args(entry.get('args'), location.parent)
    result['envKeys'] = sorted((entry.get('env') or {}).keys())
    return result


def parse_toml_fallback(text, table_path, server_name):
    """``tomllib`` 不可用时的最小回退解析。

    只处理本用途需要的形状：``[mcp_servers.<name>]`` 段里的 ``args`` 数组与
    ``env`` 子表。够用即可，不试图实现完整 TOML。
    """
    prefix = ''
    markers = []
    for match in TOML_TABLE_PATTERN.finditer(text):
        markers.append((match.start(), [seg.strip().strip('"\'') for seg in match.group(1).split('.')]))
    wanted = [seg for seg in table_path]
    for index, (start, segments) in enumerate(markers):
        if len(segments) != len(wanted) + 1 or segments[:len(wanted)] != wanted:
            continue
        if segments[-1] != server_name:
            continue
        end = markers[index + 1][0] if index + 1 < len(markers) else len(text)
        return text[start:end]
    return None


def probe_mcp_toml(location, server_table_path, server_name):
    """探测一个 TOML MCP 配置文件。"""
    result = blank_result('mcp-toml', location)
    if not location.is_file():
        result['error'] = 'file-missing'
        return result
    result['available'] = True
    data = None
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:
        tomllib = None
    if tomllib is not None:
        try:
            data = tomllib.loads(location.read_text(encoding='utf-8'))
        except Exception as exc:
            result['error'] = f'parse-error:{exc.__class__.__name__}'
            return result
    if data is not None:
        server_map = iter_table(data, server_table_path)
        if server_map is None:
            result['error'] = 'server-map-not-found'
            return result
        key, entry = pick_server_entry(server_map, server_name)
        if entry is None:
            result['error'] = 'server-not-registered'
            return result
        result['serverFound'] = True
        result['serverKey'] = key
        result['command'] = entry.get('command')
        result['entrypoint'] = entrypoint_from_args(entry.get('args'), location.parent)
        result['envKeys'] = sorted((entry.get('env') or {}).keys())
        return result
    # tomllib 缺失：退回文本解析，并把降级事实记进结果。
    section = parse_toml_fallback(location.read_text(encoding='utf-8'), server_table_path, server_name)
    if section is None:
        result['error'] = 'server-not-registered'
        result['note'] = 'tomllib-unavailable; 已退回文本解析'
        return result
    args_match = re.search(r'^\s*args\s*=\s*\[(.*?)\]', section, re.MULTILINE | re.DOTALL)
    args = [part.strip().strip('"\'') for part in (args_match.group(1).split(',') if args_match else []) if part.strip()]
    result['serverFound'] = True
    result['serverKey'] = server_name
    result['entrypoint'] = entrypoint_from_args(args, location.parent)
    result['envKeys'] = sorted(set(ENV_KEY_PATTERN.findall(section)))
    result['note'] = 'tomllib-unavailable; 已退回文本解析'
    return result


def probe_cli(argv, server_name):
    """探测一条打印注册信息的命令；命令不存在或返回非零都只记为「未命中」。"""
    result = blank_result('cli', ' '.join(argv))
    result['argv'] = list(argv)
    if not argv or shutil.which(argv[0]) is None:
        result['error'] = 'executable-not-found'
        return result
    result['available'] = True
    try:
        proc = subprocess.run(argv, text=True, capture_output=True, timeout=COMMAND_TIMEOUT)
    except Exception as exc:
        result['error'] = f'exec-failed:{exc.__class__.__name__}'
        return result
    output = (proc.stdout if proc.returncode == 0 else proc.stderr) or ''
    result['detail'] = output[-500:]
    if proc.returncode != 0:
        result['error'] = 'server-not-registered'
        return result
    entrypoint = entrypoint_from_text(output)
    if not entrypoint:
        result['error'] = 'entrypoint-not-found-in-output'
        return result
    result['serverFound'] = True
    result['serverKey'] = server_name
    result['entrypoint'] = entrypoint
    result['envKeys'] = sorted(set(ENV_KEY_PATTERN.findall(output)))
    return result


def load_table(path, server_name):
    """读适配器数据表；缺失或损坏时返回空表，让显式参数仍可用。"""
    if not path.is_file():
        return [], server_name, 'table-missing'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return [], server_name, f'table-parse-error:{exc.__class__.__name__}'
    registries = data.get('registries')
    if not isinstance(registries, list):
        return [], server_name, 'table-has-no-registries'
    return registries, data.get('serverName') or server_name, None


def collect_probes(table, skill_dir, server_dir, cwd, server_name, explicit_configs, explicit_commands):
    """把数据表与显式参数统一展开成一组探测任务，再逐个执行。"""
    probes = []

    for spec in explicit_configs:
        location = Path(os.path.expanduser(str(spec)))
        if not location.is_absolute():
            location = cwd / location
        probes.append(('explicit-mcp-config', 'mcp-json', ['mcpServers'], location))

    for spec in explicit_commands:
        argv = spec if isinstance(spec, list) else spec.split()
        probes.append(('explicit-registry-cmd', 'cli', None, argv))

    for entry in table:
        if not isinstance(entry, dict):
            continue
        kind = entry.get('kind')
        label = entry.get('id') or kind or 'registry'
        if kind == 'cli':
            argv = [
                str(token).replace('{serverName}', server_name)
                for token in (entry.get('argv') or [])
            ]
            if argv:
                probes.append((label, 'cli', None, argv))
            continue
        if kind not in ('mcp-json', 'mcp-toml'):
            continue
        locations = entry.get('locations') or []
        for spec in locations:
            probes.append((
                label,
                kind,
                entry.get('serverMapPath') or entry.get('serverTablePath') or [],
                expand_location(spec, skill_dir, server_dir),
            ))

    registrations = []
    for label, kind, table_path, payload in probes:
        if kind == 'cli':
            result = probe_cli(payload, server_name)
        elif kind == 'mcp-json':
            result = probe_mcp_json(payload, table_path, server_name)
        else:
            result = probe_mcp_toml(payload, table_path, server_name)
        result['registryId'] = label
        registrations.append(result)
    return registrations


def main():
    script_dir = Path(__file__).resolve().parent

    ap = argparse.ArgumentParser(description='检查 Lanhu MCP 就绪状态（只读，不打印凭据）')
    ap.add_argument('--skill-dir', default=str(script_dir.parent))
    ap.add_argument('--output')
    ap.add_argument('--registries', default=str(script_dir / 'mcp-registries.json'),
                    help='注册位置数据表；也可用环境变量 LANHU_MCP_REGISTRIES 指定')
    ap.add_argument('--mcp-config', action='append', default=[],
                    help='额外检查的 MCP JSON 配置文件（可重复）；'
                         '也可用环境变量 LANHU_MCP_CONFIGS 传多个（按 path 分隔符）')
    ap.add_argument('--registry-cmd', action='append', default=[],
                    help='额外执行的注册查询命令（可重复，整条命令作为一个参数）')
    ap.add_argument('--server-name', default=None, help='MCP server 名，默认取数据表')
    args = ap.parse_args()

    root = Path(args.skill_dir).resolve()
    server = root / 'lanhu-mcp-server'
    dist = server / 'dist' / 'index.js'
    cwd = Path.cwd()

    # 环境变量注入的配置文件与命令行参数等价，便于宿主/harness 在调用时指定。
    explicit_configs = list(args.mcp_config) + [
        item for item in os.environ.get('LANHU_MCP_CONFIGS', '').split(os.pathsep) if item.strip()
    ]

    table_path = Path(os.path.expanduser(
        os.environ.get('LANHU_MCP_REGISTRIES') or args.registries
    ))
    table, table_server_name, table_error = load_table(table_path, DEFAULT_SERVER_NAME)
    server_name = args.server_name or table_server_name or DEFAULT_SERVER_NAME

    registrations = collect_probes(
        table, root, server, cwd, server_name, explicit_configs, args.registry_cmd
    )

    dist_real = os.path.realpath(dist) if dist.is_file() else None
    for item in registrations:
        entrypoint = item.get('entrypoint')
        item['entrypointExists'] = bool(entrypoint and Path(entrypoint).is_file())
        item['entrypointMatches'] = bool(
            dist_real and entrypoint and os.path.realpath(entrypoint) == dist_real
        )
        item['credentials'] = {key: key in item.get('envKeys', []) for key in CREDENTIAL_KEYS}
        item.pop('envKeys', None)

    found = [item for item in registrations if item.get('serverFound')]
    matched = [item for item in registrations if item.get('entrypointMatches')]

    blocking = []
    if not dist.is_file():
        blocking.append(f'本地未构建 lanhu-mcp-server：{dist}')
    if not found:
        blocking.append(
            f'未在任何 MCP 配置或注册命令中找到 {server_name}'
            f'（已检查 {len(registrations)} 处，数据表：{table_path}）'
        )
    else:
        for item in found:
            if not item.get('entrypoint'):
                blocking.append(
                    f"{item['location']} 的注册记录中未解析到入口脚本"
                )
            elif not item.get('entrypointMatches'):
                blocking.append(
                    f"注册入口与本地 dist 不一致：{item['entrypoint']}"
                    f"（来源：{item['registryId']} {item['location']}）"
                )

    ready_registries = sorted({item['registryId'] for item in matched})
    wired = bool(dist_real) and bool(matched)
    status = 'ready' if wired else 'setup-required'

    result = {
        'schemaVersion': 2,
        'serverName': server_name,
        'skillDirectory': str(root),
        'serverDirectory': str(server),
        'localCheckout': server.is_dir(),
        'builtEntrypoint': str(dist) if dist.is_file() else None,
        'built': dist.is_file(),
        'registriesTable': {
            'path': str(table_path),
            'entries': len(table),
            'error': table_error,
        },
        'registrations': registrations,
        # 聚合字段：第一条命中的入口，以及「是否存在真正指向本 checkout 的注册」。
        'registeredEntrypoint': found[0]['entrypoint'] if found else None,
        'entrypointMatches': bool(matched),
        'readyRegistries': ready_registries,
        'status': status,
        'blockingReasons': [] if wired else blocking,
    }

    if not wired:
        node = shutil.which('node') or 'node'
        result['suggestedRegistrations'] = {
            'mcpJson': {
                'mcpServers': {
                    server_name: {
                        'type': 'stdio',
                        'command': node,
                        'args': [str(dist)],
                        'env': {},
                    }
                }
            },
            'howTo': [
                '把上面的 mcpJson 片段合并进你所使用客户端的 MCP 配置文件的 mcpServers；',
                '或使用该客户端自带的「新增 MCP server」命令注册同一 command/args；',
                f'凭据无需写进配置——server 会自行读取 {server / ".env"}；',
                '注册后 MCP 通常需要信任/启用，并重启会话才会生效。',
            ],
            'verifyCommand': f'{node} {dist}',
        }
        if table_error:
            result['suggestedRegistrations']['howTo'].append(
                f'注册位置数据表不可用（{table_error}）：可用 --mcp-config 或 --registry-cmd 显式指定。'
            )

    out = Path(args.output) if args.output else root / '.lanhu-mcp-status.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
