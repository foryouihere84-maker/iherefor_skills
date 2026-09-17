#!/usr/bin/env python3
"""宽度轴静态核对：``adaptiveLayout`` 的声明自身完整，且源码照它声明的方式实现。

本脚本与 ``check_layout_proportions.py`` 是姊妹：那个管**尺寸轴 + 位置轴**（尺寸按闭合方式声明、
位置相对直接父视图），这个管**宽度轴**（父视图变宽之后内容怎么收敛）。
两门都在**写码完成后、编译之前**跑，纯静态、秒级、不编译不起浏览器。

为什么这一门必须排在编译之前？因为它拦的东西**截图看不出来**：

* 单列内容在 1024pt 上拉满 —— 元素没越界、尺寸也没变，像素 diff 全绿，但阅读节奏坏了；
* 声明了 ``max-content-width`` 而源码里根本没有封顶原语 —— 手机档下两者视觉一致；
* 用 ``UIScreen.main.bounds`` 当布局基准 —— 全屏下与 ``view.bounds`` 恰好相等，
  只有分屏与自由窗口才分岔。

把它们留到编译之后，等于为每一条都付一次编译 + 装机 + 截图的成本，而截图还证明不了。

判定分两层，与 ``validate_run.py`` 对布局约束的三层核对同形：

1. **计划质量**（``--plan-only`` 也跑）：``adaptiveLayout`` 自身完整 —— 采样覆盖三个宽度档、
   每个区域都归入一个合法 ``widthPolicy``、``maxContentWidth`` / ``columnCount`` 该给的给了、
   ``forbiddenAdaptations`` 非空。只读计划，判起来最硬。
2. **源码合规**（需 ``--source``）：声明与实现逐条对上 —— 声明封顶就得有封顶原语、
   声明网格就不得写死列数、不得出现四类禁止模式。

**方向锁的判定是条件式的**，不是「一律禁止」：只有计划**声明了** ``adaptiveLayout``
（即声称支持多宽度档）时，锁死单一方向才算违规 —— 因为锁了竖屏就拿不到 regular 宽度档。
未声明时最多告警，不硬判。

用法：
    python3 scripts/check_adaptive_layout.py --plan <plan.json> --plan-only
    python3 scripts/check_adaptive_layout.py --plan <plan.json> --source <源码根>
    python3 scripts/check_adaptive_layout.py --plan <plan.json> --source <源码根> \
        --targets <run>/adaptive-targets.json --output <report.json>

退出码：0 = 通过；1 = 存在违规；2 = 用法或读取错误。
"""
import argparse
import json
import re
import sys
from pathlib import Path

WIDTH_POLICIES = ('full-bleed', 'max-content-width', 'centered-column',
                  'grid', 'pane', 'stacked')
# ``stretch-full-width`` 刻意不在上面这组里。单列内容拉满宽屏是本契约要拦的头号问题：
# 它不会让任何断言失败（元素没越界、尺寸也没变），所以必须由 ``full-bleed`` 显式声明，
# 不能是默认行为、更不能是一个可以随手写上的 policy。
FORBIDDEN_POLICIES = ('stretch-full-width',)
CAPPING_POLICIES = ('max-content-width', 'centered-column')
REQUIRED_FORBIDDEN_ADAPTATIONS = ('uniform-scale', 'stretch-full-width', 'font-scale')
WIDTH_CLASSES = ('compact', 'medium', 'expanded')
DEFAULT_FIRST_LEVEL_WIDTH_CLASS = 'compact'
MODEL = 'continuous-window-width'
MIN_WINDOW_SAMPLES = 4

# 宽度档的数值阈值（用于「宽度档是否与实际宽度明显不符」的提示，不是硬判违规的边界）。
# 注意：现有口径里「iPad 竖 1024」被约定为 medium，与这里的 medium < 840 有历史出入，
# 所以只用「明显越界」（跨档越级）做 warning，不用它去判「1024 该是 medium 还是 expanded」。
WIDTH_CLASS_RANGES = {'compact': (0, 600), 'medium': (600, 840),
                      'expanded': (840, float('inf'))}

