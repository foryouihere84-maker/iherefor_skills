#!/usr/bin/env python3
"""Read-only discovery of Xcode entry points, schemes and connected devices.

只读取工程结构并调用 xcodebuild / simctl / devicectl 查询，不修改任何工程文件。

注意：``xcrun devicectl`` 没有 ``--json`` 选项，JSON 只能通过
``--json-output <path>`` 落盘后再读回；使用 ``--json`` 会直接以 exit 64 失败。
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

COMMAND_TIMEOUT = 60


def run(cmd):
    """执行只读命令并归一化结果，异常不抛出，转为 failed 状态。"""
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=COMMAND_TIMEOUT)
        return {
            'command': ' '.join(cmd),
            'status': 'passed' if proc.returncode == 0 else 'failed',
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'code': proc.returncode,
        }
    except Exception as exc:
        return {'command': ' '.join(cmd), 'status': 'failed', 'stdout': '', 'stderr': str(exc), 'code': -1}


def physical_devices():
    with tempfile.TemporaryDirectory() as tmp:
        json_path = Path(tmp) / 'devicectl-devices.json'
        result = run(['xcrun', 'devicectl', 'list', 'devices', '--json-output', str(json_path)])
        raw = []
        if result['status'] == 'passed':
            if json_path.is_file():
                try:
                    raw = json.loads(json_path.read_text()).get('result', {}).get('devices', [])
                except Exception as exc:
                    result['status'] = 'failed'
                    result['stderr'] = f'解析 devicectl JSON 失败：{exc}'
            else:
                result['status'] = 'failed'
                result['stderr'] = 'devicectl 未产出 JSON 文件'
    result['devices'] = [{
        'name': (d.get('deviceProperties') or {}).get('name'),
        'udid': d.get('identifier'),
        'osVersion': (d.get('deviceProperties') or {}).get('osVersionNumber'),
        'pairingState': (d.get('connectionProperties') or {}).get('pairingState'),
        'tunnelState': (d.get('connectionProperties') or {}).get('tunnelState'),
    } for d in raw]
    result['deviceCount'] = len(result['devices'])
    result.pop('stdout', None)  # 原始输出可能含设备私密信息，只保留解析后的摘要
    return result


def simulators():
    result = run(['xcrun', 'simctl', 'list', 'devices', 'available', '-j'])
    booted = []
    if result['status'] == 'passed':
        try:
            payload = json.loads(result['stdout'] or '{}')
        except Exception as exc:
            result['status'] = 'failed'
            result['stderr'] = f'解析 simctl JSON 失败：{exc}'
            payload = {}
        for runtime, devices in (payload.get('devices') or {}).items():
            for device in devices:
                if device.get('state') == 'Booted':
                    booted.append({
                        'name': device.get('name'),
                        'udid': device.get('udid'),
                        'runtime': runtime,
                        'state': device.get('state'),
                    })
    result['booted'] = booted
    result.pop('stdout', None)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--output')
    args = ap.parse_args()

    root = Path(args.root).resolve()
    workspaces = sorted(
        str(p) for p in root.rglob('*.xcworkspace')
        if 'Pods' not in p.parts and not any(part.endswith('.xcodeproj') for part in p.parts)
    )
    projects = sorted(str(p) for p in root.rglob('*.xcodeproj') if 'Pods' not in p.parts)

    entries = (
        [{'type': 'workspace', 'path': p, 'list': run(['xcodebuild', '-list', '-json', '-workspace', p])} for p in workspaces]
        + [{'type': 'project', 'path': p, 'list': run(['xcodebuild', '-list', '-json', '-project', p])} for p in projects]
    )

    physical = physical_devices()
    sim = simulators()

    device_candidates = (
        [{'kind': 'simulator', **d} for d in sim.get('booted', [])]
        + [{'kind': 'physical', **d} for d in physical.get('devices', [])]
    )

    if len(entries) == 1:
        selection = {'status': 'entry-point-resolved', 'entryPoint': entries[0]['path'], 'reason': None}
    elif not entries:
        selection = {'status': 'needs-entry-point', 'entryPoint': None, 'reason': '未找到 .xcworkspace 或 .xcodeproj'}
    else:
        selection = {
            'status': 'needs-user-choice',
            'entryPoint': None,
            'reason': '存在多个工程入口，必须由用户或既有约定指定，不能猜测',
            'candidates': [{'type': e['type'], 'path': e['path']} for e in entries],
        }
    selection['deviceCandidates'] = device_candidates
    if not device_candidates:
        selection['deviceStatus'] = 'needs-device'
        selection['deviceReason'] = '没有已启动的模拟器，也没有已配对的真机'
    else:
        selection['deviceStatus'] = 'candidates-available'

    result = {
        'schemaVersion': 1,
        'root': str(root),
        'entryPoints': entries,
        'devices': {'simulators': sim, 'physical': physical},
        'selection': selection,
    }

    out = Path(args.output) if args.output else root / '.ios-environment.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
