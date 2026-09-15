#!/usr/bin/env python3
"""多宽度采样的**几何**契约审计：平板/大屏适配的运行期那一半。

**它不做像素比对，这是刻意的。** Lanhu 只提供一份设计稿，其几何基准是某一台设备的
`rowDims`；拿它直接比 iPad 是拿两个不同画布比对，是**证据类型不匹配**。所以平板这一关
断言的是**几何关系**，输入是各采样的几何转储（``actual/geometry-<sample-id>.json``），不是截图。

八项检查里，``sizeInvariance`` 是最有价值的一项：它把「尺寸不缩放」这条最核心的契约
从文档口号变成可执行断言 —— 同一个 ``fixed`` 元素在 iPhone 与 iPad 上的点值必须逐字相等。
平板适配里最典型的缺陷（整页等比放大 1.5 倍）会让它立刻炸出来，而像素 diff 在
「基准只有一份」的前提下根本发现不了。

``sampleCoverage`` 缺必需采样时判 ``fail`` 而不是 ``pass``：缺采样会让其余七项
「全绿」，那是**假绿** —— 少一个采样不等于多一份放心。

用法：
    python3 scripts/audit_adaptive.py --targets <run>/adaptive-targets.json
    python3 scripts/audit_adaptive.py --targets <run>/adaptive-targets.json \
        --plan <run>/ui-implementation-plan.json \
        --output <run>/diff/adaptive-audit.json

退出码：0 = 通过；1 = 存在违规；2 = 用法或读取错误。
"""
import argparse
import json
import sys
from pathlib import Path

CAPPING_POLICIES = ('max-content-width', 'centered-column')
# 平台最小点击区。几何转储可以显式给 touchTargetMinimum 覆盖，缺省按平台推。
PLATFORM_TOUCH_MINIMUM = {'ios': 44.0, 'android': 48.0}
DEFAULT_TOUCH_MINIMUM = 44.0
# 「逐字相等」的判定留一点浮点噪声余量：值来自运行时 NSLog，格式化后可能有末位差。
# 这个余量刻意远小于任何真实缺陷的幅度（等比放大 1.5 倍会差几十 pt），
# 所以它不会把「真的被缩放了」放过去。
EXACT_EPSILON = 1e-3


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8')), None
    except Exception as exc:  # noqa: BLE001 - 读取失败的原因原样上报
        return None, str(exc)


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def rect_of(element):
    rect = element.get('rect')
    if not isinstance(rect, dict):
        return None
    for key in ('x', 'y', 'width', 'height'):
        if not is_number(rect.get(key)):
            return None
    return {key: float(rect[key]) for key in ('x', 'y', 'width', 'height')}


def element_id(element):
    return element.get('id') or element.get('region') or '<unnamed>'


def failure(kind, detail, **extra):
    item = {'kind': kind, 'detail': detail}
    item.update({key: value for key, value in extra.items() if value is not None})
    return item


def overlaps(a, b):
    return not (a['x'] + a['width'] <= b['x'] or b['x'] + b['width'] <= a['x']
                or a['y'] + a['height'] <= b['y'] or b['y'] + b['height'] <= a['y'])


# 「设备平台」维度（phone/tablet）与「窗口宽度档」（compact/medium/expanded）是**正交**的：
# 前者回答「照哪套稿的尺寸/字号」，后者回答「父视图变宽时内容怎么收敛」。
# sizeInvariance 的「尺寸不缩放」铁律作用域是**同一设备内**——同一台 phone 的多个宽度采样、
# 或同一台 tablet 的多个宽度采样之间，fixed 尺寸必须逐字相等；跨设备（phone vs tablet）
# 的差异才允许走 sizeVariants 分档（此时有 xx 与 xx-iPad 两份稿，照各自稿还原）。
DEVICE_CLASSES = ('phone', 'tablet')