# 「设备平台」维度（phone/tablet），与「窗口宽度档」（compact/medium/expanded）正交。
# sizeVariants 声明的跨平台分档，要求 phone 与 tablet 两档都有采样覆盖。
DEVICE_CLASSES = ('phone', 'tablet')


def infer_device_class(sample):
    """从采样的 deviceClass / device / id 推断设备平台，返回 phone / tablet / None。"""
    device_class = sample.get('deviceClass')
    if device_class in DEVICE_CLASSES:
        return device_class
    sid = (sample.get('id') or '').lower()
    if 'phone' in sid:
        return 'phone'
    if 'tablet' in sid or sid.startswith('pad') or 'ipad' in sid:
        return 'tablet'
    device = sample.get('device')
    if isinstance(device, str):
        dev = device.lower()
        if 'iphone' in dev or 'pixel' in dev or 'galaxy' in dev:
            return 'phone'
        if 'ipad' in dev or 'tablet' in dev or 'fold' in dev:
            return 'tablet'
    return None

SOURCE_SUFFIXES = ('.swift', '.m', '.mm', '.h', '.kt', '.java', '.xml')
EXTRA_SOURCE_NAMES = ('Info.plist', 'AndroidManifest.xml', 'project.pbxproj')

# 禁止模式。每条都对应一次真实会踩的坑，所以 ``detail`` 写的是「为什么」而不是「不许」。
SOURCE_PATTERNS = (
    (re.compile(r'UIScreen\s*\.\s*main\s*\.\s*(?:nativeBounds|bounds)'),
     'screen-as-layout-source',
     '用 UIScreen.main.bounds 当布局基准：分屏与自由窗口下它返回的是整块屏、'
     '不是你的窗口，原点与可用宽度都会错。改用 view.bounds / windowScene'),
    (re.compile(r'\bDisplayMetrics\b|getRealSize\s*\(|getRealMetrics\s*\('),
     'display-metrics-as-layout-source',
     '用 DisplayMetrics 当布局基准：它描述的是显示设备而不是窗口，'
     '多窗口与折叠屏下必然错。改用 WindowMetricsCalculator / WindowSizeClass'),
    (re.compile(r'UIRequiresFullScreen'),
     'requires-full-screen',
     'UIRequiresFullScreen 会退出分屏与 Slide Over 支持，平板上的窗口尺寸就固定了 —— '
     '宽度轴失去意义'),
)

# 方向锁。XML 属性（Android）与 Info.plist（iOS）两种形态分开处理：
# plist 是结构化的，用文本启发式读数组；XML 用属性匹配。
ANDROID_ORIENTATION = re.compile(
    r'android:screenOrientation\s*=\s*"(portrait|landscape|reversePortrait|'
    r'reverseLandscape|sensorPortrait|sensorLandscape)"')
# 这两组之外的取值（unspecified / fullSensor / user / behind / nosensor）不算锁死。

INFO_ORIENTATION_KEY = re.compile(
    r'<key>\s*UISupportedInterfaceOrientations\s*</key>\s*<array>(.*?)</array>',
    re.DOTALL)
IPAD_ORIENTATION_KEY = re.compile(
    r'<key>\s*UISupportedInterfaceOrientations~ipad\s*</key>\s*<array>(.*?)</array>',
    re.DOTALL)
PLIST_STRING = re.compile(r'<string>\s*([^<]+?)\s*</string>')
TARGETED_FAMILY = re.compile(r'TARGETED_DEVICE_FAMILY\s*=\s*"?([0-9,\s]+)"?')

# 封顶原语。按模式分组的并集 —— 只要命中任一组即可，因为一个工程可能同时有
# SwiftUI 与 UIKit 目标，也可能同时有 Compose 与 Views。**不按目标模式挑**：
# 挑错模式会造出一个假违规，而假违规会训练出「看到告警就忽略」的习惯。
CAPPING_IDIOMS = (
    # iOS
    'maxContentWidth', 'readableContentGuide', 'maxWidth', 'lessThanOrEqualToConstant',
    'containerRelativeFrame',
    # Android Views / XML
    'layout_constraintWidth_max', 'content_max_width', 'layout_constraintWidth_percent',
    # Compose
    'widthIn', 'contentMaxWidth', 'BoxWithConstraints',
)

