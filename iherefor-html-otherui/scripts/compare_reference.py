#!/usr/bin/env python3
"""Compare HTML reference and native-app screenshots without changing either input.

判定为三态，且只有 pass 允许放行：

    pass               structuralRatio <= warnStructuralRatio 且 fillRatio <= maxFillRatio
    pass-with-review   warnStructuralRatio < structuralRatio <= maxStructuralRatio
    fail               structuralRatio > maxStructuralRatio，或 fillRatio > maxFillRatio，
                       或两张图尺寸不一致

退出码：0 = pass，1 = fail，2 = pass-with-review。

**为什么阈值不直接加在 changedRatio 上。** 原始 changedRatio 把几类完全不同的差异
混在一起。同一套几何形状因为字体栅格化、抗锯齿、次像素相位差而像素值不同 —— 这是
噪点；几何错位、尺寸变化、间距改错 —— 这是真缺陷；平坦区颜色写错 —— 这既不是噪点
也不是几何问题。把阈值加在混合值上会双输：抗锯齿多的页面（尤其是 HTML 侧用 Web
字体、App 侧用系统字体）会一直撞上限而无法交付，而真正错位的图只要背景色接近也可能
因为纹理差异低而侥幸通过。所以必须先把差异分类，再只对「真缺陷」那几类设阈值。

**三分法（互斥且穷尽）。** 记 ``E`` 为强边图（梯度 >= ``--edge-threshold``）：

* ``structural`` = 差异 ∩ **位移区**：某张图的强边在另一张图里 ``--edge-tolerance``
  像素范围内**找不到对应**。几何错位、尺寸变化、圆角/间距改错属于这类 —— 真缺陷。
* ``fill``       = 差异 ∩ **平坦区**：两张图的梯度都低于 ``--flat-threshold``，即
  纯色块内部。填充色/背景色写错、文字颜色写错、整块缺少遮罩属于这类 —— 真缺陷。
  它不产生边缘，结构差异抓不到；又不是噪点，不能放过。
* ``texture``    = 剩下的差异：位于有内容的区域、但强边位置上对得上 —— 字体栅格化、
  抗锯齿、次像素相位差。这是噪点，不参与放行判定。

**为什么结构差异必须用「最近邻配对」，不能比较膨胀后的边缘集合。** 两种看似合理的
写法都是错的：

1. 「差异落在任一方的边缘带上即结构差异」。抗锯齿差异本身就长在边缘上，所以这条
   规则把字体替换（HTML 用 Web 字体、App 用系统字体）产生的全部差异算成结构差异，
  页面永远无法交付。
2. 「膨胀后的边缘集合求 XOR」。膨胀只是把集合往外扩，**平移过的集合和原集合求 XOR
   永远非空**，哪怕只挪了 0.1 像素。结果是任何次像素相位差都被判成几何错位。

正确做法是配对：对每条强边，看另一张图在 ``--edge-tolerance`` 内**有没有**对应的边。
``tolerance`` 因此有了明确语义 —— 它划定了「多小的边缘移动算栅格化噪声」与「多大的
移动算几何错位」的分界线。默认 1 像素；在 scale 3 的截图上即 0.33pt，远小于契约要求
的 2pt 位置容差。

另需注意 ``fill`` 不能简单地定义为「两张图都没有强边」：强边阈值是 64，而抗锯齿斜坡
的梯度常落在 16-64 之间，这些像素既不是强边也不是纯色 —— 若按「无强边」算平坦区，
抗锯齿差异会被误算成填充差异。所以平坦区用**低阈值**（``--flat-threshold``）判定。

``--threshold`` 是**单像素颜色容差**（0-255），不是差异比例阈值；决定是否放行的是
``--max-structural-ratio`` / ``--max-fill-ratio``。尺寸不一致一律 fail —— 比较器不
接受缩放或裁剪过的派生图，它不会把「缩放到同一尺寸」当作通过。
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

DEFAULT_WARN_RATIO = 0.005
DEFAULT_MAX_RATIO = 0.02
DEFAULT_MAX_FILL_RATIO = 0.02
DEFAULT_EDGE_THRESHOLD = 64   # 梯度达到多少算强边（0-255）
DEFAULT_FLAT_THRESHOLD = 16   # 梯度低于多少算平坦区（0-255）
DEFAULT_EDGE_TOLERANCE = 2    # 强边移动多少像素以内仍算同一条边（标定见 tests/test_compare_reference.py）
DEFAULT_GRID_ROWS = 6
DEFAULT_GRID_COLS = 1


def changed_mask(reference, actual, threshold):
    """「最大通道差 > threshold」的二值掩膜（255 = 差异像素）。

    逐波段 point 二值化后用 lighter 合并，语义与逐像素 ``max(pixel) > threshold``
    完全一致，但计算发生在 C 层，避免 Python 双层循环在大截图上耗时数十秒。
    """
    diff = ImageChops.difference(reference, actual)
    mask = None
    for band in diff.split():
        hit = band.point(lambda value, t=threshold: 255 if value > t else 0)
        mask = hit if mask is None else ImageChops.lighter(mask, hit)
    return mask


def gradient_map(*images):
    """任一方的梯度幅度图（'L'）。"""
    union = None
    for image in images:
        edges = image.convert('L').filter(ImageFilter.FIND_EDGES)
        union = edges if union is None else ImageChops.lighter(union, edges)
    return union


def binarize(gradient, threshold):
    """梯度图按阈值二值化成 0/255（'L'）。"""
    return gradient.point(lambda value, t=threshold: 255 if value >= t else 0)


def dilate(mask, radius):
    """二值图的方形膨胀。``radius`` <= 0 时原样返回。"""
    for _ in range(max(0, radius)):
        mask = mask.filter(ImageFilter.MaxFilter(3))
    return mask


def misplaced_edges(reference, actual, threshold, tolerance):
    """强边「找不到对应」的区域（已膨胀），是结构差异的候选区。

    对每条强边，只要另一张图在 ``tolerance`` 像素内有边，就认为这条边只是被重新
    栅格化；找不到才说明它真的移动了。注意不能用两边的膨胀集合求 XOR —— 平移过的
    集合和原集合求 XOR 永远非空，会让任何次像素相位差都被判成几何错位。
    """
    ref_strong = binarize(reference.convert('L').filter(ImageFilter.FIND_EDGES), threshold)
    act_strong = binarize(actual.convert('L').filter(ImageFilter.FIND_EDGES), threshold)
    ref_only = ImageChops.subtract(ref_strong, dilate(act_strong, tolerance))
    act_only = ImageChops.subtract(act_strong, dilate(ref_strong, tolerance))
    # 膨胀一圈：两条错开的边之间的过渡带也算结构差异，否则只有边线本身被抓到。
    return dilate(ImageChops.lighter(ref_only, act_only), tolerance + 1)


def content_map(*images, low, tolerance):
    """「这里不是纯色块」。用低阈值判定，把抗锯齿斜坡也算作有内容。

    ``tolerance`` 只用于结构差异的边配对，**不**用来膨胀内容图：内容图一膨胀，
    细笔画（几像素高的文字）就会整条被划进「有内容」，于是「文字颜色写错」这种纯
    颜色缺陷会被算成纹理差异而放过。抗锯齿斜坡本身已经由低阈值覆盖，不需要膨胀。
    """
    return binarize(gradient_map(*images), low)


def split_diff(mask, reference, actual, edge_threshold, flat_threshold, tolerance,
               content_dilate=0):
    """把差异掩膜拆成 ``(structural, texture, fill)`` 三张互斥且穷尽的二值图。"""
    structural = ImageChops.multiply(
        mask, misplaced_edges(reference, actual, edge_threshold, tolerance))
    rest = ImageChops.subtract(mask, structural)
    content = content_map(reference, actual, low=flat_threshold, tolerance=tolerance)
    if content_dilate > 0:
        content = dilate(content, content_dilate)
    fill = ImageChops.multiply(rest, ImageChops.invert(content))
    texture = ImageChops.subtract(rest, fill)
    return structural, texture, fill


def ratio_of(mask, box=None):
    """掩膜中 255 像素的占比。``box`` 给定时只统计该区域。"""
    if box is not None:
        mask = mask.crop(box)
    total = mask.size[0] * mask.size[1]
    if total <= 0:
        return 0.0, 0, 0
    count = mask.histogram()[255]
    return count / total, count, total


def region_stats(mask, structural, texture, fill, rows, cols, size):
    """按网格给出每格的差异明细，用于把「差在哪」从整页数值细化到具体区域。"""
    width, height = size
    regions = []
    row_height = height / rows
    col_width = width / cols
    for row in range(rows):
        for col in range(cols):
            box = (int(col * col_width), int(row * row_height),
                   int(min(width, (col + 1) * col_width)), int(min(height, (row + 1) * row_height)))
            if box[2] - box[0] <= 0 or box[3] - box[1] <= 0:
                continue
            changed_ratio, changed_px, total_px = ratio_of(mask, box)
            regions.append({
                'row': row, 'col': col, 'box': {'x': box[0], 'y': box[1],
                                                'width': box[2] - box[0], 'height': box[3] - box[1]},
                'pixels': total_px,
                'changedRatio': round(changed_ratio, 6),
                'structuralRatio': round(ratio_of(structural, box)[0], 6),
                'textureRatio': round(ratio_of(texture, box)[0], 6),
                'fillRatio': round(ratio_of(fill, box)[0], 6),
                'changedPixels': changed_px,
            })
    return regions


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument('--reference', required=True)
    ap.add_argument('--actual', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--threshold', type=int, default=8,
                    help='单像素颜色容差 0-255，不是差异比例阈值（默认 8）')
    ap.add_argument('--warn-structural-ratio', type=float, default=DEFAULT_WARN_RATIO,
                    help=f'结构差异告警线，超过判 pass-with-review（默认 {DEFAULT_WARN_RATIO}）')
    ap.add_argument('--max-structural-ratio', type=float, default=DEFAULT_MAX_RATIO,
                    help=f'结构差异上限，超过判 fail（默认 {DEFAULT_MAX_RATIO}）')
    ap.add_argument('--max-fill-ratio', type=float, default=DEFAULT_MAX_FILL_RATIO,
                    help=f'平坦区颜色差异上限，超过判 fail（默认 {DEFAULT_MAX_FILL_RATIO}）')
    ap.add_argument('--edge-threshold', type=int, default=DEFAULT_EDGE_THRESHOLD,
                    help=f'梯度达到多少算强边，0-255（默认 {DEFAULT_EDGE_THRESHOLD}）')
    ap.add_argument('--flat-threshold', type=int, default=DEFAULT_FLAT_THRESHOLD,
                    help=f'梯度低于多少算平坦区，0-255（默认 {DEFAULT_FLAT_THRESHOLD}）')
    ap.add_argument('--edge-tolerance', type=int, default=DEFAULT_EDGE_TOLERANCE,
                    help='强边移动多少像素以内仍算同一条边（默认 '
                         f'{DEFAULT_EDGE_TOLERANCE}）—— 即「栅格化噪声」与「几何错位」的分界线')
    ap.add_argument('--grid-rows', type=int, default=DEFAULT_GRID_ROWS,
                    help=f'区域统计的行数（默认 {DEFAULT_GRID_ROWS}）')
    ap.add_argument('--grid-cols', type=int, default=DEFAULT_GRID_COLS,
                    help=f'区域统计的列数（默认 {DEFAULT_GRID_COLS}）')
    args = ap.parse_args()

    if args.warn_structural_ratio > args.max_structural_ratio:
        ap.error('--warn-structural-ratio 不能大于 --max-structural-ratio')
    if args.grid_rows < 1 or args.grid_cols < 1:
        ap.error('--grid-rows / --grid-cols 必须 >= 1')
    if args.edge_tolerance < 0:
        ap.error('--edge-tolerance 不能为负')

    reference = Image.open(args.reference).convert('RGBA')
    actual = Image.open(args.actual).convert('RGBA')

    result = {
        'schemaVersion': 2,
        'reference': str(Path(args.reference).resolve()),
        'actual': str(Path(args.actual).resolve()),
        'referenceSize': {'width': reference.size[0], 'height': reference.size[1]},
        'actualSize': {'width': actual.size[0], 'height': actual.size[1]},
        'threshold': args.threshold,
        'edgeThreshold': args.edge_threshold,
        'flatThreshold': args.flat_threshold,
        'edgeTolerance': args.edge_tolerance,
        'warnStructuralRatio': args.warn_structural_ratio,
        'maxStructuralRatio': args.max_structural_ratio,
        'maxFillRatio': args.max_fill_ratio,
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

    mask = changed_mask(reference, actual, args.threshold)
    structural, texture, fill = split_diff(mask, reference, actual,
                                           args.edge_threshold, args.flat_threshold,
                                           args.edge_tolerance)

    ratio, changed, total = ratio_of(mask)
    structural_ratio, structural_px, _ = ratio_of(structural)
    texture_ratio, texture_px, _ = ratio_of(texture)
    fill_ratio, fill_px, _ = ratio_of(fill)
    width, height = reference.size

    result.update({
        'changedPixels': changed,
        'totalPixels': total,
        'changedRatio': ratio,
        'structuralChangedPixels': structural_px,
        'structuralRatio': structural_ratio,
        'textureChangedPixels': texture_px,
        'textureRatio': texture_ratio,
        'fillChangedPixels': fill_px,
        'fillRatio': fill_ratio,
        'regions': region_stats(mask, structural, texture, fill,
                                args.grid_rows, args.grid_cols, (width, height)),
    })
    worst = sorted(result['regions'],
                   key=lambda item: max(item['structuralRatio'], item['fillRatio']),
                   reverse=True)[:5]
    result['worstRegions'] = [dict(item) for item in worst if
                              item['structuralRatio'] > args.warn_structural_ratio
                              or item['fillRatio'] > args.max_fill_ratio]

    # 判定只看结构差异与平坦区差异；纹理差异（抗锯齿/字体栅格化）不参与放行判定。
    if structural_ratio > args.max_structural_ratio:
        status, reason, code = 'fail', 'structural-diff-exceeded', 1
    elif fill_ratio > args.max_fill_ratio:
        status, reason, code = 'fail', 'fill-diff-exceeded', 1
    elif structural_ratio > args.warn_structural_ratio:
        status, reason, code = 'pass-with-review', 'structural-diff-above-warn', 2
    else:
        status, reason, code = 'pass', None, 0

    result.update({'status': status, 'exitCode': code})
    if reason:
        result['reason'] = reason
    return emit(result, code)


if __name__ == '__main__':
    raise SystemExit(main())
