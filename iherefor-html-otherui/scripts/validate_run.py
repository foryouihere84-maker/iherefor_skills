#!/usr/bin/env python3
"""校验一次 run 是否满足 references/artifact-contract.md 的产物契约。

只读取 run 目录，不修改任何文件。契约以 artifact-contract.md 为准，本脚本是其
可执行版本：文档改了，这里必须同步改，`scripts/tests/` 下有对应回归。

用法：
    python3 scripts/validate_run.py --run <run-dir> [--json <out-path>]

退出码：0 = 满足契约；1 = 违反契约；2 = 用法或读取错误。
"""
import argparse
import json
import struct
import sys
from pathlib import Path

ALLOWED_STATUS = ('pass', 'pass-with-review', 'fail', 'not-run')
IOS_MODES = ('ios-swiftui', 'ios-uikit-swift', 'ios-uikit-objective-c')
ANDROID_MODES = ('android-compose-kotlin', 'android-views-kotlin', 'android-views-java')
KNOWN_MODES = IOS_MODES + ANDROID_MODES

BASE_REQUIRED = (
    'run.json',
    'review.json',
    'delivery-gate.json',
    'ui-implementation-plan.json',
    'resource-policy.json',
    'runtime-device.json',
    'actual',
    'diff',
)
GATE_KEYS = ('reference', 'browser', 'sourceAssets', 'implementation', 'build', 'tests', 'visualDiff')
RUN_REQUIRED_KEYS = ('schemaVersion', 'runId', 'pageId', 'targetMode', 'status', 'referenceBaseline')

# 降采样/裁剪派生图的文件名特征：一旦出现在 diff 输入里，比较结果就不再是原始证据。
DERIVED_MARKERS = ('reference-size', 'reference_size', 'resized', 'rescale', 'scaled',
                   'downscaled', 'down-sample', 'thumbnail', 'thumb', '-copy', '-resize')


def png_size(path):
    """从 PNG 头读取像素尺寸，不依赖 Pillow。"""
    try:
        with open(path, 'rb') as handle:
            head = handle.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    width, height = struct.unpack('>II', head[16:24])
    return {'width': width, 'height': height}


def load_json(path):
    """读取 JSON，失败时返回 (None, 错误信息)。"""
    try:
        return json.loads(path.read_text()), None
    except Exception as exc:
        return None, str(exc)


def computed_delivery_ready(gate):
    statuses = gate.get('status') or {}
    if any(statuses.get(key) != 'pass' for key in GATE_KEYS):
        return False
    unsupported = gate.get('unsupported') or {}
    return unsupported.get('count') == unsupported.get('reviewedCount')