# 固定列数。声明了 grid 的区域出现这些就是「写了死列数、没随宽度档变」。
FIXED_COLUMN_IDIOMS = (
    re.compile(r'GridCells\s*\.\s*Fixed\s*\('),
    re.compile(r'android:spanCount\s*=\s*"\d+"'),
    re.compile(r'layoutManager\s*=\s*GridLayoutManager\s*\([^)]*,\s*\d+\s*\)'),
)

SW600DP_DIR = 'values-sw600dp'


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8')), None
    except Exception as exc:  # noqa: BLE001 - 读取失败的原因原样上报
        return None, str(exc)


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def iter_source_files(roots):
    """列出源码根下的可读文本文件。跳过构建产物与依赖目录。"""
    skip = {'node_modules', '.git', 'build', 'DerivedData', '.runtime', 'Pods',
            '__pycache__', '.gradle'}
    for root in roots:
        root_path = Path(root)
        if root_path.is_file():
            yield root_path
            continue
        if not root_path.is_dir():
            continue
        for path in sorted(root_path.rglob('*')):
            if any(part in skip for part in path.parts):
                continue
            if not path.is_file():
                continue
            if path.suffix in SOURCE_SUFFIXES or path.name in EXTRA_SOURCE_NAMES:
                yield path


def has_qualifier_dir(roots, name):
    """资源限定符目录可能**是空的**（值只在别处被引用），所以按目录名找而不是按文件找。"""
    skip = {'node_modules', '.git', 'build', 'DerivedData', '.runtime', 'Pods',
            '__pycache__', '.gradle'}
    for root in roots:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        for path in root_path.rglob(name):
            if path.is_dir() and not any(part in skip for part in path.parts):
                return True
    return False


def read_text(path):
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''


def violation(kind, detail, **extra):
    item = {'kind': kind, 'detail': detail}
    item.update({key: value for key, value in extra.items() if value is not None})
    return item


# --------------------------------------------------------------------------- 计划质量