def infer_device_class(sample_id, device, device_class):
    """推断采样的「设备平台」（phone / tablet），优先级从高到低：

    1. 显式 ``deviceClass``（phone / tablet）—— 最权威；
    2. ``sample_id`` 前缀（``phone-*`` / ``tablet-*`` / ``pad-*`` / 含 ``ipad``）；
    3. 具体设备型号名（``device`` 字段，如 ``iPhone 17`` / ``iPad Pro ...``）。

    三者都没有时返回 ``None`` —— 此时 sizeInvariance 退化为「全采样一致」的旧口径，
    向后兼容没有声明设备维度、也没有用 phone-/tablet- 前缀命名的老素材。
    """
    if device_class in DEVICE_CLASSES:
        return device_class
    sid = (sample_id or '').lower()
    if 'phone' in sid:
        return 'phone'
    if 'tablet' in sid or sid.startswith('pad') or 'ipad' in sid:
        return 'tablet'
    if isinstance(device, str):
        dev = device.lower()
        if 'iphone' in dev or 'pixel' in dev or 'galaxy' in dev or 'android phone' in dev:
            return 'phone'
        if 'ipad' in dev or 'tablet' in dev or 'fold' in dev or 'android tablet' in dev:
            return 'tablet'
    return None


class Sample:
    """一个宽度采样的几何转储。"""

    def __init__(self, sample_id, width_class, window, document, path,
                 platform=None, device=None):
        self.id = sample_id
        self.width_class = width_class
        self.window = window
        self.document = document
        self.path = path
        self.platform = platform
        self.device = device
        self.elements = [item for item in (document.get('elements') or [])
                         if isinstance(item, dict)]
        self.by_id = {element_id(item): item for item in self.elements}

    @property
    def window_width(self):
        return float((self.window or {}).get('width') or 0)

    @property
    def window_height(self):
        return float((self.window or {}).get('height') or 0)

    def touch_minimum(self):
        declared = self.document.get('touchTargetMinimum')
        if is_number(declared):
            return float(declared)
        return PLATFORM_TOUCH_MINIMUM.get((self.platform or '').lower(),
                                          DEFAULT_TOUCH_MINIMUM)


def resolve_geometry_path(raw, base_dir, override=False):
    """把几何转储路径解析成绝对路径。

    targets 里声明的路径是**相对 targets 文件所在目录**的（契约示例写的是
    ``actual/geometry-<sample-id>.json``，那是 run 目录下的相对路径）；
    命令行 ``--geometry NAME=PATH`` 是用户当场给的，按当前工作目录解析。
    不区分这两者的话，从别的目录调用就会整批读不到 —— 而报出来的错是
    「必需采样缺几何证据」，看起来像素材缺失，其实是路径基准搞错了。
    """
    path = Path(raw)
    if path.is_absolute():
        return path
    return (Path.cwd() if override else base_dir) / path


def resolve_samples(targets, geometry_overrides, base_dir):
    """按 targets 的声明装载采样。返回 (samples, failures, warnings)。

    ``geometry`` 缺省取 targets 里声明的路径；``--geometry NAME=PATH`` 可逐项覆盖
    （便于从别处取证据，或在回归测试里喂固定素材）。
    """
    failures = []
    warnings = []
    samples = []
    platform = targets.get('platform')
    for index, entry in enumerate(targets.get('samples') or []):
        if not isinstance(entry, dict):
            failures.append(failure('sample-not-object', f'samples[{index}] 必须是对象'))
            continue
        sample_id = entry.get('id')
        if not sample_id:
            failures.append(failure('sample-missing-id', f'samples[{index}] 缺少 id'))
            continue
        required = entry.get('required', True) is not False
        override_path = geometry_overrides.get(sample_id)
        raw = override_path or entry.get('geometry')
        if not raw:
            if required:
                failures.append(failure(
                    'sample-missing-geometry',
                    f'必需采样 {sample_id!r} 没有 geometry 路径：'
                    '没有几何证据，其余七项检查会在缺采样的情况下「全绿」——那是假绿',
                    sample=sample_id))
            else:
                warnings.append(f'可选采样 {sample_id!r} 没有 geometry 路径，已跳过')
            continue
        path = resolve_geometry_path(raw, base_dir, override=bool(override_path))
        document, error = load_json(path)
        if document is None:
            if required:
                failures.append(failure(
                    'sample-geometry-unreadable',
                    f'必需采样 {sample_id!r} 的几何转储读取失败：{error}',
                    sample=sample_id, evidence=str(path)))
            else:
                warnings.append(f'可选采样 {sample_id!r} 的几何转储读取失败：{error}')
            continue
        if not isinstance(document, dict):
            failures.append(failure(
                'sample-geometry-not-object',
                f'采样 {sample_id!r} 的几何转储必须是 JSON 对象',
                sample=sample_id))
            continue
        window = document.get('windowBoundsPoints') or entry.get('windowBoundsPoints')
        width_class = (entry.get('widthClass')
                       or document.get('widthClass')
                       or 'compact')
        device = infer_device_class(sample_id, entry.get('device'),
                                    entry.get('deviceClass'))
        samples.append(Sample(sample_id, width_class, window, document, str(path),
                              entry.get('platform') or platform, device))
    return samples, failures, warnings


