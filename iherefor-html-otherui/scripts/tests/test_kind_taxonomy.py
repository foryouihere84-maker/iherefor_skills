#!/usr/bin/env python3
"""类别表守卫：八类 kind 只许有一个真相源，别处不许出现更短的清单。

## 为什么专门测这一件事

``--source`` 侧的判据是**按类别分派**的：``intrinsic`` 不得写等值常量、``bounded``
必须有 ``>=``/``<=``、``fixed`` 必须有 ``why``…… 判据表本身是对的，但它只会被
**清单里列到的**类别触发。所以一旦某处的类别清单比真相源短，落在缺的那几类上的
关系就会**静默跳过**：脚本照跑、测试全绿、闸门照过，只有真拿这样一份计划跑一遍
才会发现压根没判。这是「两个真相源」的典型病害 —— 改口径时改了 A 忘了 B。

本仓库已经栽过一次同类的跟头：``needsReview`` 在 ``_fixed_candidate`` 与调用侧
各写了一份，改坏任一处测试照样绿（变异探针才抓到）。类别清单是同一个shape。

## 锁四件事

1. **真相源不许缩水**：``check_layout_proportions.RELATION_KINDS`` 必须是那八类，
   不多不少。想加第九类就必须先改这里 —— 这是**故意**的一步，因为加类别要同时
   决定新类别的源码侧判据，不该顺手加上就完事。
2. **声明为「穷举」的清单必须是排列**：见 ``EXHAUSTIVE_LISTS``。这些清单的用途是
   *给一个关系挑类别*，漏掉任何一类都意味着那类关系拿不到类别、下游静默跳过。
   （不是所有清单都要穷举：``("intrinsic", "bounded")`` 那种是**过滤器**，
   部分才是它的本意，所以不进这张表。区别在用途，不在长得像不像。）
3. **旧计数词不许回来**：见 ``DEAD_PHRASES``。
4. **文档里的 JSON 示例也要能过校验器认的字段与类别**：见 ``RELATION_FORBIDDEN_KEYS``。
   文档是 Agent 唯一的输入，示例里出现实现不认的字段（``relations`` 嵌套、``constant``、
   ``widthPolicy``）时，Agent 会照抄，而校验器**不报错、只静默丢掉** ——
   产物判 ``pass`` 却少了声明，这是本契约里最贵的一种错法，因为没有症状。
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"

# 真相源所在文件与常量名。
CANONICAL_FILE = SCRIPTS / "check_layout_proportions.py"
CANONICAL_NAME = "RELATION_KINDS"
# 锁的是**集合**，不锁顺序：真相源里的顺序是历史产物（旧五类 + 后来追加的三类），
# 把顺序也锁死只会制造无谓的改动。真正会出事的是「少了一类」。
CANONICAL_KINDS = ("fixed", "intrinsic", "bounded", "aspect-ratio",
                   "pinned", "proportional", "equal", "centered")

# 这两轴的分法也要锁：类别归错轴，docs 与判据就会各说一套。
SIZE_AXIS = ("fixed", "intrinsic", "bounded", "aspect-ratio")
RELATION_AXIS = ("pinned", "proportional", "equal", "centered")

# 「必须穷举」的清单：用途是给关系挑类别，漏一类就静默跳过。
# 新增这类清单时**必须**登记在这里，否则它退化成没有守卫的普通列表。
EXHAUSTIVE_LISTS = {
    "check_layout_proportions.py": ["RELATION_KINDS"],
    "audit_adaptive.py": ["KIND_FALLBACK_ORDER"],
}

# 已废弃的计数说法。只收**断言当前口径**的写法；叙述历史的近义词不在此列：
# 例如 ``layout_proportions.py`` 里「kind 从「五档」扩到「两轴八类」」是在讲沿革，
# 是这句改动的证据，误伤它等于逼着人删掉历史。
DEAD_PHRASES = {
    "五类 kind": "旧五类类别表（现为两轴八类）",
    "五类关系": "旧五类类别表（现为两轴八类）",
    "尺寸轴八类": "八类分两轴，不是「尺寸轴八类」",
    "kind 五档": "旧五档类别表（现为两轴八类）",
}

DOC_GLOBS = ("SKILL.md", "README.md", "references/*.md", "evals/*.md",
             "evals/**/*.md", "agents/*.yaml", "scripts/*.py", "scripts/**/*.py")

# 扫废弃说法时要跳过的文件。它们都**故意**把废弃说法当字面量存着：
#   * 本文件 —— DEAD_PHRASES 的键就是这些说法本身；
#   * mutation_probe.py —— 每条探针的「改成」参数就是一段含废弃说法的文本，
#     那是变异数据，不是残留。（第一版没排除它，守卫立刻把自己人抓了：
#     mutation_probe.py:251 出现废弃说法「五类 kind」。抓得对，但对象选错了。）
PHRASE_SCAN_SKIP = {"test_kind_taxonomy.py", "mutation_probe.py"}


def module_string_constants(path: Path, name: str):
    """从源码里取某个模块级赋值的字符串常量元组（按 AST 取，不靠正则）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            continue
        value = node.value
        if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
            items = []
            for element in value.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    items.append(element.value)
                else:
                    return None, f"{name} 里有非字符串元素"
            return items, None
        return None, f"{name} 不是元组/列表/集合字面量"
    return None, f"找不到模块级常量 {name}"