def check_plan(plan):
    """``adaptiveLayout`` 自身是否完整。只读计划，不依赖源码。"""
    violations = []
    warnings = []
    layout = plan.get('adaptiveLayout')

    if layout is None:
        warnings.append(
            'ui-implementation-plan.json 未声明 adaptiveLayout：宽度轴（父视图变宽时内容'
            '怎么收敛）没有规则可依。缺它时「第一层位置按页面比例」会一路推到 1024pt —— '
            '位置 ×2.6 而尺寸 ×1，内容被挤到左侧、右侧大片空白。'
            '若本页确实只交付手机档，请显式写明；否则按 references/adaptive-layout.md 补齐')
        return violations, warnings, None

    if not isinstance(layout, dict):
        violations.append(violation(
            'adaptive-layout-not-object',
            f'adaptiveLayout 必须是对象，实际是 {type(layout).__name__}'))
        return violations, warnings, None

    if layout.get('model') != MODEL:
        violations.append(violation(
            'adaptive-model-mismatch',
            f"adaptiveLayout.model 应为 {MODEL!r}，实际 {layout.get('model')!r}。"
            '值不同说明用的是「手机/平板两个断点」的旧口径：断点之间的连续宽度无定义，'
            '分屏与自由窗口下必然失效'))

    samples = layout.get('windowSamples')
    if not isinstance(samples, list) or not samples:
        violations.append(violation(
            'missing-window-samples',
            'adaptiveLayout.windowSamples 必须是非空数组：采样是验证的取样点，'
            '没有它就无法证明任何宽度档下布局成立'))
    else:
        if len(samples) < MIN_WINDOW_SAMPLES:
            violations.append(violation(
                'too-few-window-samples',
                f'只声明了 {len(samples)} 个采样，至少需要 {MIN_WINDOW_SAMPLES} 个 —— '
                'phone-compact / tablet-regular-portrait / tablet-regular-landscape / '
                'phone-regular-landscape。漏掉手机横屏就会把「medium 一定来自平板」'
                '写成假设'))
        seen = set()
        seen_devices = set()
        for index, sample in enumerate(samples):
            if not isinstance(sample, dict):
                violations.append(violation(
                    'window-sample-not-object',
                    f'windowSamples[{index}] 必须是对象'))
                continue
            if not sample.get('id'):
                violations.append(violation(
                    'window-sample-missing-id', f'windowSamples[{index}] 缺少 id'))
            width_class = sample.get('widthClass')
            if width_class not in WIDTH_CLASSES:
                violations.append(violation(
                    'window-sample-bad-width-class',
                    f'windowSamples[{index}].widthClass 取值非法：{width_class!r}，'
                    f'应为 {WIDTH_CLASSES} 之一',
                    sample=sample.get('id')))
            else:
                seen.add(width_class)
            declared_device_class = sample.get('deviceClass')
            if declared_device_class is not None and declared_device_class not in DEVICE_CLASSES:
                violations.append(violation(
                    'window-sample-bad-device-class',
                    f'windowSamples[{index}].deviceClass 取值非法：{declared_device_class!r}，'
                    f'应为 {DEVICE_CLASSES} 之一（或省略，由 id 前缀 / 机型名推断）',
                    sample=sample.get('id')))
            else:
                inferred_device = infer_device_class(sample)
                if inferred_device in DEVICE_CLASSES:
                    seen_devices.add(inferred_device)
            if not is_number(sample.get('width')):
                violations.append(violation(
                    'window-sample-missing-width',
                    f'windowSamples[{index}] 缺少数值 width', sample=sample.get('id')))
            elif width_class in WIDTH_CLASSES:
                # 宽度档由「实际窗口宽度」决定，不是随设备名写死。这里只提示「明显越界」
                # （把手机宽度标成 medium/expanded、或把平板宽度标成 compact 这种跨档越级），
                # 不去判「1024 该归 medium 还是 expanded」——那涉及既有历史口径，见 adaptive-layout.md §2。
                width = float(sample['width'])
                lo, hi = WIDTH_CLASS_RANGES[width_class]
                if width < lo or width >= hi:
                    warnings.append(
                        f'windowSamples[{index}]（{sample.get("id")}）width={width} 但标注 '
                        f'{width_class}（阈值 {lo}–{hi}）：宽度档应按实际窗口宽度归类，'
                        '请确认这个采样真的落在它所声明的档位。iPad 稿画布可能是 810 这类'
                        '非标值（不是只有 1024/1366），照实际宽度就近归类')
        for width_class in WIDTH_CLASSES:
            if width_class not in seen:
                violations.append(violation(
                    'window-class-uncovered',
                    f'没有任何采样落在 {width_class!r} 档：宽度轴是按档做决策的，'
                    '漏掉一档就等于那一档的行为没有定义'))

    first_level = layout.get('firstLevelWidthClass', DEFAULT_FIRST_LEVEL_WIDTH_CLASS)
    if first_level not in WIDTH_CLASSES:
        violations.append(violation(
            'bad-first-level-width-class',
            f'firstLevelWidthClass 取值非法：{first_level!r}，应为 {WIDTH_CLASSES} 之一'))
    elif first_level != DEFAULT_FIRST_LEVEL_WIDTH_CLASS:
        warnings.append(
            f'firstLevelWidthClass = {first_level!r}（非缺省 compact）：'
            '「第一层水平位置按页面比例」被放宽到了更宽的档。该规则的水平位置按比例 ×N 而尺寸 ×1，'
            '在宽档上会把内容挤到左侧，确认这是有意为之。'
            '（垂直位置不受此开关影响：它由普通 Auto Layout 内容链闭合。）')

    forbidden = layout.get('forbiddenAdaptations')
    if not isinstance(forbidden, list) or not forbidden:
        violations.append(violation(
            'forbidden-adaptations-missing',
            'adaptiveLayout.forbiddenAdaptations 必须是非空数组：'
            '它是「哪些做法明确不许用」的清单，空清单等于没有约束'))
    else:
        missing = [name for name in REQUIRED_FORBIDDEN_ADAPTATIONS if name not in forbidden]
        if missing:
            violations.append(violation(
                'forbidden-adaptations-incomplete',
                f'forbiddenAdaptations 缺少 {missing}：'
                'uniform-scale（整页等比放大）、stretch-full-width（单列拉满）、'
                'font-scale（平板上把字号调大）是平板适配的三种典型错解，必须逐条禁止'))

    # sizeVariants 是「跨平台分档」的声明：它说「xx 稿给 A、xx-iPad 稿给 B，照各自稿还原」。
    # 既然谈的是 phone vs tablet 的差异，就必须先有 phone 和 tablet 两档的采样，否则
    # 「分档」没有可指认的两个平台，sizeInvariance 也无法判定「同设备内」是否仍然不变。
    size_variants = layout.get('sizeVariants')
    if isinstance(size_variants, list) and size_variants:
        missing_dims = [dim for dim in DEVICE_CLASSES if dim not in seen_devices]
        if missing_dims:
            violations.append(violation(
                'size-variants-without-device-coverage',
                f'声明了 adaptiveLayout.sizeVariants（跨平台分档），但采样里没有覆盖 '
                f'{missing_dims} 平台：跨平台分档必须能指认「是哪两个平台在分」，'
                '且 sizeInvariance 要靠设备维度去判断「同设备内是否仍然不变」。'
                '请在 windowSamples 补上对应平台的采样（或显式标 deviceClass）'))
        for index, entry in enumerate(size_variants):
            if not isinstance(entry, dict):
                violations.append(violation(
                    'size-variant-not-object', f'sizeVariants[{index}] 必须是对象'))
                continue
            if not entry.get('region'):
                violations.append(violation(
                    'size-variant-missing-region',
                    f'sizeVariants[{index}] 缺少 region：分档必须指认是哪个元素分档'))
            if not entry.get('basis'):
                violations.append(violation(
                    'size-variant-missing-basis',
                    f'sizeVariants[{index}] 缺少 basis：分档必须说明照哪份稿'
                    '（xx / xx-iPad 的 design 名 + image_id）'))
            if not entry.get('why'):
                violations.append(violation(
                    'size-variant-missing-why',
                    f'sizeVariants[{index}] 缺少 why：分档必须说明为什么这一档尺寸不同'
                    '（照稿还原，非缩放）'))
            if not isinstance(entry.get('values'), dict) or not entry.get('values'):
                violations.append(violation(
                    'size-variant-missing-values',
                    f'sizeVariants[{index}] 缺少 values：分档必须给出至少两个采样档的'
                    '宽/高值，且与稿一致'))

    regions = layout.get('regions')
    if not isinstance(regions, list) or not regions:
        violations.append(violation(
            'missing-adaptive-regions',
            'adaptiveLayout.regions 必须是非空数组：每个可见区域都要归入一个 widthPolicy，'
            '「默认拉满」不是一种可选答案'))
        return violations, warnings, layout

    for index, region in enumerate(regions):
        if not isinstance(region, dict):
            violations.append(violation(
                'adaptive-region-not-object', f'regions[{index}] 必须是对象'))
            continue
        name = region.get('region') or f'regions[{index}]'
        policy = region.get('widthPolicy')
        if policy in FORBIDDEN_POLICIES:
            violations.append(violation(
                'stretch-full-width-not-a-policy',
                f'{name} 的 widthPolicy 是 {policy!r}，它不在合法枚举内。'
                '单列内容拉满宽屏是本契约要拦的头号问题 —— 元素没越界、尺寸也没变，'
                '断言全绿但阅读节奏坏了。确实需要铺满时用 full-bleed 显式声明',
                region=name))
            continue
        if policy not in WIDTH_POLICIES:
            violations.append(violation(
                'bad-width-policy',
                f'{name} 的 widthPolicy 取值非法：{policy!r}，应为 {WIDTH_POLICIES} 之一',
                region=name))
            continue
        if policy in CAPPING_POLICIES:
            cap = region.get('maxContentWidth')
            if not isinstance(cap, dict) or not is_number(cap.get('value')) or cap.get('value') <= 0:
                violations.append(violation(
                    'missing-max-content-width',
                    f'{name} 声明了 {policy}，必须给出 maxContentWidth.value（>0 的设计常量，'
                    '600~700pt 量级）：没有封顶值，这条 policy 就没有内容',
                    region=name))
            elif not cap.get('of') or not cap.get('reason'):
                violations.append(violation(
                    'incomplete-max-content-width',
                    f'{name} 的 maxContentWidth 缺少 of 或 reason：'
                    '封顶值要说明基准父视图与理由，否则无从复核它是不是随手填的',
                    region=name))
        if policy == 'grid':
            counts = region.get('columnCount')
            if not isinstance(counts, dict):
                violations.append(violation(
                    'missing-column-count',
                    f'{name} 声明了 grid，必须给出 columnCount 的 compact / medium / expanded 三档',
                    region=name))
            else:
                values = []
                for width_class in WIDTH_CLASSES:
                    value = counts.get(width_class)
                    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                        violations.append(violation(
                            'bad-column-count',
                            f'{name} 的 columnCount.{width_class} 必须是 ≥1 的整数，'
                            f'实际 {value!r}',
                            region=name))
                    else:
                        values.append(value)
                if len(values) == len(WIDTH_CLASSES) and values != sorted(values):
                    violations.append(violation(
                        'column-count-not-monotonic',
                        f'{name} 的 columnCount {values} 不是单调不减的：'
                        '更宽的窗口反而给出更少的列，几乎一定是写反了',
                        region=name))
    return violations, warnings, layout


