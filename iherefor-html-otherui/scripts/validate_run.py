#!/usr/bin/env python3
"""校验一次 run 是否满足 references/artifact-contract.md 的产物契约。

本脚本只读 run 目录来判定；唯一的例外是给了 ``--source`` 时会把「布局约束有没有照计划
声明的方式实现」的结论落成 ``diff/layout-proportions.json``（源码在 run 目录之外，那条
结论需要单独留证）。契约以 artifact-contract.md 为准，本脚本是其可执行版本：文档改了，
这里必须同步改，`scripts/tests/` 下有对应回归。

用法：
    python3 scripts/validate_run.py --run <run-dir> [--source <源码根>] [--json <out-path>]

``--source`` 会额外核对「计划声明的布局约束有没有被照做」——**尺寸是常量、位置相对直接
父视图**，那是本 skill 的硬约束。但它看的是原生源码，而源码在 run 目录之外，所以 run
目录本身答不了这个问题。给了 ``--source`` 就硬判；没给就只告警，不假装已经验证过。

退出码：0 = 满足契约；1 = 违反契约；2 = 用法或读取错误。
"""
import argparse
import json
import struct
import subprocess
import sys
import tempfile
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


LAYOUT_PROPORTIONS = 'scripts/check_layout_proportions.py'
# 源码合规结论的落盘位置。与上面的脚本路径是两回事：交叉校验看的是**结论文件**，
# 所以报错里要点出文件名，让人知道该去翻哪一份。
LAYOUT_REPORT = 'diff/layout-proportions.json'
AUDIT_FONTS = 'scripts/audit_fonts.py'


def check_font_chain(run_dir, gate_status, warnings, warn_only=False):
    """核对基准渲染的字体链：声明的字体族有没有真的用上。

    这一条防的是 run 011 的字体链事故。基准是「自洽地错」的：CSS 声明 ``AvenirLT-Black``、
    ``@font-face`` 规则数为 0、无 generic fallback ⇒ Chromium 静默回落到 Times；
    DOM 与基准图因为用了同一套回落字体而互相印证，对齐审计于是把不一致归给 App 侧。
    所以只要这份基准还在被当成可信证据（``reference`` 闸门为 pass），就必须拦下。

    两层，与 alignment.json / visualDiff 的交叉校验同形：

    1. **现算**：事实表与元数据都在页面级 ``reference/`` 下，读得到就直接跑一遍审计
       （结论写进临时目录，不改动 run）。它比落盘结论更可信 —— 落盘文件是产物的一部分，
       而这里看的是原始事实。
    2. **与闸门交叉**：现算或已落盘的 ``diff/font-chain.json`` 判出了替换，而
       ``delivery-gate.status.reference`` 仍是 pass，就是自相矛盾。若闸门已经诚实地
       记成非 pass，不重复报错，只提示。

    ``warn_only`` 供 legacy run 使用：legacy 没有闸门可比，不能硬判，但「基准字体链断了」
    这件事本身就是纯信息 —— 而 legacy 页面（含 run 011 那次事故）恰恰最容易踩这个坑，
    所以至少要说出来，不能因为跳过产物检查就顺手也跳过它。
    """
    page_dir = run_dir.parent.parent
    facts = page_dir / 'reference' / 'page-facts.json'
    problems = []
    reference_gate = gate_status.get('reference')

    script = Path(__file__).resolve().parent / 'audit_fonts.py'
    fresh = None
    if not script.is_file():
        warnings.append(f'未找到 {AUDIT_FONTS}，跳过基准字体链核对')
    elif not facts.is_file():
        warnings.append(
            '未提供页面级 reference/page-facts.json：无法核对基准渲染有没有发生字体替换。'
            '基准字体被静默替换时，基准图会「自洽地错」——DOM 与基准图互相印证，'
            '对齐审计只能把不一致归给 App 侧。')
    else:
        with tempfile.TemporaryDirectory() as scratch:
            scratch_report = Path(scratch) / 'font-chain.json'
            proc = _run_font_audit(script, facts, page_dir, scratch_report)
            if proc is None:
                warnings.append('字体链审计无法执行，跳过核对')
            elif proc.returncode == 2:
                fresh, _ = load_json(scratch_report)
                reason = (fresh or {}).get('reason') or '证据不足'
                warnings.append(
                    f'基准字体链无法判定（{reason}）：请先确认 '
                    'reference/browser-meta.json 的 fontMeasurement.ok 与 fontJoin.ok 均为 true')
            else:
                fresh, _ = load_json(scratch_report)
                if fresh is None:
                    warnings.append('字体链审计没有产出结论')

    on_disk, _ = load_json(run_dir / 'diff' / 'font-chain.json')
    for label, report in (('现算', fresh), ('已落盘', on_disk)):
        if not isinstance(report, dict) or report.get('substituted') is not True:
            continue
        missing = ' / '.join(report.get('missingFamilies') or []) or '声明的族'
        landed = ' / '.join(report.get('landedFamilies') or []) or '声明之外的族'
        count = len(report.get('affectedElements') or [])
        detail = (f'{label}的字体链结论：{missing} 没有落地，运行时实际用的是 {landed}'
                  f'（影响 {count} 个文本元素）')
        if reference_gate == 'pass':
            problems.append(
                f'{detail}，但 delivery-gate.status.reference 记录为 pass：'
                '基准图是「自洽地错」的，DOM 与它一起错，所以对齐审计会把问题归给 App —— '
                '先修基准的字体栈（补 @font-face 或换成运行时真实存在的族）并重渲染基准，'
                '再谈 App 侧')
        elif reference_gate is None:
            warnings.append(
                f'{detail}；本次没有 reference 闸门可对照（legacy run 或闸门未记录），'
                '不硬判，但必须先修基准字体栈并重渲染、重新测量，再谈 App 侧')
        else:
            warnings.append(
                f'{detail}；reference 闸门已记录为 {reference_gate!r}，不重复报错，'
                '但必须先修基准字体栈并重渲染，再重新测量')
        break

    if fresh is None and on_disk is None and facts.is_file():
        warnings.append(
            '未提供 diff/font-chain.json：建议跑 scripts/audit_fonts.py 把字体链结论落盘，'
            '否则「基准用的字体对不对」这件事没有可复核的证据')
    # 审计自己记下的告警（部分元素没测到 / 系统关键字无法比对）要透出来，
    # 免得「结论覆盖了多少」这件事被一个 status 字段盖住。
    for report in (fresh, on_disk):
        if isinstance(report, dict):
            for item in report.get('warnings') or []:
                warnings.append(f'字体链审计：{item}')
            break
    if warn_only and problems:
        warnings.extend(problems)
        return []
    return problems