def resolve_kind(element, plan_kinds):
    kind = element.get('kind')
    if isinstance(kind, str) and kind:
        return kind
    return plan_kinds.get(element_id(element))


def plan_region_kinds(plan):
    """从计划取「区域 → 关系类型」的映射，供几何转储省略 ``kind`` 时回退。"""
    kinds = {}
    if not isinstance(plan, dict):
        return kinds
    proportions = plan.get('layoutProportions')
    if not isinstance(proportions, dict):
        return kinds
    for region in proportions.get('regions') or []:
        if not isinstance(region, dict):
            continue
        name = region.get('region')
        if not name:
            continue
        declared = {relation.get('kind') for relation in (region.get('relations') or [])
                    if isinstance(relation, dict)}
        for candidate in ('fixed', 'pinned', 'intrinsic', 'proportional', 'centered'):
            if candidate in declared:
                kinds.setdefault(name, candidate)
                break
    return kinds


def plan_max_content_widths(plan):
    """从计划的 adaptiveLayout 取「区域 → 封顶值」。"""
    caps = {}
    if not isinstance(plan, dict):
        return caps
    layout = plan.get('adaptiveLayout')
    if not isinstance(layout, dict):
        return caps
    for region in layout.get('regions') or []:
        if not isinstance(region, dict):
            continue
        if region.get('widthPolicy') not in CAPPING_POLICIES:
            continue
        cap = region.get('maxContentWidth')
        if isinstance(cap, dict) and is_number(cap.get('value')):
            caps[region.get('region')] = float(cap['value'])
    return caps


def plan_size_variants(plan):
    """从计划的 ``adaptiveLayout.sizeVariants[]`` 取「区域 → 分档尺寸表」。

    这是「尺寸不缩放」铁律的**唯一合法出口**：当同一设计存在多设备稿
    （如 ``xx`` 与 ``xx-iPad``），iPad 档的尺寸参数写在 iPad 稿里、照稿还原，是
    合规的分档 —— 不是把手机稿等比放大。但「分档」必须逐档声明并附稿依据，
    否则「尺寸随窗口变」这个形态无法和「整页等比放大」区分开。

    返回 ``{region: {sample_id: {width, height}, ...}, ...}``；没有 basis/why 的项
      直接忽略（交给 check_size_invariance 按「未声明」判违规）。
    """
    variants = {}
    if not isinstance(plan, dict):
        return variants
    layout = plan.get('adaptiveLayout')
    if not isinstance(layout, dict):
        return variants
    for entry in layout.get('sizeVariants') or []:
        if not isinstance(entry, dict):
            continue
        region = entry.get('region')
        values = entry.get('values')
        why = entry.get('why')
        basis = entry.get('basis')
        # 缺依据或缺理由的分档是「乱改尺寸」，不配进白名单 —— 由 sizeInvariance 判违规。
        if not region or not isinstance(values, dict) or not why or not basis:
            continue
        per_sample = {}
        for sample_id, dims in values.items():
            if isinstance(dims, dict) and (is_number(dims.get('width')) or is_number(dims.get('height'))):
                per_sample[str(sample_id)] = {
                    'width': float(dims['width']) if is_number(dims.get('width')) else None,
                    'height': float(dims['height']) if is_number(dims.get('height')) else None,
                }
        if per_sample:
            variants[region] = per_sample
    return variants