# --------------------------------------------------------------------------- 源码合规


def capping_idiom_present(texts):
    for text in texts:
        for idiom in CAPPING_IDIOMS:
            if idiom in text:
                return idiom
    return None


def device_family_warnings(roots):
    """工程声称支持 iPad（TARGETED_DEVICE_FAMILY 含 2）却没有宽度轴声明时的告警。

    同一个 ``TARGETED_DEVICE_FAMILY`` 在 ``project.pbxproj`` 里会出现很多次（每个
    build configuration 一份），逐条报会刷出六条一模一样的告警 —— 而重复告警会训练出
    「看到告警就忽略」的习惯。所以按**文件**去重，一个文件只说一次。
    """
    warnings = []
    for path in iter_source_files(roots):
        text = read_text(path)
        if not text:
            continue
        for match in TARGETED_FAMILY.finditer(text):
            families = {token.strip() for token in match.group(1).split(',') if token.strip()}
            if '2' in families:
                warnings.append(
                    f'{path.name} 的 TARGETED_DEVICE_FAMILY 含 2（iPad），'
                    '但本页没有宽度轴声明：工程会声称支持 iPad 而实际以竖屏或兼容缩放模式'
                    '运行。要么补齐 adaptiveLayout，要么把设备族收窄到 1')
                break
    return warnings