def validate(run_dir):
    violations = []
    warnings = []
    run_json_path = run_dir / 'run.json'

    if not run_dir.is_dir():
        return {'ok': False, 'violations': [f'run 目录不存在：{run_dir}'], 'warnings': []}, 2

    if not run_json_path.is_file():
        return {'ok': False, 'violations': ['缺少 run.json，无法判定目标模式与是否 legacy'], 'warnings': []}, 1

    run, error = load_json(run_json_path)
    if run is None:
        return {'ok': False, 'violations': [f'run.json 解析失败：{error}'], 'warnings': []}, 1

    for key in RUN_REQUIRED_KEYS:
        if key not in run:
            violations.append(f'run.json 缺少字段：{key}')

    target_mode = run.get('targetMode')
    if target_mode and target_mode not in KNOWN_MODES:
        violations.append(f'未知 targetMode：{target_mode}')

    legacy = bool(run.get('legacy'))
    if legacy:
        warnings.append('run.json 标记 legacy：跳过产物必需项检查（不得据此把页面判为 ready）')
        return {'ok': True, 'legacy': True, 'violations': violations, 'warnings': warnings}, 0

    required = list(BASE_REQUIRED)
    if target_mode in IOS_MODES:
        required.append('ios-environment.json')
    for name in required:
        if not (run_dir / name).exists():
            violations.append(f'缺少必需产物：{name}')

    gate_path = run_dir / 'delivery-gate.json'
    if gate_path.is_file():
        gate, error = load_json(gate_path)
        if gate is None:
            violations.append(f'delivery-gate.json 解析失败：{error}')
        else:
            statuses = gate.get('status') or {}
            for key in GATE_KEYS:
                if key not in statuses:
                    violations.append(f'delivery-gate.status 缺少字段：{key}')
                elif statuses[key] not in ALLOWED_STATUS:
                    violations.append(f'delivery-gate.status.{key} 取值非法：{statuses[key]!r}')
            unsupported = gate.get('unsupported')
            if not isinstance(unsupported, dict):
                violations.append('delivery-gate 缺少 unsupported 计数对象')
            else:
                for key in ('count', 'reviewedCount'):
                    if not isinstance(unsupported.get(key), int):
                        violations.append(f'delivery-gate.unsupported.{key} 必须是整数')
            expected = computed_delivery_ready(gate)
            if gate.get('deliveryReady') is not expected:
                violations.append(
                    f'deliveryReady 与契约推导不一致：记录 {gate.get("deliveryReady")!r}，应为 {expected!r}'
                )
            if gate.get('deliveryReady') is False and not gate.get('blockingReasons'):
                violations.append('deliveryReady=false 时必须在 blockingReasons 中说明原因')

    # 基准必须与目标设备截图同源：点尺寸来自运行时 API，像素尺寸必须一致
    page_dir = run_dir.parent.parent
    baseline = page_dir / 'reference' / 'reference.png'
    device_size = None
    device_path = run_dir / 'runtime-device.json'
    if device_path.is_file():
        device, error = load_json(device_path)
        if device is None:
            violations.append(f'runtime-device.json 解析失败：{error}')
        else:
            candidate = device.get('screenshotPixels')
            if not isinstance(candidate, dict) or not candidate.get('width') or not candidate.get('height'):
                violations.append('runtime-device.json 缺少 screenshotPixels')
            else:
                device_size = candidate

    if not baseline.is_file():
        violations.append('缺少页面级已批准基准：reference/reference.png')
    elif device_size:
        size = png_size(baseline)
        if size is None:
            violations.append('reference/reference.png 不是可解析的 PNG')
        elif size['width'] != device_size['width'] or size['height'] != device_size['height']:
            violations.append(
                f"基准图与设备截图不同源：reference.png {size['width']}x{size['height']} "
                f"vs screenshotPixels {device_size['width']}x{device_size['height']}"
            )

    # diff 输入必须是已批准基准与本次 run 的原始截图，禁止降采样/裁剪派生图
    diff_dir = run_dir / 'diff'
    if diff_dir.is_dir():
        for summary_path in sorted(diff_dir.glob('*.json')):
            summary, error = load_json(summary_path)
            if summary is None:
                violations.append(f'{summary_path.name} 解析失败：{error}')
                continue
            for key in ('reference', 'actual'):
                value = summary.get(key)
                if not value:
                    continue
                candidate = Path(value)
                if any(marker in candidate.name.lower() for marker in DERIVED_MARKERS):
                    violations.append(f'{summary_path.name} 的 {key} 使用了派生图：{candidate.name}')
                if key == 'reference' and baseline.is_file() and candidate.resolve() != baseline.resolve():
                    violations.append(f'{summary_path.name} 的 reference 不是已批准基准：{value}')
                if key == 'actual' and run_dir not in candidate.resolve().parents:
                    violations.append(f'{summary_path.name} 的 actual 不在本次 run 目录内：{value}')

    payload = {
        'schemaVersion': 1,
        'run': str(run_dir),
        'runId': run.get('runId'),
        'targetMode': target_mode,
        'legacy': legacy,
        'ok': not violations,
        'violations': violations,
        'warnings': warnings,
    }
    return payload, (0 if not violations else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run', required=True, help='run 目录，例如 .ihereforUI/pages/<page-id>/runs/<run-id>')
    ap.add_argument('--json', help='把结果同时写入该路径')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    payload, code = validate(Path(args.run).resolve())
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')
    if not args.quiet:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