# --------------------------------------------------------------------------- 八项检查


def check_sample_coverage(samples, required_ids, missing):
    present = {sample.id for sample in samples}
    absent = sorted(str(item) for item in required_ids - present)
    status = 'pass' if not absent and not missing else 'fail'
    return {'status': status, 'required': len(required_ids), 'present': len(present),
            'missing': absent}, [
        failure('sample-coverage', f'必需采样 {absent} 缺少几何证据：'
                '缺采样时其余检查会「全绿」，那是假绿', sample=', '.join(absent))
    ] if absent else []


def check_size_invariance(samples, kinds, size_variants, tolerance):
    """同一 ``fixed`` 元素在**同一设备**的全部采样上点值必须逐字相等。

    「尺寸不缩放」的作用域是**设备平台**，不是「跨所有采样全局一致」：

    - **同设备内**（phone 的多个宽度采样 / tablet 的多个宽度采样之间）：尺寸必须逐字
      相等，**``sizeVariants`` 也不能豁免** —— 这是铁律。一份 iPhone 稿在手机不同宽度档
      之间尺寸不变、一份 iPad 稿在 iPad 不同宽度档之间尺寸不变。
    - **跨设备**（phone vs tablet）：差异允许，但必须走 ``adaptiveLayout.sizeVariants``
      逐档声明（此时有 ``xx`` 与 ``xx-iPad`` 两份稿，照各自稿还原，不是「把手机稿放大」）。

    没有声明设备维度（``device``/``deviceClass``，也无法从 id / 机型推断）的老素材，
    退化回「全采样一致」的旧口径，行为不变。
    """
    compared = 0
    problems = []
    by_id = {}
    device_of_sample = {sample.id: sample.device for sample in samples}
    for sample in samples:
        for element in sample.elements:
            if resolve_kind(element, kinds) != 'fixed':
                continue
            rect = rect_of(element)
            if rect is None:
                continue
            by_id.setdefault(element_id(element), {})[sample.id] = rect
    for name, per_sample in sorted(by_id.items()):
        compared += 1
        # ① 同设备内：尺寸必须逐字相等，sizeVariants 也不豁免（「平台内不变」是铁律）。
        device_groups = {}
        for sample_id, rect in per_sample.items():
            device_groups.setdefault(device_of_sample.get(sample_id), {})[sample_id] = rect
        within_violation = None
        for device, group in sorted(device_groups.items(), key=lambda kv: (kv[0] is None, str(kv[0]))):
            if device is None:
                continue
            widths = {sample_id: rect['width'] for sample_id, rect in group.items()}
            heights = {sample_id: rect['height'] for sample_id, rect in group.items()}
            spread_w = max(widths.values()) - min(widths.values())
            spread_h = max(heights.values()) - min(heights.values())
            if spread_w <= EXACT_EPSILON and spread_h <= EXACT_EPSILON:
                continue
            within_violation = failure(
                'size-not-invariant-within-device',
                f'{name} 是 fixed 元素，但在同一设备 {device!r} 的多个宽度采样之间尺寸不一致：'
                f'宽 {widths}、高 {heights}。「尺寸不缩放」的作用域是设备平台 —— '
                '同一台手机 / 同一台平板的各个宽度档之间尺寸必须逐字相等，'
                'sizeVariants 不能豁免这条（它只许跨平台分档）',
                element=name, device=device, widths=widths, heights=heights,
                maxSpreadPt=round(max(spread_w, spread_h), 4))
            break
        if within_violation:
            problems.append(within_violation)
            continue

        # ② 跨设备（或未声明设备维度）：整体检查，允许 sizeVariants 分档。
        widths = {sample_id: rect['width'] for sample_id, rect in per_sample.items()}
        heights = {sample_id: rect['height'] for sample_id, rect in per_sample.items()}
        spread_w = max(widths.values()) - min(widths.values())
        spread_h = max(heights.values()) - min(heights.values())
        if spread_w <= EXACT_EPSILON and spread_h <= EXACT_EPSILON:
            continue  # 各采样逐字相等，合规

        # 尺寸跨采样不一致：只有「已在 sizeVariants 逐档声明且各档值吻合」才合法。
        declared = size_variants.get(name)
        if declared is not None and _matches_variant(widths, heights, declared):
            continue  # 声明过的分档，合规

        problems.append(failure(
            'size-not-invariant',
            f'{name} 是 fixed 元素，但尺寸在各采样间不一致：'
            f'宽 {widths}（差 {spread_w:.2f}pt）、高 {heights}（差 {spread_h:.2f}pt）。'
            '尺寸是常量，不得随窗口缩放。若这是「多设备稿照稿还原」的合法跨平台分档，'
            '必须在 adaptiveLayout.sizeVariants 里逐档声明尺寸并附 basis 与 why',
            element=name, widths=widths, heights=heights,
            maxSpreadPt=round(max(spread_w, spread_h), 4)))
    return {'status': 'fail' if problems else 'pass', 'compared': compared,
            'violations': problems}, problems