def iter_scripts():
    for path in sorted(SCRIPTS.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def iter_docs():
    """要扫废弃说法的文件。

    必须包含 ``scripts/**/*.py``：本轮的「五类 kind」在 ``validate_run.py`` 的
    docstring 里、「五类关系」在测试的断言消息里 —— 只扫 md 会正好漏掉它们。
    ``PHRASE_SCAN_SKIP`` 里的文件除外（它们把废弃说法当数据存着）。
    """
    seen = set()
    for pattern in DOC_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if not path.is_file() or path in seen:
                continue
            if "__pycache__" in path.parts or path.name in PHRASE_SCAN_SKIP:
                continue
            seen.add(path)
            yield path


def iter_inline_kind_collections():
    """找出源码里**写死**的 kind 集合字面量（不含已登记的穷举清单）。

    不按缩进过滤：本轮真正出问题的那个清单就嵌套在函数里的内层循环中
    （``for candidate in ('fixed', 'pinned', …)``），只扫模块级会正好漏掉它。
    """
    known = {name for names in EXHAUSTIVE_LISTS.values() for name in names}
    for path in iter_scripts():
        # 本文件自己的 SIZE_AXIS / RELATION_AXIS 就是「按轴分组」，不是挑类别，跳过。
        if path.name == Path(__file__).name:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        registered = set()
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id in known for t in node.targets):
                registered.add(id(node.value))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
                continue
            if id(node) in registered:
                continue
            values = [e.value for e in node.elts
                      if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            hits = [v for v in values if v in CANONICAL_KINDS]
            if len(set(hits)) >= 2:
                yield path, node.lineno, hits


# 文档示例里**不许出现**的关系字段，每一个都对应一次真实踩坑：
#
#   * ``relations`` —— 曾经的「一条关系同时挂两轴」写法。没有任何代码读它，
#     校验器也不报错，于是内边距声明被判 pass 而静默丢掉（最贵的一种错法：没有症状）。
#   * ``constant`` —— 贴边内边距的字段名是 ``inset``。``constant`` 全仓不存在于实现，
#     只在两份文档的示例里出现过。
#   * ``widthPolicy`` —— 它是 ``adaptiveLayout.regions[]`` 的字段，不是关系的字段；
#     而且示例里还写过 ``"bounded"`` 这个**不在 ``widthPolicy`` 枚举内**的取值。
RELATION_FORBIDDEN_KEYS = {
    "relations": "关系没有内嵌子数组：一条关系只声明一个 kind，写了不会被读取也不会报错，只会静默丢掉",
    "constant": "贴边内边距的字段名是 inset；constant 在全仓实现里不存在",
    "widthPolicy": "widthPolicy 属于 adaptiveLayout.regions[]，不是关系的字段",
}

JSON_FENCE = re.compile(r"```json\s*\n(.*?)```", re.S)
DOC_SAMPLE_GLOBS = ("SKILL.md", "README.md", "references/*.md", "evals/*.md",
                    "evals/**/*.md")


def iter_doc_relation_objects():
    """从文档的 ```json 块里抠出**关系对象**（``relations`` 数组的成员）。

    只看落在 ``relations`` 数组里的对象，不按 ``kind`` 值猜：计划里还有资源的
    ``kind``（``image`` / ``label`` / ``mcp-json`` …），按值猜会把它们一起框进来。
    抠不动的块（伪代码、多对象片段）跳过 —— 宁可少查也不能误报。
    """
    for pattern in DOC_SAMPLE_GLOBS:
        for doc in sorted(ROOT.glob(pattern)):
            if not doc.is_file() or "__pycache__" in doc.parts:
                continue
            text = doc.read_text(encoding="utf-8")
            for block_index, block in enumerate(JSON_FENCE.findall(text), start=1):
                try:
                    payload = json.loads(block)
                except Exception:
                    yield doc, block_index, None, "unparsed"
                    continue
                for relation in _relations_in(payload):
                    yield doc, block_index, relation, "ok"


def _relations_in(node):
    """抠出关系对象。认两种形态：

    ① 落在名为 ``relations`` 的数组里（正确形态）；
    ② 自己同时带 ``kind`` 与 ``relations``（**错误的嵌套形态**，正是要抓的对象）。
       它不保证落在某个 ``relations`` 数组里 —— 文档里常有单独展示一条关系的例子，
       只认 ① 会让那种写法逃掉「不许有内嵌 relations」这条判据（第一版就是这样漏的：
       只报了 ``constant``，嵌套本身没报）。

    形态 ② 命中后**继续往下钻**，内层那些带 ``constant`` 的关系也各自报一条 ——
    一次把该修的都指出来，而不是让人改一轮跑一轮。
    """
    if isinstance(node, dict):
        if "kind" in node and isinstance(node.get("relations"), list):
            yield node
        for key, value in node.items():
            if key == "relations" and isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        yield item
            else:
                yield from _relations_in(value)
    elif isinstance(node, list):
        for item in node:
            yield from _relations_in(item)


def main() -> int:
    problems: list[str] = []
    checks = 0

    canonical, error = module_string_constants(CANONICAL_FILE, CANONICAL_NAME)
    if error:
        print(f"类别表守卫无法建立：{error}")
        return 1

    checks += 1
    if set(canonical) != set(CANONICAL_KINDS):
        missing = sorted(set(CANONICAL_KINDS) - set(canonical))
        extra = sorted(set(canonical) - set(CANONICAL_KINDS))
        problems.append(
            f"{CANONICAL_FILE.relative_to(ROOT)} 的 {CANONICAL_NAME} 与锁定的两轴八类不一致：\n"
            f"      实际 {tuple(canonical)}\n      期望 {CANONICAL_KINDS}\n"
            f"      缺 {missing or '无'}，多 {extra or '无'}\n"
            "      新增/删除类别要连源码侧逐类判据一起改，并同步 references 的两轴表、"
            "scripts/tests/test_layout_proportions.py，以及本文件的 CANONICAL_KINDS")

    checks += 1
    if not set(SIZE_AXIS) | set(RELATION_AXIS) == set(canonical):
        problems.append("SIZE_AXIS / RELATION_AXIS 的并集必须等于两轴八类（本文件的锁也要维护）")

    # ① 声明为穷举的清单必须是真相源的排列。
    for filename, names in sorted(EXHAUSTIVE_LISTS.items()):
        path = SCRIPTS / filename
        checks += 1
        if not path.is_file():
            problems.append(f"EXHAUSTIVE_LISTS 登记的 {filename} 不存在：删掉这条登记，"
                            "别让它把真正的检查挡住")
            continue
        for name in names:
            values, error = module_string_constants(path, name)
            if error:
                problems.append(f"{filename} 的 {name} 取不到：{error}")
                continue
            if set(values) != set(canonical):
                missing = sorted(set(canonical) - set(values))
                extra = sorted(set(values) - set(canonical))
                problems.append(
                    f"{filename} 的 {name} 不是两轴八类的排列 —— 它是**穷举**用途，"
                    f"漏一类就会让那类关系拿不到类别、下游判据静默跳过。\n"
                    f"      缺 {missing or '无'}，多 {extra or '无'}")

    # ② 写死的 kind 集合：不禁止，但要能看见（防止又长出一个半截清单）。
    # 这些提示**攒起来最后打**，不能先打：变异探针取的是输出的第一行，
    # 提示行跑到结论前面，就会让人把「[note] …部分清单（部分即本意）」误读成失败原因。
    notes: list[str] = []
    inline = list(iter_inline_kind_collections())
    checks += len(inline)
    for path, lineno, hits in inline:
        if len(set(hits)) == len(CANONICAL_KINDS):
            continue
        notes.append(f"  [note] {path.relative_to(ROOT)}:{lineno} 写死的 kind 集合为部分清单 "
                     f"{sorted(set(hits))} —— 若它的用途是「挑类别/分派判据」，请登记进 "
                     "EXHAUSTIVE_LISTS；若只是过滤器（部分即本意），忽略本条。")

    # ③ 旧计数词不许回来。
    for doc in iter_docs():
        text = doc.read_text(encoding="utf-8")
        for phrase, reason in DEAD_PHRASES.items():
            checks += 1
            if phrase in text:
                line = next((i for i, l in enumerate(text.splitlines(), 1) if phrase in l), 0)
                problems.append(f"{doc.relative_to(ROOT)}:{line} 出现废弃说法「{phrase}」"
                                f"（{reason}）")

    # ④ 文档里的示例也是一份契约：扣出来的关系对象要能过校验器认的字段与类别。
    # 这里修的是本轮最贵的一处 —— 示例写了嵌套 relations + constant，喂给校验器**判 pass**，
    # 于是照它写计划的 Agent 会以为已经声明了内边距，而产物里什么都没有。
    sample_count = 0
    unparsed = []
    for doc, block_index, relation, status in iter_doc_relation_objects():
        if status == "unparsed":
            unparsed.append(f"{doc.relative_to(ROOT)} 第 {block_index} 个 json 块（伪代码/片段，跳过）")
            continue
        sample_count += 1
        checks += 1
        where = f"{doc.relative_to(ROOT)} 第 {block_index} 个 json 块的关系 {relation.get('id') or '(无 id)'}"
        for key, reason in RELATION_FORBIDDEN_KEYS.items():
            if key in relation:
                problems.append(f"{where} 含字段 `{key}`：{reason}")
        kind = relation.get("kind")
        if kind is not None and kind not in CANONICAL_KINDS:
            problems.append(f"{where} 的 kind={kind!r} 不在两轴八类里")

    if problems:
        print("类别表漂移：")
        for problem in problems:
            print(f"  - {problem}")
        for note in notes:
            print(note)
        return 1

    print(f"类别表守卫通过：两轴八类锁定，{len(EXHAUSTIVE_LISTS)} 个穷举清单均为排列，"
          f"文档示例 {sample_count} 条关系合规，{len(list(iter_docs()))} 个文件无废弃计数词"
          f"（{checks} 项检查）")
    for note in notes:
        print(note)
    for line in unparsed:
        print(f"  [note] 未校验：{line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