def check_source(layout, roots):
    """声明与实现逐条对上。只有给了 ``--source`` 才谈得上。"""
    violations = []
    warnings = []
    files = list(iter_source_files(roots))
    texts = []
    for path in files:
        texts.append((path, read_text(path)))

    # 四类禁止模式。逐文件逐行定位，报出来的东西必须能直接跳到源码。
    for path, text in texts:
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern, kind, detail in SOURCE_PATTERNS:
                if pattern.search(line):
                    violations.append(violation(
                        kind, detail, file=str(path), line=line_number,
                        snippet=line.strip()[:120]))
            match = ANDROID_ORIENTATION.search(line)
            if match:
                violations.append(violation(
                    'orientation-locked',
                    f'android:screenOrientation 锁死为 {match.group(1)!r}：'
                    '锁了方向就拿不到别的宽度档，而 Android 15（API 35）起 sw≥600dp 设备上'
                    '系统会直接忽略这个锁定并强制可调整大小 —— 锁方向不是保险，是信箱模式',
                    file=str(path), line=line_number, snippet=line.strip()[:120]))

    # Info.plist 的方向数组是结构化的，单独读一次。
    plist_texts = [(path, text) for path, text in texts if path.name == 'Info.plist']
    for path, text in plist_texts:
        ipad_set = IPAD_ORIENTATION_KEY.search(text)
        match = INFO_ORIENTATION_KEY.search(text)
        if match:
            declared = set(PLIST_STRING.findall(match.group(1)))
            # **iPhone 只支持竖屏、iPad 支持全方向是一个合法且常见的组合**，
            # 所以只有「通用方向集锁死竖屏、又没有 ~ipad 方向集」才算违规 ——
            # 那种情况下 regular 宽度档在**所有**设备上都拿不到。
            # 见到 Portrait 就报，会把上面那个合法组合一起误报掉。
            if declared == {'UIInterfaceOrientationPortrait'} and ipad_set is None:
                violations.append(violation(
                    'orientation-locked',
                    'UISupportedInterfaceOrientations 只声明了 Portrait，且没有 '
                    'UISupportedInterfaceOrientations~ipad：竖屏锁死后 regular 宽度档'
                    '（iPad 竖 1024、手机横屏）在所有设备上都拿不到，宽度轴无从验证',
                    file=str(path)))
        if ipad_set is None and match:
            warnings.append(
                f'{path.name} 没有 UISupportedInterfaceOrientations~ipad：'
                'iPad 会回落到通用方向集。若本页确实只交付手机档，这是预期内的；'
                '否则应显式声明 iPad 方向集')

    # 声明封顶 ⇒ 源码里必须有封顶原语。
    capping_regions = [region.get('region') for region in (layout.get('regions') or [])
                       if isinstance(region, dict)
                       and region.get('widthPolicy') in CAPPING_POLICIES]
    if capping_regions:
        idiom = capping_idiom_present([text for _, text in texts])
        if idiom is None:
            violations.append(violation(
                'missing-max-content-width-idiom',
                f'计划给 {capping_regions} 声明了内容列封顶，但源码里找不到任何封顶原语'
                f'（{", ".join(CAPPING_IDIOMS[:6])} 等）：手机档下两者视觉一致，'
                '所以这一条只能在静态门里拦',
                region=', '.join(str(name) for name in capping_regions)))

    # Android Views/XML 模式下，封顶值应当来自资源限定符分档。
    has_views_xml = any(path.suffix == '.xml' for path, _ in texts)
    if has_views_xml and (capping_regions or
                          any(isinstance(region, dict) and region.get('widthPolicy') == 'grid'
                              for region in (layout.get('regions') or []))):
        if not has_qualifier_dir(roots, SW600DP_DIR):
            warnings.append(
                f'源码里没有 {SW600DP_DIR}/ 资源目录：Views/XML 模式下「手机不限、'
                '平板封顶」靠资源限定符分档给值（values 给 0dp、'
                f'{SW600DP_DIR} 给 600dp）。缺它时封顶只能写死在代码里')

    # 声明网格 ⇒ 不得写死列数。
    grid_regions = [region.get('region') for region in (layout.get('regions') or [])
                    if isinstance(region, dict) and region.get('widthPolicy') == 'grid']
    if grid_regions:
        for path, text in texts:
            for line_number, line in enumerate(text.splitlines(), start=1):
                for pattern in FIXED_COLUMN_IDIOMS:
                    if pattern.search(line):
                        violations.append(violation(
                            'fixed-column-count',
                            f'计划给 {grid_regions} 声明了 grid（列数随宽度档变），'
                            '源码里却出现固定列数：宽度档一换列数不会变',
                            file=str(path), line=line_number,
                            region=', '.join(str(name) for name in grid_regions),
                            snippet=line.strip()[:120]))
    return violations, warnings, len(files)


