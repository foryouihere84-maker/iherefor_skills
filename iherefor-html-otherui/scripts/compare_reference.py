#!/usr/bin/env python3
"""Compare HTML reference and native-app screenshots without changing either input.

判定为三态，且只有 pass 允许放行：

    pass               structuralRatio <= warnStructuralRatio 且 fillRatio <= maxFillRatio
    pass-with-review   warnStructuralRatio < structuralRatio <= maxStructuralRatio
                       —— 或 —— structuralRatio > maxStructuralRatio，但不超过「声明下界」
                       且 fillRatio 合规（reason = structural-within-declared-floor，见下）
    fail               structuralRatio 超出声明下界（未声明下界时即 > maxStructuralRatio），
                       或 fillRatio > maxFillRatio，或两张图尺寸不一致

退出码：0 = pass，1 = fail，2 = pass-with-review。

**声明的结构差异下界（`--expected-structural-floor`）。** 文字密集页的结构差异存在一个
**物理下界**：基准图是在 `scale(1.0229)` 的画布上渲染的，所以基准字形 = 设计字号 × 1.0229；
而尺寸契约明令字号**不得**按比例缩放（见 `references/sizing-and-positioning.md` §2.2）。
两者相差 2.29%，足以让字形边缘的相位差超过 ``--edge-tolerance`` 的配对容差而被判成
``structural`` —— 实测文字类结构差异可达 0.01563，单项就占 0.02 阈值的 78%。
这个下界**不可能靠改代码降到 0**，所以必须由计划显式声明（`gateReachability`），
而不是让 Agent 反复去逼近一个不存在的 0。

传了该值时：结构差异超过 ``--max-structural-ratio`` 但不超过声明下界的，
判 ``pass-with-review``（``reason = structural-within-declared-floor``）。三条边界：

* **只对结构差异开口子。** 平坦区颜色写错与字号无关，`fillRatio` 超标永远判 fail。
* **只降级、不放宽。** 它把 ``fail`` 降为 ``pass-with-review``，不会把任何情况升为 ``pass``；
  实际值**超过**声明下界时仍然判 ``fail`` —— 下界是「不可消除的下界」，不是「豁免额度」。
* **不传则行为完全不变。** 没有 ``--expected-structural-floor``、``--plan`` 里也没有
  ``gateReachability`` 时，判定与旧版逐字一致。

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

**`regions` 与 `attribution` 的分工。** `regions` 是**网格切块**（按 `--grid-rows` /
`--grid-cols` 均分），回答「差在哪一带」；`attribution` 是**具名区域归因**，回答
「差在哪个控件」。后者需要 `--page-facts` 提供 `elements[].rectInReference`：

* 归属规则是**最小包含元素优先**（面积升序），且**互斥且穷尽** ——
  `Σ(区域 changedPixels) + unattributed.changedPixels == 整页 changedPixels`，
  一个像素只会算进一个区域，也不会被悄悄丢掉。
* `declaredUnsupported` 是计划里 `unsupported.items[]` 声明的差异覆盖区（取并集，
  重叠不重复计数）。`residual` 是**扣除它之后**的剩余三类比值 —— 整页比值里混着
  已声明为 `unsupported` 的差异（系统状态栏、无法等价映射的 CSS 特性），不扣除就
  说不清「还剩多少是真缺陷」，那才是 `review.json` 该引用的数字。
* 给不出 `--page-facts`、或事实表没有 `rectInReference` 时，`attribution.status` 记
  `insufficient-evidence` 并写明原因，**不冒充**「归因完成」；`residual` 仍照常给出。
* `attribution` 只增不改：不给 `--page-facts` 时它记 `not-run`，`status` / `exitCode`
  的判定语义与旧版完全一致。
"""

import argparse
import json
import math
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
DEFAULT_REGION_MIN_SIDE = 4   # 归因区域的最小边长（像素），比它小的框量不出归属
MAX_ATTRIBUTION_REGIONS = 255  # 归属图用 'L' 模式承载区域号，故上限 255


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


def region_name(element):
    """具名区域的回退链：``id`` → ``className`` → ``ownText`` → 下标。

    刻意与 ``layout_proportions.region_label`` 保持同一套链而不 import：本脚本要在
    只装了 Pillow 的环境里独立可跑，不引入脚本间的硬依赖。两处改动时需同步。
    """
    for key in ('id', 'className'):
        value = (element.get(key) or '').strip()
        if value:
            return value.split()[0].lstrip('.')[:32]
    text = (element.get('ownText') or '').strip()
    if text:
        return text[:24]
    return f"element_{element.get('index')}"