def _run_font_audit(script, facts, page_dir, report_path):
    """调用字体链审计。用当前解释器，保证与被测脚本同一套依赖。"""
    args = [sys.executable, str(script), '--page-facts', str(facts),
            '--output', str(report_path), '--quiet']
    meta = page_dir / 'reference' / 'browser-meta.json'
    if meta.is_file():
        args += ['--browser-meta', str(meta)]
    try:
        return subprocess.run(args, capture_output=True, text=True)
    except OSError:
        return None


def check_layout_proportions(run_dir, source_roots, gate_status, warnings):
    """核对该 run 的布局约束契约，返回违反项。

    三层，各自的证据强度不同，不能混：

    1. **计划质量**：计划声明了 ``layoutProportions.regions`` 时，它必须结构完好
       （五类 kind 各自带齐必需的字段、区域基准与父视图一致、禁止清单只指向
       ``proportional``）。这一步只读计划，判起来最硬 —— 而且复用校验器本身，
       不在这里重写一份判定逻辑。
    2. **源码合规**：只有给了 ``--source`` 才谈得上。给了就扫源码并把结论落成
       ``diff/layout-proportions.json``；没给就只告警，绝不假装验证过。
    3. **与闸门交叉**：已落盘的 ``diff/layout-proportions.json`` 若判 fail，
       而 ``delivery-gate.status.implementation`` 是 pass，那就是自相矛盾 ——
       和「对齐审计 needs-review 却 visualDiff=pass」是同一类问题。

    **这里的口径是两轴的**：尺寸是常量（设计稿的封闭值，写成字面量）、
    位置相对直接父视图（贴边写约束闭合、居中写对齐锚点）。所以衡量合规与否不是
    「有没有比例原语」这一条，而是「计划怎么声明、源码有没有照它声明的方式实现」。
    """
    plan_path = run_dir / 'ui-implementation-plan.json'
    plan, _ = load_json(plan_path) if plan_path.is_file() else (None, None)
    declared = isinstance(plan, dict) and bool(
        (plan.get('layoutProportions') or {}).get('regions'))

    if plan is None:
        return []

    script = Path(__file__).resolve().parent / 'check_layout_proportions.py'
    if not declared:
        warnings.append(
            'ui-implementation-plan.json 未声明 layoutProportions：组件之间的布局关系必须'
            '逐条声明（尺寸是常量、位置相对直接父视图），否则无从核对「有没有照抄探针'
            '设备上的绝对值」。用 scripts/layout_proportions.py 生成后并入计划')
        return []

    if not script.is_file():
        warnings.append(f'未找到 {LAYOUT_PROPORTIONS}，跳过布局约束核对')
        return []

    problems = []
    # 第 1 层：计划质量。只读计划，不依赖源码，所以**总是**跑 ——
    # 计划是 Agent 自己写的，kind 写错、贴边关系带上比例系数、区域基准与父视图对不上
    # 都是回不去的硬伤。
    with tempfile.TemporaryDirectory() as scratch:
        scratch_report = Path(scratch) / 'plan-only.json'
        proc = _run_checker(script, plan_path, [], scratch_report, plan_only=True)
        if proc is None or proc.returncode == 2:
            warnings.append('布局约束校验器无法执行，跳过计划质量核对')
        else:
            plan_report, _ = load_json(scratch_report)
            if plan_report is None:
                warnings.append('布局约束校验器（--plan-only）没有产出结论')
            else:
                problems.extend(
                    f'布局约束（计划本身）：{_describe(item)}'
                    for item in (plan_report.get('violations') or []))

    # 第 2 层：源码合规。只有给了 --source 才谈得上，结论落成 diff/layout-proportions.json。
    report_path = run_dir / LAYOUT_REPORT
    report = None
    if source_roots:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        proc = _run_checker(script, plan_path, source_roots, report_path)
        if proc is None:
            warnings.append('布局约束校验器无法执行，跳过源码合规核对')
        elif proc.returncode == 2:
            warnings.append(f'布局约束校验器用法错误，未取得结论：{proc.stderr.strip()[:200]}')
        else:
            report, _ = load_json(report_path)
            if report is None:
                warnings.append('布局约束校验器没有产出结论文件')
            else:
                for item in report.get('violations') or []:
                    where = item.get('file') or report.get('plan')
                    line = f":{item['line']}" if item.get('line') else ''
                    problems.append(
                        f'布局约束违规 [{Path(where).name}{line}] {_describe(item)}')
                if report.get('violations'):
                    counts = report.get('relationKindCounts') or {}
                    kinds = ' '.join(f'{kind}={count}'
                                     for kind, count in counts.items() if count)
                    problems.append(
                        f'布局约束：计划声明了 {report.get("relationCount")} 条关系（{kinds}），'
                        f'源码里的比例原语 {report.get("proportionalIdiomCount")} 处、'
                        f'贴边原语 {report.get("pinnedIdiomCount")} 处。尺寸应当是常量'
                        '（设计稿的封闭值）、位置应当相对直接父视图（贴边写约束闭合、'
                        '居中写对齐锚点），不得照抄探针设备上的绝对值')
    else:
        report, _ = load_json(report_path)
        if report is None:
            relation_count = sum(len(r.get("relations") or [])
                                 for r in (plan["layoutProportions"]["regions"] or []))
            warnings.append(
                f'未核对源码里的布局约束（未传 --source）：计划声明了 {relation_count} '
                '条布局关系，但源码是否照它声明的方式实现尚未验证。'
                '跑 scripts/check_layout_proportions.py --plan ui-implementation-plan.json '
                '--source <源码根>，或用 validate_run.py --source <源码根>')

    # 第 3 层：与闸门交叉。已落盘的结论判 fail 而 implementation 仍写 pass，就是自相矛盾。
    if report is not None and report.get('status') not in (None, 'pass'):
        if gate_status.get('implementation') == 'pass':
            problems.append(
                f'布局约束校验判 {report.get("status")}'
                f'（{len(report.get("violations") or [])} 项违规），'
                '但 delivery-gate.status.implementation 记录为 pass，'
                f'与已落盘的 {LAYOUT_REPORT} 自相矛盾：'
                '计划声明的布局关系没有被照做（尺寸没写成设计常量、或位置没相对父视图），'
                'implementation 不能算通过')
    elif report is not None and report.get('ambiguousLiteralCount'):
        warnings.append(
            f'布局约束校验有 {report["ambiguousLiteralCount"]} 处待判字面量'
            '（数值小到与设计常量无法区分），需人工确认是否为设计常量')
    return problems


