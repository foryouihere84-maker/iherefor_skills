#!/usr/bin/env python3
"""字体链审计：基准渲染时 CSS 声明的字体族有没有真的用上。

**为什么需要这个脚本。** run 011 的字体链事故是这样发生的：Lanhu 导出页的 CSS 写着
``font-family: AvenirLT-Black``，但页面里 ``@font-face`` 规则数为 0、没有字体文件、
也没有 generic fallback。Chromium 于是**静默回落到默认衬线字体 Times**。后果不是
「基准图明显错了」，而是「基准图自洽地错」：

* DOM 事实表与基准图当然一致 —— 两者是同一套回落字体渲染出来的，``domVsReference``
  判 ``aligned``；
* 元素级对齐审计于是把不一致归给 App 实现侧。

也就是说，只看工具结论的 Agent 会照着坏基准去改 App 的字体，越改越远。而**只读 CSS
声明的 ``fontFamily``** 更糟：那正是声明，不是结果。声明 ≠ 结果，这就是本脚本存在的理由。

**判据。** 唯一可信的证据是运行时**实际参与排版**的字体族 —— 也就是
``page-facts.json`` 里各文本元素的 ``primaryFont`` / ``fontsResolved``（由 CDP
``CSS.getPlatformFontsForNode`` 采集），以及 ``browser-meta.json`` 的
``fontProbe.fontFaceRules``。本脚本把两者逐元素对起来：

    声明的族（element.fontFamily / element.style.fontFamily）
        vs
    实际用上的族（element.primaryFont / element.fontsResolved）

两者对不上 ⇒ 发生了一次字体替换，而且要改的是**基准的字体栈**（补 ``@font-face``
或换成运行时真实存在的族），改完重新渲染基准、重新测量，再谈 App 侧还有没有残余差异。

用法：

    python3 scripts/audit_fonts.py \\
        --page-facts pages/<page>/reference/page-facts.json \\
        --browser-meta pages/<page>/reference/browser-meta.json \\
        --output    pages/<page>/runs/<run>/diff/font-chain.json

``--browser-meta`` 可选；不给就少一层机制证据（``@font-face`` 规则数），判定照样成立。

退出码：0 = 未发现替换；1 = 发现替换（账在基准侧）；2 = 证据不足，无法判定。

判定讲究「闸门要准，不是要响」：族名格式差异（``Avenir-Medium`` 与 ``Avenir Medium``
是同一个族的两种写法）、系统关键字（``-apple-system`` / ``system-ui`` 本就没有可比对的
族名字符串）、一次性测量失败，都会被识别出来并**排除在违规之外**，而不是凑成一个替换数。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FIX_SIDE_BASELINE = 'baseline'
FIX_SIDE_NONE = 'none'


def load_json(path):
    """读 JSON，失败时返回 (None, 错误信息)。"""
    try:
        return json.loads(Path(path).read_text(encoding='utf-8')), None
    except FileNotFoundError:
        return None, f'文件不存在：{path}'
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def norm_family(value) -> str:
    """把一个族名归一化成可比对的键。

    归一化是必要的，不是宽容：``Avenir-Medium``（CSS 声明里的写法）与
    ``Avenir Medium``（CDP 报回的 familyName）是**同一个族**，逐字符比会把它们判成
    一次替换 —— 实测该页 18 个文本元素里 14 个都是这种格式差异，全都报成替换就等于
    把闸门焊死。归一化之后，那页只剩下 2 处真替换（两个 ``AvenirLT-*``）。

    能抹掉的只有**字形**后缀（见 ``STYLE_SUFFIXES``）：它们描述同一族的斜体/正体变体，
    而 CDP 的 ``postScriptName`` 常带、CSS 声明常不带（``Times`` vs ``Times-Roman``）。
    """
    text = str(value or '').strip()
    text = text.strip('"').strip("'").strip()
    text = re.sub(r'!\s*important', '', text, flags=re.I)
    text = re.sub(r'[\s_\-]+', ' ', text).strip().lower()
    words = text.split()
    while len(words) > 1 and words[-1] in STYLE_SUFFIXES:
        words.pop()
    return ' '.join(words)


# 族名尾部可以安全抹掉的**字形**后缀。
#
# **字重后缀（Bold / Black / Heavy / Medium / Light / Thin / Semibold …）故意不在
# 这个表里。** 它们通常是族标识的一部分（``Avenir Heavy`` 与 ``Avenir Black`` 是两个族），
# 抹掉就会把「声明的族没落地」静默成「匹配」—— 那正是闸门失灵的方向。想查字重看 CSS 的
# ``font-weight``，不要靠族名。
#
# 同理 ``LT`` / ``MT`` 之类代字号后缀也不能进表：``AvenirLT-Black`` 与 ``Avenir-Black``
# 是两个不同的族（前者才是那次事故里根本不存在的那个），抹掉就把事故本身抹平了。
STYLE_SUFFIXES = {'roman', 'italic', 'oblique', 'regular', 'book', 'normal'}

# 系统关键字：由平台解析成「系统 UI 字体」，没有可比对的族名字符串。
# 命中它们却比不相等，**不构成**替换证据。
#
# 必须以**归一化之后**的形式存放：归一化会把 ``-apple-system`` 变成 ``apple system``、
# ``sans-serif`` 变成 ``sans serif``，直接拿带连字符的原字面去比永远比不中。
SYSTEM_KEYWORDS = {norm_family(name) for name in (
    '-apple-system', 'system-ui', 'ui-serif', 'ui-sans-serif', 'ui-monospace',
    'ui-rounded', 'blinkmacsystemfont',
)}

# generic 族：浏览器按自己的默认字体解析。命中它们说明作者把回落写进了栈里，
# 但真正想要的族仍然没落地 —— 属于替换，只是没有「静默」那么严重。
GENERIC_KEYWORDS = {norm_family(name) for name in (
    'serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'math',
)}


def declared_families(element) -> list:
    """元素**声明**的字体族（CSS 侧事实），按栈顺序返回。

    优先读扁平 ``fontFamily``（简化 schema / 评测素材），再读 ``style.fontFamily``
    （render_reference.mjs 的真实输出）。**绝不**回落到 ``primaryFont``：那正是要区分
    的两侧，混起来这个脚本就没有意义了。
    """
    raw = element.get('fontFamily')
    if raw is None:
        raw = element.get('fontFamilies')
    if raw is None:
        raw = element.get('cssFontFamily')
    if raw is None:
        raw = (element.get('style') or {}).get('fontFamily')
    if raw is None:
        return []
    items = raw if isinstance(raw, (list, tuple)) else str(raw).split(',')
    out = []
    for item in items:
        text = str(item or '').strip().strip('"').strip("'").strip()
        if text:
            out.append(text)
    return out


def resolved_families(element) -> list:
    """元素**实际用上**的字体族（运行时事实），主字体在前。

    只认 ``primaryFont`` / ``fontsResolved``。这两个字段由 CDP
    ``CSS.getPlatformFontsForNode`` 采集，是「渲染到底用了什么字」的唯一直接证据；
    ``document.fonts.check()`` 对不存在的族同样返回 true（见 browser-meta 的
    ``fontProbe.probeNote``），不能用来判断 fallback。
    """
    raw = []

    def add(entry):
        if not entry:
            return
        if isinstance(entry, str):
            raw.append(entry)
            return
        if isinstance(entry, dict):
            for key in ('familyName', 'family', 'name', 'fontFamily'):
                if entry.get(key):
                    raw.append(str(entry[key]))
            if entry.get('postScriptName'):
                raw.append(str(entry['postScriptName']))

    add(element.get('primaryFont'))
    for entry in (element.get('fontsResolved') or []):
        add(entry)

    seen, unique = set(), []
    for item in raw:
        key = norm_family(item)
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def is_text_element(element) -> bool:
    """这个元素是否**自己排版了文本**。

    ``text`` 是 innerText 聚合值（含后代文本），只有祖先容器才有意义；判断「谁排版了
    文字」一律用 ``ownsText`` / ``ownText``。旧 schema 没有这两个标记时退化为
    「有 text 且没有子孙元素」——那类事实表本来就没做字体测量（没有 ``primaryFont``），
    后面会判成证据不足，不会因为判错元素而得到假结论。
    """
    if element.get('ownsText') or element.get('ownText'):
        return True
    if 'ownsText' in element or 'ownText' in element:
        return False
    has_children = bool(element.get('children') or element.get('childIndexes'))
    return bool(str(element.get('text') or '').strip()) and not has_children


def lookup(container, *names):
    """从 dict 里按顺序取第一个存在的键值，用于兼容字段改名。"""
    for name in names:
        if isinstance(container, dict) and container.get(name) is not None:
            return container[name]
    return None


def classify_element(element) -> dict:
    """给一个文本元素定分类：matched / substituted / ambiguous / unmeasured。"""
    declared = declared_families(element)
    resolved = resolved_families(element)
    declared_keys = {norm_family(f) for f in declared if norm_family(f)}
    resolved_keys = {norm_family(f) for f in resolved if norm_family(f)}

    record = {
        'index': element.get('index'),
        'tag': element.get('tag'),
        'text': (element.get('ownText') or element.get('text') or '')[:80],
        'declaredFontFamily': declared,
        'resolvedFontFamily': resolved,
        'isCustomFont': lookup(element.get('primaryFont') or {}, 'isCustomFont'),
        'advanceWidth': lookup(element.get('textMetrics') or {}, 'advanceWidth'),
        'kind': None,
        'mechanism': None,
        'severity': None,
    }

    if not declared or not resolved:
        record['kind'] = 'unmeasured'
        record['mechanism'] = 'no-declaration' if not declared else 'no-runtime-font'
        return record

    if declared_keys & resolved_keys:
        record['kind'] = 'matched'
        return record

    system_hits = sorted(declared_keys & SYSTEM_KEYWORDS)
    if system_hits:
        # 系统关键字本来就映射到平台字体，没有可比对的族名字符串：不构成替换证据。
        record['kind'] = 'ambiguous'
        record['mechanism'] = 'system-keyword'
        record['severity'] = 'low'
        return record

    generic_hits = sorted(declared_keys & GENERIC_KEYWORDS)
    if generic_hits:
        # 作者把 generic 写进了栈：回落是栈内行为，但想要的族仍然没落地。
        record['kind'] = 'substituted'
        record['mechanism'] = 'generic-fallback'
        record['severity'] = 'medium'
        return record

    # 栈里既没有可比对的族、也没有 generic：浏览器只能用它自己的默认字体。
    record['kind'] = 'substituted'
    record['mechanism'] = 'silent-default-fallback'
    record['severity'] = 'high'
    return record


def font_probe(browser_meta) -> dict:
    """收敛 browser-meta 里的字体探测信息；缺失一律记 None，不假装。"""
    probe = (browser_meta or {}).get('fontProbe') or {}
    measurement = (browser_meta or {}).get('fontMeasurement')
    join = (browser_meta or {}).get('fontJoin')

    rules = probe.get('fontFaceRules')
    families = probe.get('declaredFamilies') or []

    out = {
        'probeNote': probe.get('probeNote'),
        'fontFaceRules': len(rules) if isinstance(rules, (list, tuple)) else None,
        'stylesheetFamilies': [],
        'measurementOk': None,
        'joinOk': None,
        'textMarkMismatchCount': None,
        'unjoinedIndexes': [],
        'measuredElements': None,
        'textElements': None,
    }
    for entry in (families if isinstance(families, (list, tuple)) else []):
        text = str(entry or '')
        if not text:
            continue
        for piece in text.split(','):
            piece = piece.strip().strip('"').strip("'").strip()
            if piece and piece not in out['stylesheetFamilies']:
                out['stylesheetFamilies'].append(piece)
    if isinstance(measurement, dict):
        out['measurementOk'] = measurement.get('ok')
        out['measurementError'] = measurement.get('error')
    if isinstance(join, dict):
        out['joinOk'] = join.get('ok')
        out['textMarkMismatchCount'] = join.get('textMarkMismatchCount')
        out['unjoinedIndexes'] = join.get('unjoinedIndexes') or []
        out['measuredElements'] = join.get('joinedElements')
        out['textElements'] = join.get('textElements')
    return out


def audit(page_facts, browser_meta, page_facts_path=None):
    """返回 (结果文档, 退出码)。"""
    probe = font_probe(browser_meta)
    result = {
        'schemaVersion': 1,
        'pageFacts': str(page_facts_path) if page_facts_path else None,
        'browserMeta': None,
        'viewport': page_facts.get('viewport'),
        'styleDeclaredFamilies': probe['stylesheetFamilies'],
        'declaredFontFamily': [],
        'resolvedFontFamily': [],
        'missingFamilies': [],
        'landedFamilies': [],
        'fontFaceRuleCount': probe['fontFaceRules'],
        'fontMeasurementOk': probe['measurementOk'],
        'fontJoinOk': probe['joinOk'],
        'textMarkMismatchCount': probe['textMarkMismatchCount'],
        'substituted': None,
        'status': 'insufficient-evidence',
        'severity': None,
        'mechanism': None,
        'textElementCount': 0,
        'measuredElementCount': 0,
        'coverage': None,
        'affectedElements': [],
        'ambiguousElements': [],
        'unmeasuredElements': [],
        'evidence': [],
        'fixSide': FIX_SIDE_NONE,
        'verdict': '',
        'warnings': [],
    }
    evidence = result['evidence']
    warnings = result['warnings']

    if probe['probeNote']:
        evidence.append(f'browser-meta: {probe["probeNote"]}')

    # ---- 测量链路本身可不可信：不可信就**不下结论**，哪怕元素上还留着字体字段 ----
    # 这是一道硬闸门，不是告警：元素上的 primaryFont 是「上一次采集留下的结果」时，
    # 它照样长得像一份正常数据 —— 拿它下结论比没有数据更危险。宁可判证据不足。
    blocked = None
    if probe['measurementOk'] is False:
        blocked = 'font-measurement-failed'
        warnings.append(
            'browser-meta.fontMeasurement.ok = false'
            f'（{probe.get("measurementError") or "未记录原因"}）：'
            '本次没有拿到运行时字体，元素上残留的字体字段不能当成本次证据')
    if probe['joinOk'] is False or (probe['textMarkMismatchCount'] or 0) > 0:
        blocked = 'font-attribution-unreliable'
        warnings.append(
            'browser-meta.fontJoin.ok = false'
            f'（textMarkMismatchCount={probe["textMarkMismatchCount"]}）：'
            '标记的 index 与采集的 index 空间漂移，primaryFont 可能归属到隔壁元素，'
            '本次字体归属不可信')

    elements = [e for e in (page_facts.get('elements') or [])]
    texts = [e for e in elements if is_text_element(e)]
    result['textElementCount'] = len(texts)

    records = [classify_element(e) for e in texts]
    matched = [r for r in records if r['kind'] == 'matched']
    substituted = [r for r in records if r['kind'] == 'substituted']
    ambiguous = [r for r in records if r['kind'] == 'ambiguous']
    unmeasured = [r for r in records if r['kind'] == 'unmeasured']

    judged = matched + substituted + ambiguous
    result['measuredElementCount'] = len(judged)
    if texts:
        result['coverage'] = round(len(judged) / len(texts), 4)

    declared_all, resolved_all = [], []
    for record in records:
        for family in record['declaredFontFamily']:
            if family not in declared_all:
                declared_all.append(family)
        for family in record['resolvedFontFamily']:
            if family not in resolved_all:
                resolved_all.append(family)
    result['declaredFontFamily'] = declared_all
    result['resolvedFontFamily'] = resolved_all

    for record in substituted:
        for family in record['declaredFontFamily']:
            if family not in result['missingFamilies']:
                result['missingFamilies'].append(family)
        for family in record['resolvedFontFamily']:
            if family not in result['landedFamilies']:
                result['landedFamilies'].append(family)
    result['affectedElements'] = substituted
    result['ambiguousElements'] = ambiguous
    result['unmeasuredElements'] = unmeasured

    # ---- 证据不足：什么都比不了，或者证据来源不可信，就不要给结论 ----
    if blocked:
        result['reason'] = blocked
    elif not texts:
        result['reason'] = 'no-text-elements'
        warnings.append(
            '事实表里找不到「自己排版了文本」的元素（ownsText/ownText 全为空）：'
            '没有可比对的声明与结果，无法判定字体链')
    elif not judged:
        result['reason'] = 'no-runtime-font'
        warnings.append(
            f'{len(texts)} 个文本元素都没有运行时字体字段（primaryFont / fontsResolved）：'
            '这份事实表没做过字体测量（render_reference.mjs 的 CDP 采集未生效或被裁掉），'
            '仅凭 CSS 声明不能判断字体有没有被替换')

    if not judged or blocked:
        result['substituted'] = None
        result['affectedElements'] = []
        result['verdict'] = (
            '证据不足：无法从当前产物判断基准渲染有没有发生字体替换。'
            '请用 scripts/render_reference.mjs 重新渲染基准（它会调 CDP '
            'CSS.getPlatformFontsForNode 采 primaryFont / fontsResolved），'
            '确认 fontMeasurement.ok 与 fontJoin.ok 都为 true 后再跑本脚本。')
        if not evidence:
            evidence.append('没有任何元素同时具备「声明的族」与「运行时实际使用的族」')
        return result, 2

    # ---- 有可判定的元素了 ----
    if unmeasured:
        warnings.append(
            f'{len(unmeasured)} 个文本元素只拿到声明、没拿到运行时字体'
            f'（如 index {[r["index"] for r in unmeasured][:5]}）：'
            f'结论只覆盖已测量的 {len(judged)} 个')
    if ambiguous:
        warnings.append(
            f'{len(ambiguous)} 个元素声明的是系统关键字'
            f'（{sorted({k for r in ambiguous for k in r["declaredFontFamily"]})}）：'
            '系统关键字由平台解析成系统 UI 字体，族名字符串无法与运行时对比，未计入判定')
    if probe['fontFaceRules'] == 0:
        evidence.append(
            'browser-meta.fontProbe.fontFaceRules = []：本页没有任何 @font-face 规则，'
            '声明的族除非系统已安装，否则浏览器只能回落到自己的默认字体')
    elif probe['fontFaceRules']:
        evidence.append(
            f'browser-meta.fontProbe.fontFaceRules 有 {probe["fontFaceRules"]} 条：'
            '声明里的自定义族至少有一个可加载来源')

    if not substituted:
        result['status'] = 'clean'
        result['substituted'] = False
        result['mechanism'] = None
        evidence.append(
            f'{len(matched)} 个文本元素声明的族都在运行时真正参与排版'
            + (f'（其中 index {matched[0]["index"]} 声明 '
               f'{" / ".join(matched[0]["declaredFontFamily"])} 且解析为 '
               f'{" / ".join(matched[0]["resolvedFontFamily"])}）' if matched else ''))
        result['verdict'] = (
            '基准渲染的字体链是通的：CSS 声明的族与运行时实际使用的族一致，'
            '没有发生替换。基准图可以当证据用。')
        return result, 0

    # 有替换。账记在基准侧。
    result['status'] = 'substituted'
    result['substituted'] = True
    severities = {r['severity'] for r in substituted}
    result['severity'] = 'high' if 'high' in severities else ('medium' if 'medium' in severities else 'low')
    mechanisms = []
    for record in substituted:
        if record['mechanism'] not in mechanisms:
            mechanisms.append(record['mechanism'])
    result['mechanism'] = '+'.join(mechanisms)

    for record in substituted:
        declared = ' / '.join(record['declaredFontFamily'])
        resolved = ' / '.join(record['resolvedFontFamily'])
        # 证据必须落到具体元素上：只有一条全局结论无法复核，也定位不到问题范围。
        detail = (f'元素 index {record["index"]}（{record["tag"]}'
                  f'{"「" + record["text"] + "」" if record["text"] else ""}）'
                  f'声明 {declared}，实际用上 {resolved}')
        if record['advanceWidth'] is not None:
            detail += f'；排版宽度 {record["advanceWidth"]}px（字体被替换时该值必然变化）'
        evidence.append(detail + f' —— 机制：{record["mechanism"]}')

    if matched:
        # 对照组是这份判定里最有价值的一条证据：同一个页面上，声明能被满足的元素
        # 确实解析成了声明的族 ⇒ 测量链路是通的，所以上面那些不匹配不是测量噪声。
        sample = matched[0]
        evidence.append(
            f'对照组：index {sample["index"]} 声明 '
            f'{" / ".join(sample["declaredFontFamily"])}，运行时也用上了 '
            f'{" / ".join(sample["resolvedFontFamily"])} —— 测量链路本身是通的，'
            '所以上面这些不匹配不是测量噪声')
    else:
        evidence.append('全部已测量的文本元素都用了声明之外的族：整页都在回落字体上渲染')

    result['fixSide'] = FIX_SIDE_BASELINE
    hint = ''
    if result['mechanism'] == 'silent-default-fallback':
        hint = ('声明的族既没落到运行时、栈里也没有 generic 兜底，浏览器只能用自己的'
                '默认字体 —— 这是最隐蔽的一类：基准图看起来「自洽」，DOM 与基准图一起错。')
    result['verdict'] = (
        f'基准渲染发生了字体替换（{" / ".join(result["missingFamilies"])} → '
        f'{" / ".join(result["landedFamilies"])}，影响 {len(substituted)} 个文本元素）。'
        f'{hint}先修**基准的字体栈**（补 @font-face 或换成运行时真实存在的族），'
        '重新渲染基准、重新测量，再判断 App 侧还有没有残余差异 —— '
        '不要照着这份基准去改 App 的字体。')
    return result, 1


def print_summary(result):
    print(f"font-chain status={result['status']} fixSide={result['fixSide']}")
    if result.get('declaredFontFamily'):
        print(f"  declared: {' / '.join(result['declaredFontFamily'])}")
    if result.get('resolvedFontFamily'):
        print(f"  resolved: {' / '.join(result['resolvedFontFamily'])}")
    print(f"  textElements={result['textElementCount']} measured={result['measuredElementCount']}"
          f" coverage={result['coverage']}")
    for warning in result.get('warnings') or []:
        print(f"  warn: {warning}")
    for line in result.get('evidence') or []:
        print(f"  · {line}")
    print(f"  → {result.get('verdict')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--page-facts', required=True,
                    help='页面级 reference/page-facts.json（元素级事实表，含运行时字体）')
    ap.add_argument('--browser-meta',
                    help='页面级 reference/browser-meta.json（可选；提供 @font-face 规则数'
                         '与测量链路状态）')
    ap.add_argument('--output', required=True, help='写入字体链审计 JSON')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    page_facts, error = load_json(args.page_facts)
    if page_facts is None:
        print(f'无法读取 page-facts：{error}', file=sys.stderr)
        return 2
    if not isinstance(page_facts, dict):
        print('page-facts 不是对象', file=sys.stderr)
        return 2

    browser_meta = None
    if args.browser_meta:
        browser_meta, error = load_json(args.browser_meta)
        if browser_meta is None:
            print(f'无法读取 browser-meta：{error}', file=sys.stderr)
            return 2

    result, code = audit(page_facts, browser_meta, page_facts_path=Path(args.page_facts))
    if args.browser_meta:
        result['browserMeta'] = str(Path(args.browser_meta))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    if not args.quiet:
        print_summary(result)
    return code


if __name__ == '__main__':
    sys.exit(main())