def reference_regions(page_facts, plan, size):
    """从事实表取出可归因的具名区域，**按面积升序**返回（最具体的排在最前）。

    面积升序是归属规则的一半：先让最小（最具体）的框认领像素，外层容器才拿不到
    已经被子元素认领的部分。返回 ``(regions, reason)``，``reason`` 非空即证据不足。
    """
    width, height = size
    elements = page_facts.get('elements') or []
    if not any(isinstance(e, dict) and 'rectInReference' in e for e in elements):
        return None, ('事实表里没有 rectInReference（需要 schemaVersion 3 的 page-facts.json）：'
                      '无法把差异像素定位到具名区域')

    # 计划里的 region 名是 Agent 确认过的，优先于从 DOM 身份猜出来的名字。
    confirmed = {}
    if isinstance(plan, dict):
        for item in ((plan.get('layoutProportions') or {}).get('regions') or []):
            if isinstance(item, dict) and item.get('index') is not None and item.get('region'):
                confirmed[item['index']] = str(item['region'])

    regions = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        rect = element.get('rectInReference') or {}
        try:
            x = float(rect.get('x', 0))
            y = float(rect.get('y', 0))
            w = float(rect.get('width', 0))
            h = float(rect.get('height', 0))
        except (TypeError, ValueError):
            continue
        x0 = max(0, int(math.floor(x)))
        y0 = max(0, int(math.floor(y)))
        x1 = min(width, int(math.ceil(x + w)))
        y1 = min(height, int(math.ceil(y + h)))
        if (x1 - x0) < DEFAULT_REGION_MIN_SIDE or (y1 - y0) < DEFAULT_REGION_MIN_SIDE:
            continue
        regions.append({
            'region': confirmed.get(element.get('index')) or region_name(element),
            'index': element.get('index'),
            'box': {'x': x0, 'y': y0, 'width': x1 - x0, 'height': y1 - y0},
        })

    if not regions:
        return None, '事实表里没有满足最小尺寸的 rectInReference 区域'
    regions.sort(key=lambda item: (item['box']['width'] * item['box']['height'],
                                   item['box']['y'], item['box']['x']))
    return regions[:MAX_ATTRIBUTION_REGIONS], None


def declared_unsupported_mask(plan, size):
    """计划里 ``unsupported.items[]`` 声明覆盖的像素区（并集）。

    取并集而非逐个累加：两个声明项的范围可能重叠，累加会把同一片像素扣两次。
    没有坐标的声明项进 ``unlocated`` —— 它们**扣不掉**，必须如实说出来，
    而不是当作「已扣除」把 residual 算小。
    """
    width, height = size
    union = None
    located, unlocated = [], []
    if not isinstance(plan, dict):
        return None, located, unlocated
    # unsupported 有两种契约形态：既有 plan 用**数组**（纯文字描述，无坐标，全部
    # 落在 unlocated——扣不掉但必须如实说明）；带坐标的可扣除项用
    # ``{"items": [{...rect/box/rectInReference...}]}``。两种都要能读，不能因为
    # 数组形态就 AttributeError 崩掉 —— 曾有 plan 用数组、脚本却当成 dict 取值。
    unsupported = plan.get('unsupported')
    if isinstance(unsupported, dict):
        items = unsupported.get('items') or []
    elif isinstance(unsupported, list):
        items = unsupported
    else:
        items = []
    for position, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        label = str(item.get('region') or item.get('category')
                    or item.get('reason') or f'item_{position}')
        rect = None
        for key in ('rectInReference', 'box', 'rect'):
            candidate = item.get(key)
            if isinstance(candidate, dict) and candidate.get('width') and candidate.get('height'):
                rect = candidate
                break
        if rect is None:
            unlocated.append(label)
            continue
        try:
            x0 = max(0, int(math.floor(float(rect.get('x', 0)))))
            y0 = max(0, int(math.floor(float(rect.get('y', 0)))))
            x1 = min(width, int(math.ceil(float(rect.get('x', 0)) + float(rect['width']))))
            y1 = min(height, int(math.ceil(float(rect.get('y', 0)) + float(rect['height']))))
        except (TypeError, ValueError):
            unlocated.append(label)
            continue
        if x1 <= x0 or y1 <= y0:
            unlocated.append(label)
            continue
        patch = Image.new('L', size, 0)
        patch.paste(255, (x0, y0, x1, y1))
        union = patch if union is None else ImageChops.lighter(union, patch)
        located.append({'label': label,
                        'box': {'x': x0, 'y': y0, 'width': x1 - x0, 'height': y1 - y0}})
    return union, located, unlocated