def _run_checker(script, plan_path, source_roots, report_path, plan_only=False):
    """调用校验器。用当前解释器，保证与被测脚本同一套依赖。"""
    args = [sys.executable, str(script), '--plan', str(plan_path),
            '--output', str(report_path), '--quiet']
    if plan_only:
        args.append('--plan-only')
    for root in source_roots:
        args += ['--source', str(root)]
    try:
        return subprocess.run(args, capture_output=True, text=True)
    except OSError:
        return None


def _describe(item):
    if item.get('kind') == 'forbidden-literal-used':
        return (f'字面量 {item.get("literal"):g} 等于设备推导值 '
                f'{item.get("deviceDerivedPt"):g}pt（{item.get("relation")}），'
                f'应当用比例 {item.get("expectedRatio")}')
    return f'{item.get("kind")}: {item.get("detail")}'


def computed_delivery_ready(gate):
    """按契约推导 delivery-ready。返回 True / False / **None**（证据不足，不猜）。

    为什么是三态而不是布尔：「查过、不够格」（False）和「没东西可查」（None）必须分开。
    合成一个布尔会得出一个很危险的结果 —— 原先写的是 ``gate.get('unsupported') or {}``，
    于是缺字段时 ``count`` 与 ``reviewedCount`` 同为 ``None``、彼此相等，推导出 **True**，
    校验器接着报「deliveryReady 记录 false，应为 true」：等于要求 Agent 把「没做人工
    复核」改成「可以交付」。计数写成字符串（``'2' == '2'``）同样会被判为复核完毕。

    None 的语义是「本次不判」，调用方必须跳过一致性核对并告警，而不是按 False 或 True 落章。
    """
    statuses = gate.get('status')
    if not isinstance(statuses, dict):
        # 旧 schema 里 status 是一个字符串（如 "pass-with-review"），无法推导。
        return None
    unsupported = gate.get('unsupported')
    if not isinstance(unsupported, dict):
        return None
    if any(not isinstance(unsupported.get(key), int) for key in ('count', 'reviewedCount')):
        return None
    if any(statuses.get(key) != 'pass' for key in GATE_KEYS):
        return False
    return unsupported['count'] == unsupported['reviewedCount']