# --------------------------------------------------------------------------- 入口


def run(plan_path, source_roots, targets_path, plan_only):
    plan, error = load_json(plan_path)
    if plan is None:
        return {'schemaVersion': 1, 'status': 'error',
                'reason': f'实现计划读取失败：{error}', 'violations': [],
                'warnings': [], 'exitCode': 2}, 2
    if not isinstance(plan, dict):
        return {'schemaVersion': 1, 'status': 'error',
                'reason': '实现计划必须是 JSON 对象', 'violations': [],
                'warnings': [], 'exitCode': 2}, 2

    plan_violations, plan_warnings, layout = check_plan(plan)
    violations = list(plan_violations)
    warnings = list(plan_warnings)

    declared = layout is not None
    checked_files = 0
    source_checked = False
    if declared and source_roots and not plan_only:
        source_violations, source_warnings, checked_files = check_source(layout, source_roots)
        violations.extend(source_violations)
        warnings.extend(source_warnings)
        source_checked = True
    elif declared and not source_roots and not plan_only:
        warnings.append(
            '未核对源码（未传 --source）：计划声明了宽度轴，但「封顶原语在不在、'
            '有没有方向锁与 UIScreen.main」尚未验证。跑 '
            'scripts/check_adaptive_layout.py --plan <plan> --source <源码根>')
    elif not declared and source_roots and not plan_only:
        # 未声明宽度轴是合法状态（等于声明「本页只交付手机档」），但工程声称支持 iPad
        # 却没有任何宽度轴决策时至少要说出来 —— 那正是「声称支持、实际没适配」的形态。
        warnings.extend(device_family_warnings(source_roots))

    if targets_path:
        targets, targets_error = load_json(targets_path)
        if targets is None:
            warnings.append(f'adaptive-targets.json 读取失败：{targets_error}')
        elif isinstance(targets, dict):
            samples = targets.get('samples')
            if not isinstance(samples, list) or not samples:
                violations.append(violation(
                    'targets-without-samples',
                    'adaptive-targets.json 的 samples 必须是非空数组'))
            elif declared:
                # 只核对计划里标为必需的采样：``required: false`` 的采样本来就允许
                # 不取几何证据（它的作用是「知道有这一档」，不是「每档都取证」）。
                # 拿可选采样去要求 targets，会造出一条永远修不掉的告警。
                planned = {sample.get('id')
                           for sample in (layout.get('windowSamples') or [])
                           if isinstance(sample, dict) and sample.get('id')
                           and sample.get('required', True) is not False}
                actual = {sample.get('id') for sample in samples
                          if isinstance(sample, dict)}
                missing = sorted(str(item) for item in planned - actual if item)
                if missing:
                    violations.append(violation(
                        'targets-missing-samples',
                        f'计划声明为必需的采样 {missing} 没有出现在 adaptive-targets.json：'
                        '采样只写在计划里而没有落成目标，就没有几何证据可采'))

    policy_counts = {}
    for region in (layout.get('regions') or []) if isinstance(layout, dict) else []:
        if isinstance(region, dict):
            policy = region.get('widthPolicy')
            policy_counts[policy] = policy_counts.get(policy, 0) + 1

    status = 'fail' if violations else ('pass' if declared else 'not-declared')
    payload = {
        'schemaVersion': 1,
        'model': MODEL,
        'plan': str(plan_path),
        'sources': [str(root) for root in (source_roots or [])],
        'declared': declared,
        'sourceChecked': source_checked,
        'status': status,
        'windowSampleCount': len(layout.get('windowSamples') or []) if declared else 0,
        'policyCounts': policy_counts,
        'checkedFiles': checked_files,
        'violations': violations,
        'warnings': warnings,
    }
    code = 1 if violations else 0
    payload['exitCode'] = code
    return payload, code


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--plan', required=True, help='ui-implementation-plan.json 路径')
    ap.add_argument('--source', action='append',
                    help='原生源码根目录，可重复；给了才核对「声明有没有被照做」')
    ap.add_argument('--targets', help='adaptive-targets.json 路径（核对采样是否落成目标）')
    ap.add_argument('--output', help='把结论同时写入该路径')
    ap.add_argument('--plan-only', action='store_true',
                    help='只校验计划自身，不看源码')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    payload, code = run(Path(args.plan), args.source, args.targets, args.plan_only)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')

    if not args.quiet:
        if payload.get('status') == 'error':
            print(f"宽度轴校验无法执行：{payload.get('reason')}", file=sys.stderr)
        elif payload.get('status') == 'not-declared':
            print('宽度轴：计划未声明 adaptiveLayout（本页按只交付手机档处理）')
        else:
            print(f"宽度轴：{payload['windowSampleCount']} 个采样，"
                  f"policy 分布 {payload['policyCounts'] or '{}'}，"
                  f"核对源码 {payload['checkedFiles']} 个文件")
            for item in payload['violations']:
                where = item.get('file') or payload['plan']
                line = f":{item['line']}" if item.get('line') else ''
                print(f"  违规 [{item['kind']}] {Path(where).name}{line} — {item['detail']}")
            for item in payload['warnings']:
                print(f'  告警：{item}')
            print(f"结论：{payload['status']}"
                  f"（违规 {len(payload['violations'])} 项）")
    return code


if __name__ == '__main__':
    raise SystemExit(main())