def _matches_variant(widths, heights, declared):
    """实测的各采样宽/高是否与 sizeVariants 声明吻合。

    语义：分档只能发生在**声明过的档**之间。声明表里没列出的采样，其尺寸必须等于
    「基准档」（表里第一个条目，通常是 phone-compact）—— 没声明的档不得擅自改尺寸，
    否则就是「漏声明」，和没声明分档一样是违规。
    """
    if not declared:
        return False
    base_id = next(iter(declared))  # 基准档 = 声明表第一个条目
    base = declared[base_id]

    def expected(sample_id, axis):
        dv = declared.get(sample_id)
        if dv is not None:
            return dv.get(axis)
        return base.get(axis)   # 未列档 = 沿用基准档

    for sample_id, w in widths.items():
        exp = expected(sample_id, 'width')
        if exp is not None and abs(w - exp) > EXACT_EPSILON:
            return False
    for sample_id, h in heights.items():
        exp = expected(sample_id, 'height')
        if exp is not None and abs(h - exp) > EXACT_EPSILON:
            return False
    return True


def check_inset_preservation(samples, kinds):
    """``pinned`` 元素的固定内边距是设计常量，在各采样上必须相等。"""
    compared = 0
    problems = []
    by_id = {}
    for sample in samples:
        for element in sample.elements:
            if resolve_kind(element, kinds) != 'pinned':
                continue
            insets = element.get('insets')
            if not isinstance(insets, dict):
                continue
            exempt = set(element.get('insetExempt') or [])
            kept = {key: value for key, value in insets.items()
                    if is_number(value) and key not in exempt}
            if not kept:
                continue
            by_id.setdefault(element_id(element), {})[sample.id] = kept
    for name, per_sample in sorted(by_id.items()):
        compared += 1
        keys = set()
        for kept in per_sample.values():
            keys |= set(kept)
        for key in sorted(keys):
            values = {sample_id: kept[key] for sample_id, kept in per_sample.items()
                      if key in kept}
            if len(values) < 2:
                continue
            spread = max(values.values()) - min(values.values())
            if spread > EXACT_EPSILON:
                problems.append(failure(
                    'inset-not-preserved',
                    f'{name} 的 pinned 内边距 {key} 在各采样间不一致：{values}'
                    f'（差 {spread:.2f}pt）。「左右各 16pt」是设计常量、由约束闭合，'
                    '宽屏上它仍然必须是 16pt，而不是被撑大或比例化',
                    element=name, edge=key, insets=values,
                    maxSpreadPt=round(spread, 4)))
    return {'status': 'fail' if problems else 'pass', 'compared': compared,
            'violations': problems}, problems


