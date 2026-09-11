#!/usr/bin/env python3
"""Compare HTML reference and native-app screenshots without changing either input.

判定为三态，且只有 pass 允许放行：

    pass               changedRatio <= warn-changed-ratio
    pass-with-review   warn-changed-ratio < changedRatio <= max-changed-ratio
    fail               changedRatio > max-changed-ratio，或两张图尺寸不一致

退出码：0 = pass，1 = fail，2 = pass-with-review。

注意 ``--threshold`` 是**单像素颜色容差**（0-255），不是差异比例阈值；
决定是否放行的是 ``--max-changed-ratio``。尺寸不一致一律 fail——比较器不接受
缩放或裁剪过的派生图，它不会把「缩放到同一尺寸」当作通过。
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops

DEFAULT_WARN_RATIO = 0.005
DEFAULT_MAX_RATIO = 0.02


def changed_pixel_count(reference, actual, threshold):
    """统计「最大通道差 > threshold」的像素数。

    逐波段 point 二值化后用 lighter 合并，再取直方图峰值桶，语义与逐像素
    ``max(pixel) > threshold`` 完全一致，但计算发生在 C 层，避免 Python 双层
    循环在大截图上耗时数十秒。
    """
    diff = ImageChops.difference(reference, actual)
    mask = None
    for band in diff.split():
        hit = band.point(lambda value, t=threshold: 255 if value > t else 0)
        mask = hit if mask is None else ImageChops.lighter(mask, hit)
    return mask.histogram()[255]


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument('--reference', required=True)
    ap.add_argument('--actual', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--threshold', type=int, default=8,
                    help='单像素颜色容差 0-255，不是差异比例阈值（默认 8）')
    ap.add_argument('--warn-changed-ratio', type=float, default=DEFAULT_WARN_RATIO,
                    help=f'差异比例告警线，超过判 pass-with-review（默认 {DEFAULT_WARN_RATIO}）')
    ap.add_argument('--max-changed-ratio', type=float, default=DEFAULT_MAX_RATIO,
                    help=f'差异比例上限，超过判 fail（默认 {DEFAULT_MAX_RATIO}）')
    args = ap.parse_args()

    if args.warn_changed_ratio > args.max_changed_ratio:
        ap.error('--warn-changed-ratio 不能大于 --max-changed-ratio')

    reference = Image.open(args.reference).convert('RGBA')
    actual = Image.open(args.actual).convert('RGBA')

    result = {
        'schemaVersion': 1,
        'reference': str(Path(args.reference).resolve()),
        'actual': str(Path(args.actual).resolve()),
        'referenceSize': {'width': reference.size[0], 'height': reference.size[1]},
        'actualSize': {'width': actual.size[0], 'height': actual.size[1]},
        'threshold': args.threshold,
        'warnChangedRatio': args.warn_changed_ratio,
        'maxChangedRatio': args.max_changed_ratio,
    }

    def emit(payload, code):
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + '\n')
        print(json.dumps(payload, indent=2))
        return code

    if reference.size != actual.size:
        result.update({'status': 'fail', 'reason': 'size-mismatch', 'exitCode': 1,
                       'detail': '两张图尺寸不同，禁止用缩放/裁剪后的派生图参与比较'})
        return emit(result, 1)

    changed = changed_pixel_count(reference, actual, args.threshold)
    total = reference.size[0] * reference.size[1]
    ratio = changed / total if total else 0.0

    if ratio > args.max_changed_ratio:
        status, reason, code = 'fail', 'changed-ratio-exceeded', 1
    elif ratio > args.warn_changed_ratio:
        status, reason, code = 'pass-with-review', 'changed-ratio-above-warn', 2
    else:
        status, reason, code = 'pass', None, 0

    result.update({
        'status': status,
        'changedPixels': changed,
        'totalPixels': total,
        'changedRatio': ratio,
        'exitCode': code,
    })
    if reason:
        result['reason'] = reason
    return emit(result, code)


if __name__ == '__main__':
    raise SystemExit(main())