def validate(run_dir, source_roots=None):
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
        # 产物必需项可以跳过，但「基准字体链断了」是纯信息、且 legacy 页面最容易踩，
        # 所以这里仍然跑一次，只是把硬判降级成告警。
        check_font_chain(run_dir, {}, warnings, warn_only=True)
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
            if expected is None:
                # 推不出来就说推不出来。这里**不许**退化成 False 或 True：
                # 退成 True 就是上面注释里那个「没做复核也能交付」的坑，退成 False 则会把
                # 「结构没记全」误报成「闸门没过」。缺字段本身已由上面的分支报成违规。
                warnings.append(
                    'delivery-gate 的 status / unsupported 结构不足以推导 deliveryReady：'
                    '本次跳过一致性核对，不能据此认为闸门通过')
            elif gate.get('deliveryReady') is not expected:
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
    gate_status = {}
    if gate_path.is_file():
        gate_doc, _ = load_json(gate_path)
        if isinstance(gate_doc, dict):
            candidate = gate_doc.get('status')
            # 必须是 dict：旧 schema 的 status 是字符串，若原样传下去，下面每一处
            # gate_status.get(...) 都会抛 AttributeError —— 校验器应该报「结构不对」，
            # 而不是崩在交叉校验里。
            if isinstance(candidate, dict):
                gate_status = candidate
            elif candidate is not None:
                warnings.append(
                    f'delivery-gate.status 不是对象（{type(candidate).__name__}）：'
                    '旧 schema 的字符串状态无法与证据交叉核对，闸门交叉校验已跳过')
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

            # ---- 像素比较结论：放行必须带区域级结构证据 ----
            # 「整页数值在容差内」不等于「各处都在容差内」。一次事故里两张 1206x2622
            # 的图整体差 6–21pt，整页 changedRatio 只有一个数，看不出偏差随 y 递增。
            # 所以凡是拿来放行的比较结论，都必须能指出「差在哪个区域、结构差异多大」。
            if 'changedRatio' in summary or 'structuralRatio' in summary:
                violations.extend(check_comparison_summary(summary_path.name, summary))

            # ---- 对齐审计：它判需要复核时，闸门不得为 pass ----
            if 'comparisons' in summary:
                violations.extend(check_alignment_summary(
                    summary_path.name, summary, gate_status.get('visualDiff')))
        if not (diff_dir / 'alignment.json').is_file():
            warnings.append(
                '未提供 diff/alignment.json：像素尺寸一致与整页比例都证明不了内容对齐，'
                '建议跑 scripts/audit_alignment.py 取得元素级位移证据')

    # ---- 布局约束：组件之间的尺寸与位置必须照计划声明的方式实现 ----
    # 这是本 skill 的硬约束，但它看的是原生源码；源码在 run 目录之外，所以这里
    # 分成「计划质量」与「源码合规」两层，并把结果和 implementation 闸门交叉校验 ——
    # 形状与上面 alignment.json / visualDiff 的交叉校验一致。
    violations.extend(check_layout_proportions(
        run_dir, source_roots, gate_status, warnings))

    # ---- 基准字体链：声明的字体族有没有真的用上 ----
    # 基准字体被静默替换时基准图会「自洽地错」，与 alignment.json 的交叉校验同理：
    # 工具判出来的问题，闸门不得记成 pass。
    violations.extend(check_font_chain(run_dir, gate_status, warnings))

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