def check_no_overflow(samples, tolerance):
    problems = []
    for sample in samples:
        for element in sample.elements:
            if element.get('overflowOk'):
                continue
            rect = rect_of(element)
            if rect is None or not sample.window_width or not sample.window_height:
                continue
            if (rect['x'] < -tolerance or rect['y'] < -tolerance
                    or rect['x'] + rect['width'] > sample.window_width + tolerance
                    or rect['y'] + rect['height'] > sample.window_height + tolerance):
                problems.append(failure(
                    'element-overflows-window',
                    f'{element_id(element)} 越出窗口 bounds：'
                    f'rect {rect} vs 窗口 {sample.window_width:.0f}×{sample.window_height:.0f}。'
                    '分屏与自由窗口下可用宽度变小，这是最常见的崩法；'
                    '确实需要出血的装饰元素请显式标 overflowOk',
                    sample=sample.id, element=element_id(element), rect=rect))
    return {'status': 'fail' if problems else 'pass', 'violations': problems}, problems


def check_max_content_width(samples, caps, tolerance):
    compared = 0
    problems = []
    for sample in samples:
        for element in sample.elements:
            if not element.get('contentColumn'):
                continue
            rect = rect_of(element)
            if rect is None:
                continue
            region = element.get('region') or element_id(element)
            cap = caps.get(region)
            compared += 1
            if cap is None:
                problems.append(failure(
                    'content-column-without-declared-cap',
                    f'{element_id(element)} 被标为内容列，但计划里没有给区域 {region!r} '
                    '声明 maxContentWidth：要么补声明，要么去掉这个标记',
                    sample=sample.id, element=element_id(element), region=region))
                continue
            if rect['width'] > cap + tolerance:
                problems.append(failure(
                    'content-column-too-wide',
                    f'{element_id(element)} 的内容列宽 {rect["width"]:.1f}pt 超过声明的封顶 '
                    f'{cap:.1f}pt：声明了 max-content-width 却没生效',
                    sample=sample.id, element=element_id(element),
                    width=round(rect['width'], 2), cap=cap))
            left = rect['x']
            right = sample.window_width - (rect['x'] + rect['width'])
            if sample.window_width and abs(left - right) > tolerance:
                problems.append(failure(
                    'content-column-not-centered',
                    f'{element_id(element)} 的内容列没有水平居中：'
                    f'左 {left:.1f}pt / 右 {right:.1f}pt（差 {abs(left - right):.1f}pt）。'
                    '封顶之后必须居中，否则宽屏上的留白会全部堆在一边',
                    sample=sample.id, element=element_id(element),
                    left=round(left, 2), right=round(right, 2)))
    return {'status': 'fail' if problems else 'pass', 'compared': compared,
            'violations': problems}, problems


def check_touch_target(samples, tolerance):
    compared = 0
    problems = []
    for sample in samples:
        minimum = sample.touch_minimum()
        for element in sample.elements:
            if not element.get('interactive'):
                continue
            rect = rect_of(element)
            if rect is None:
                continue
            compared += 1
            smallest = min(rect['width'], rect['height'])
            if smallest + tolerance < minimum:
                problems.append(failure(
                    'touch-target-too-small',
                    f'{element_id(element)} 是交互元素，最小边 {smallest:.1f}pt '
                    f'低于平台下限 {minimum:.0f}pt。点击区不随窗口缩放，'
                    '宽屏上也不得变小',
                    sample=sample.id, element=element_id(element),
                    smallestPt=round(smallest, 2), minimumPt=minimum))
    return {'status': 'fail' if problems else 'pass', 'compared': compared,
            'minimum': min((sample.touch_minimum() for sample in samples), default=None),
            'violations': problems}, problems