def class_stats(image, declared, total_pixels):
    """某一类差异在**扣除已声明区之后**的像素数与占比。"""
    kept = image if declared is None else ImageChops.multiply(image, ImageChops.invert(declared))
    count = kept.histogram()[255]
    return {'pixels': count, 'ratio': round(count / total_pixels, 6)}


def attribute_diff(mask, structural, texture, fill, page_facts, plan, size):
    """把差异像素互斥归属到具名区域，并给出扣除已声明差异后的剩余值。"""
    width, height = size
    total_pixels = width * height
    classes = {'changed': mask, 'structural': structural,
               'texture': texture, 'fill': fill}

    declared, located, unlocated = declared_unsupported_mask(plan, size)
    out = {
        'basis': 'page-facts.json: elements[].rectInReference',
        'assignment': 'exclusive：按面积升序（最小包含元素优先），每个差异像素只归属一个区域',
        'declaredUnsupported': {
            'located': located,
            'unlocated': unlocated,
            'note': ('以下已声明项没有坐标，无法从整页比值里扣除：' + '、'.join(unlocated)
                     + '。要么在计划里补上 rectInReference，要么在 review.json 里显式说明'
                       '它只能人工判定' if unlocated else None),
        },
        'residual': {name: class_stats(image, declared, total_pixels)
                     for name, image in classes.items()},
        'residualNote': ('扣除 declaredUnsupported 覆盖区之后的剩余差异 —— '
                         'review.json 的放行论述应引用这一组数字，而不是整页比值'),
    }

    regions, reason = reference_regions(page_facts, plan, size)
    if regions is None:
        out.update({'status': 'insufficient-evidence', 'reason': reason})
        return out

    # 归属图：像素值 = 区域序号（1 起），0 表示不属于任何区域。
    owner = Image.new('L', size, 0)
    for position, item in enumerate(regions, start=1):
        box = item['box']
        window_box = (box['x'], box['y'], box['x'] + box['width'], box['y'] + box['height'])
        window = owner.crop(window_box)
        free = window.point(lambda value: 255 if value == 0 else 0)
        take = ImageChops.multiply(mask.crop(window_box), free)
        window.paste(position, mask=take)
        owner.paste(window, window_box)

    per_region = []
    for position, item in enumerate(regions, start=1):
        box = item['box']
        window_box = (box['x'], box['y'], box['x'] + box['width'], box['y'] + box['height'])
        selector = owner.crop(window_box).point(lambda value, p=position: 255 if value == p else 0)
        row = dict(item)
        for name, image in classes.items():
            hit = ImageChops.multiply(image.crop(window_box), selector)
            count = hit.histogram()[255]
            row[f'{name}Pixels'] = count
            row[f'{name}PageShare'] = round(count / total_pixels, 6)
        area = max(1, box['width'] * box['height'])
        row['structuralRatio'] = round(row['structuralPixels'] / area, 6)
        row['textureRatio'] = round(row['texturePixels'] / area, 6)
        row['fillRatio'] = round(row['fillPixels'] / area, 6)
        per_region.append(row)

    # 互斥且穷尽：整页各类像素数 - 各区域之和 = 未归属部分。用减法而不是重数一遍，
    # 保证「区域之和 + unattributed == 整页」这条恒等式在数值上永远成立。
    totals = {name: image.histogram()[255] for name, image in classes.items()}
    attributed = {name: sum(row[f'{name}Pixels'] for row in per_region) for name in classes}
    unattributed = {}
    for name in classes:
        missing = totals[name] - attributed[name]
        unattributed[name] = {
            'pixels': missing,
            'ratio': round(missing / total_pixels, 6),
            'shareOfClass': (round(missing / totals[name], 6) if totals[name] else 0.0),
        }

    out.update({
        'status': 'ok',
        'regionCount': len(per_region),
        'regions': per_region,
        'unattributed': unattributed,
        'attributedShare': {
            name: (round(attributed[name] / totals[name], 6) if totals[name] else 1.0)
            for name in classes
        },
        'worstRegions': [
            row for row in sorted(
                per_region,
                key=lambda item: max(item['structuralPageShare'], item['fillPageShare']),
                reverse=True)[:5]
        ],
    })
    return out


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
    ap.add_argument('--page-facts',
                    help='页面事实表；给了才做具名区域归因（attribution）。'
                         '需要 elements[].rectInReference（schemaVersion 3）')
    ap.add_argument('--plan',
                    help='实现计划；可选。用它的 layoutProportions.regions 确认区域名，'
                         '用 unsupported.items 计算扣除后的剩余值，'
                         '并在未显式给出 --expected-structural-floor 时读取 '
                         'gateReachability.expectedStructuralFloor')
    ap.add_argument('--expected-structural-floor', type=float,
                    help='计划声明的结构差异下界。structuralRatio 超过 --max-structural-ratio '
                         '但不超过该值时判 pass-with-review'
                         '（reason=structural-within-declared-floor）。'
                         '它只对结构差异生效，且实际值超过它时仍判 fail。'
                         '不传且计划里也没有 gateReachability 时，判定与旧版完全一致')
    args = ap.parse_args()

    if args.warn_structural_ratio > args.max_structural_ratio:
        ap.error('--warn-structural-ratio 不能大于 --max-structural-ratio')
    if (args.expected_structural_floor is not None
            and args.expected_structural_floor < args.max_structural_ratio):
        ap.error('--expected-structural-floor 不能小于 --max-structural-ratio：'
                 '声明一个低于上限的「下界」没有意义，只会把正常放行也降级')
    if args.grid_rows < 1 or args.grid_cols < 1:
        ap.error('--grid-rows / --grid-cols 必须 >= 1')
    if args.edge_tolerance < 0:
        ap.error('--edge-tolerance 不能为负')

    # 计划只读一次：归因（区域名 / unsupported）与结构下界都从它取。
    plan, plan_error = None, None
    if args.plan:
        try:
            plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            plan_error = f'无法读取 --plan：{error}'

    expected_floor = args.expected_structural_floor
    floor_source = 'cli' if expected_floor is not None else 'none'
    if expected_floor is None and isinstance(plan, dict):
        declared = ((plan.get('gateReachability') or {}).get('expectedStructuralFloor'))
        if isinstance(declared, (int, float)) and not isinstance(declared, bool):
            expected_floor = float(declared)
            floor_source = 'plan'

    reference = Image.open(args.reference).convert('RGBA')
    actual = Image.open(args.actual).convert('RGBA')

    result = {
        'schemaVersion': 3,
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
        # 声明下界在判定前就回显，便于 validate_run 交叉核对「计划声明了没有」。
        'expectedStructuralFloor': expected_floor,
        'expectedStructuralFloorSource': floor_source,
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

    # 具名区域归因是**只增**的：它不进 status / exitCode 的判定，也不改 regions 的语义。
    # 缺 --page-facts 时如实记 not-run，而不是编一份看起来完整的归因。
    if plan_error:
        result.setdefault('warnings', []).append(plan_error)
    if not args.page_facts:
        result['attribution'] = {
            'status': 'not-run',
            'reason': '未提供 --page-facts，只做了网格 regions，未做具名区域归因',
        }
    else:
        try:
            page_facts = json.loads(Path(args.page_facts).read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            result['attribution'] = {
                'status': 'insufficient-evidence',
                'reason': f'无法读取 --page-facts：{error}',
            }
        else:
            result['attribution'] = attribute_diff(
                mask, structural, texture, fill, page_facts, plan, (width, height))

    # 判定只看结构差异与平坦区差异；纹理差异（抗锯齿/字体栅格化）不参与放行判定。
    #
    # 声明的结构下界只降级、不放宽：把 fail 降为 pass-with-review，绝不把任何情况升为 pass。
    # 平坦区颜色写错与字号无关，所以 fillRatio 超标时不适用下界。
    within_floor = expected_floor is not None and structural_ratio <= expected_floor
    if structural_ratio > args.max_structural_ratio:
        if within_floor and fill_ratio <= args.max_fill_ratio:
            status, reason, code = 'pass-with-review', 'structural-within-declared-floor', 2
        else:
            status, reason, code = 'fail', 'structural-diff-exceeded', 1
    elif fill_ratio > args.max_fill_ratio:
        status, reason, code = 'fail', 'fill-diff-exceeded', 1
    elif structural_ratio > args.warn_structural_ratio:
        status, reason, code = 'pass-with-review', 'structural-diff-above-warn', 2
    else:
        status, reason, code = 'pass', None, 0

    result['declaredStructuralFloor'] = {
        'value': expected_floor,
        'source': floor_source,
        'maxStructuralRatio': args.max_structural_ratio,
        'withinFloor': within_floor if expected_floor is not None else None,
        'headroom': (round(expected_floor - structural_ratio, 6)
                     if expected_floor is not None else None),
        'note': ('下界是「不可消除的下界」，不是「豁免额度」：只对结构差异生效，'
                 '实际值超过它仍判 fail，也不会把任何情况升为 pass'
                 if expected_floor is not None else
                 '未声明结构差异下界，判定与旧版一致'),
    }
    result.update({'status': status, 'exitCode': code})
    if reason:
        result['reason'] = reason
    return emit(result, code)


if __name__ == '__main__':
    raise SystemExit(main())