def check_comparison_summary(name, summary):
    """放行类结论必须自带区域级结构差异证据。"""
    problems = []
    status = summary.get('status')
    if status not in ('pass', 'pass-with-review'):
        return problems

    structural = summary.get('structuralRatio')
    if not isinstance(structural, (int, float)):
        problems.append(
            f'{name} 判 {status} 却没有 structuralRatio：无法确认放行判定只看结构差异'
            '（仅凭 changedRatio 会把抗锯齿轮理差异算进放行线）')

    regions = summary.get('regions')
    if not isinstance(regions, list) or not regions:
        problems.append(f'{name} 判 {status} 却没有区域级差异明细（regions）')
        return problems

    limit = summary.get('maxStructuralRatio')
    if not isinstance(limit, (int, float)):
        limit = summary.get('maxChangedRatio')
    if isinstance(limit, (int, float)):
        for region in regions:
            value = region.get('structuralRatio')
            if isinstance(value, (int, float)) and value > limit:
                box = region.get('box') or {}
                problems.append(
                    f"{name} 判 {status}，但区域 row={region.get('row')} col={region.get('col')} "
                    f"(y={box.get('y')}) 的结构差异 {value:.4f} 超过上限 {limit}："
                    '整页数值通过了，局部没有 —— 必须按区域复核')
    return problems


def check_alignment_summary(name, summary, gate_visual_diff):
    """对齐审计判「需要复核」时，视觉闸门不得是 pass。"""
    problems = []
    if summary.get('status') == 'needs-review' and gate_visual_diff == 'pass':
        problems.append(
            f'{name} 判 needs-review（{summary.get("reason")}），'
            '但 delivery-gate.status.visualDiff 记录为 pass：'
            '尺寸相同、整页比例达标都不能推翻元素级位移超容差')
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run', required=True, help='run 目录，例如 .ihereforUI/pages/<page-id>/runs/<run-id>')
    ap.add_argument('--source', action='append',
                    help='原生源码根目录，可重复；给了才核对「布局约束有没有照计划声明的方式实现」')
    ap.add_argument('--json', help='把结果同时写入该路径')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    payload, code = validate(Path(args.run).resolve(), args.source)
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')
    if not args.quiet:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