def check_no_letterbox(samples, tolerance):
    problems = []
    for sample in samples:
        if sample.document.get('compatibilityMode') is True:
            problems.append(failure(
                'compatibility-mode',
                f'{sample.id} 以 iPhone 兼容缩放模式运行：'
                '这是「声称支持平板但没做适配」的直接证据，画面会整体放大且模糊',
                sample=sample.id))
        letterbox = sample.document.get('letterbox')
        if isinstance(letterbox, dict):
            total = sum(float(letterbox.get(key) or 0)
                        for key in ('x', 'y', 'width', 'height') if is_number(letterbox.get(key)))
            if total > tolerance:
                problems.append(failure(
                    'letterbox-present',
                    f'{sample.id} 存在 {letterbox} 的信箱留边：'
                    '窗口没有被内容填满，通常是方向锁定或固定纵横比造成的',
                    sample=sample.id, letterbox=letterbox))
    return {'status': 'fail' if problems else 'pass', 'violations': problems}, problems


def check_continuity(samples, kinds, tolerance):
    """两个断点之间不能崩：尺寸不得随窗口宽度非单调，同组兄弟不得重叠。"""
    problems = []
    ordered = sorted(samples, key=lambda item: (item.window_width, item.id))
    by_id = {}
    for sample in ordered:
        for element in sample.elements:
            if resolve_kind(element, kinds) != 'pinned':
                continue
            rect = rect_of(element)
            if rect is None:
                continue
            by_id.setdefault(element_id(element), []).append((sample, rect))
    for name, series in sorted(by_id.items()):
        widths = [rect['width'] for _, rect in series]
        for index in range(1, len(widths)):
            if widths[index] + tolerance < widths[index - 1]:
                problems.append(failure(
                    'non-monotonic-width',
                    f'{name} 是 pinned 元素，宽度随窗口变宽反而变窄：'
                    f'{series[index - 1][0].id} {widths[index - 1]:.1f}pt → '
                    f'{series[index][0].id} {widths[index]:.1f}pt。'
                    '贴父派生的宽度在更宽的窗口上不可能更小，'
                    '这通常意味着只在两个断点上对、中间宽度崩了',
                    element=name,
                    series=[{'sample': sample.id, 'width': round(rect['width'], 2)}
                            for sample, rect in series]))
    for sample in samples:
        groups = {}
        for element in sample.elements:
            group = element.get('siblingGroup')
            if not group or element.get('overlapAllowed'):
                continue
            rect = rect_of(element)
            if rect is None:
                continue
            groups.setdefault(group, []).append((element_id(element), rect))
        for group, members in groups.items():
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    if overlaps(members[i][1], members[j][1]):
                        problems.append(failure(
                            'sibling-overlap',
                            f'{sample.id} 的 {group!r} 组里 {members[i][0]} 与 '
                            f'{members[j][0]} 重叠：{members[i][1]} / {members[j][1]}。'
                            '同一组的兄弟元素在任意宽度下都不该压在一起；'
                            '确属有意叠放请标 overlapAllowed',
                            sample=sample.id, group=group,
                            elements=[members[i][0], members[j][0]]))
    return {'status': 'fail' if problems else 'pass', 'violations': problems}, problems


# --------------------------------------------------------------------------- 入口


def run(targets_path, geometry_overrides, plan_path, tolerance):
    targets, error = load_json(targets_path)
    if targets is None:
        return {'schemaVersion': 1, 'status': 'error',
                'reason': f'adaptive-targets.json 读取失败：{error}',
                'violations': [], 'exitCode': 2}, 2
    if not isinstance(targets, dict):
        return {'schemaVersion': 1, 'status': 'error',
                'reason': 'adaptive-targets.json 必须是 JSON 对象',
                'violations': [], 'exitCode': 2}, 2

    plan, plan_error = (None, None)
    if plan_path:
        plan, plan_error = load_json(plan_path)

    warnings = []
    if plan_error:
        warnings.append(f'实现计划读取失败（封顶值只能靠几何转储自证）：{plan_error}')

    samples, load_failures, load_warnings = resolve_samples(
        targets, geometry_overrides, Path(targets_path).resolve().parent)
    warnings.extend(load_warnings)

    required_ids = {entry.get('id') for entry in (targets.get('samples') or [])
                    if isinstance(entry, dict) and entry.get('id')
                    and entry.get('required', True) is not False}
    kinds = plan_region_kinds(plan)
    caps = plan_max_content_widths(plan)
    size_variants = plan_size_variants(plan)

    checks = {}
    violations = list(load_failures)

    coverage, problems = check_sample_coverage(samples, required_ids,
                                               {item.get('sample') for item in load_failures})
    checks['sampleCoverage'] = coverage
    violations.extend(problems)

    size_check, problems = check_size_invariance(samples, kinds, size_variants, tolerance)
    checks['sizeInvariance'] = size_check
    violations.extend(problems)

    inset_check, problems = check_inset_preservation(samples, kinds)
    checks['insetPreservation'] = inset_check
    violations.extend(problems)

    overflow_check, problems = check_no_overflow(samples, tolerance)
    checks['noOverflow'] = overflow_check
    violations.extend(problems)

    cap_check, problems = check_max_content_width(samples, caps, tolerance)
    checks['maxContentWidth'] = cap_check
    violations.extend(problems)

    touch_check, problems = check_touch_target(samples, tolerance)
    checks['touchTarget'] = touch_check
    violations.extend(problems)

    letterbox_check, problems = check_no_letterbox(samples, tolerance)
    checks['noLetterbox'] = letterbox_check
    violations.extend(problems)

    continuity_check, problems = check_continuity(samples, kinds, tolerance)
    checks['continuity'] = continuity_check
    violations.extend(problems)

    if not samples:
        warnings.append('没有任何可用的几何采样：本次审计只能报告「证据不足」，'
                        '不得据此认为平板适配通过')

    status = 'fail' if violations else ('pass' if samples else 'insufficient-evidence')
    payload = {
        'schemaVersion': 1,
        'model': 'continuous-window-width',
        'status': status,
        'tolerancePt': tolerance,
        'targets': str(targets_path),
        'plan': str(plan_path) if plan_path else None,
        'platform': targets.get('platform'),
        'samples': [{'id': sample.id, 'widthClass': sample.width_class,
                     'windowBoundsPoints': sample.window,
                     'geometry': sample.path}
                    for sample in samples],
        'checks': checks,
        'violations': violations,
        'warnings': warnings,
    }
    code = 1 if violations else 0
    payload['exitCode'] = code
    return payload, code


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--targets', required=True, help='adaptive-targets.json 路径')
    ap.add_argument('--geometry', action='append', metavar='NAME=PATH',
                    help='覆盖某个采样的几何转储路径，可重复')
    ap.add_argument('--plan', help='ui-implementation-plan.json 路径（取 kind 与封顶值）')
    ap.add_argument('--tolerance', type=float, default=2.0,
                    help='位置与尺寸容差（pt），默认 2.0')
    ap.add_argument('--output', help='把结论同时写入该路径')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    overrides = {}
    for item in args.geometry or []:
        name, _, path = item.partition('=')
        if not name or not path:
            print(f'--geometry 需要 NAME=PATH 形式，收到 {item!r}', file=sys.stderr)
            return 2
        overrides[name] = path

    payload, code = run(Path(args.targets), overrides, args.plan, args.tolerance)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')

    if not args.quiet:
        if payload.get('status') == 'error':
            print(f"自适应审计无法执行：{payload.get('reason')}", file=sys.stderr)
        else:
            print(f"自适应几何审计：{len(payload.get('samples') or [])} 个采样，"
                  f"容差 {payload['tolerancePt']}pt")
            for name, check in (payload.get('checks') or {}).items():
                print(f"  {name:<18} {check.get('status')}")
            for item in payload['violations']:
                print(f"  违规 [{item['kind']}] — {item['detail']}")
            for item in payload['warnings']:
                print(f'  告警：{item}')
            print(f"结论：{payload['status']}（违规 {len(payload['violations'])} 项）")
    return code


if __name__ == '__main__':
    raise SystemExit(main())
