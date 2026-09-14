#!/usr/bin/env python3
"""回归：page-facts 的「文本元素事实」必须归属正确、范围正确。

这里固定住两个真实发生过、而当时**没有任何断言能发现**的缺陷：

1. **字体写到隔壁元素头上。** 文本标记用「未过滤的 DOM 序号」（
   ``querySelectorAll('body *')`` 的下标），事实采集却用「过滤掉不可见元素后的下标」。
   页面里只要有一个不可见节点（事故页是一个 ``<br>``，夹在第 4 个文本元素前面），
   它之后所有文本元素的 ``primaryFont`` 就整体错位一格 —— 实测该页 18 个文本元素里
   错了 15 个，而 ``browser-meta.json`` 一路报「字体已测量」。字体归属错了，字体替换
   这件事就永远查不出来。fixture 用一个夹在中间的 ``<br>`` 固定住这个条件。

2. **祖先容器冒充文本元素。** 旧实现用 ``innerText`` 判断「这个元素有没有文本」，
   而 ``innerText`` 会把后代文本一并算进来，于是每个祖先容器都成了一个「有 291 字符、
   21 段 rect」的伪文本元素；它的 rect 并集只是子元素矩形的凑合，不是任何一次真实排版
   的结果。拿它做对齐预测会得到横跨整屏的框，把「DOM 与基准图是否一致」整个污染掉
   （一次本该 clean 的基准被判成中位偏移 5pt，全部来自这些伪元素）。

断言全部不依赖本机装了哪些字体，因此跨机器稳定：

* 带 ``textMetrics`` 的元素必须**恰好**是「自己直接承载文本」的那些，数量不因容器膨胀；
* 文本元素的 ``textMetrics.rects`` 不得混入后代文本的矩形；
* 每个文本元素各字体 ``glyphCount`` 之和 == 它自己的字符数（归属错位时必然不等）；
* ``browser-meta.fontJoin`` 自检通过（标记下标与采集下标逐个相符）；
* fixture 必须仍然制造出「DOM 节点数 > 可见元素数」的错位条件，否则本用例是空转。
"""
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "scripts" / "tests" / "fixtures"

# fixture 的预期：7 个「自己承载文本」的元素（6 个 span + 1 个既带词又包着子元素的 div）
EXPECTED_TEXT_ELEMENTS = 7


def union(rects):
    left = min(r["x"] for r in rects)
    top = min(r["y"] for r in rects)
    right = max(r["x"] + r["width"] for r in rects)
    bottom = max(r["y"] + r["height"] for r in rects)
    return left, top, right, bottom


def main():
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            ["node", str(ROOT / "scripts" / "render_reference.mjs"),
             "--input", str(FIX / "text-elements.html"),
             "--output", tmp,
             "--viewport", "300x420", "--scale", "2"],
            capture_output=True, text=True,
        )
        facts_path = Path(tmp) / "page-facts.json"
        meta_path = Path(tmp) / "browser-meta.json"
        if proc.returncode != 0 or not facts_path.exists() or not meta_path.exists():
            print(f"render_reference.mjs 执行失败：{(proc.stderr or proc.stdout).strip()[:400]}")
            return 1

        facts = json.loads(facts_path.read_text())
        meta = json.loads(meta_path.read_text())

        elements = facts.get("elements") or []
        owning = [e for e in elements if e.get("ownsText")]
        measured = [e for e in elements if e.get("textMetrics")]

        # --- 1. textMetrics 只能出现在「自己承载文本」的元素上 ---
        owning_ids = {id(e) for e in owning}
        leaked = [e for e in measured if id(e) not in owning_ids]
        if leaked:
            problems.append(
                "有 " + str(len(leaked)) + " 个元素没有自有文本却带 textMetrics（容器冒充文本元素）："
                + ", ".join(f"#{e.get('index')} <{e.get('tag')}> {e.get('className')}" for e in leaked[:4])
            )
        missing = [e for e in owning if not e.get("textMetrics")]
        if missing:
            problems.append(
                f"有 {len(missing)} 个自有文本元素缺少 textMetrics："
                + ", ".join(f"#{e.get('index')} {(e.get('ownText') or '')[:16]!r}" for e in missing[:4])
            )
        if len(owning) != EXPECTED_TEXT_ELEMENTS:
            problems.append(
                f"自有文本元素应为 {EXPECTED_TEXT_ELEMENTS} 个，实际 {len(owning)} 个"
                "（数量膨胀说明容器又混进了文本元素集合）"
            )

        # --- 2. 后代文本不得混进本元素的 rects ---
        mixed = next((e for e in owning if (e.get("ownText") or "").strip() == "Label"), None)
        child = next((e for e in owning if (e.get("ownText") or "").strip() == "Wrapped Words Here"), None)
        if mixed is None or child is None:
            problems.append("fixture 结构变了：找不到「既带词又包着子元素」的容器或其子元素")
        else:
            if not mixed["textMetrics"].get("hasDescendantTextElement"):
                problems.append("容器元素未标记 hasDescendantTextElement")
            if len(mixed["textMetrics"]["rects"]) != 1:
                problems.append(
                    f"容器自有文本 'Label' 应只占 1 个 rect，实际 {len(mixed['textMetrics']['rects'])} 个"
                    "（后代文本被算进了本元素）"
                )
            if len(mixed["textMetrics"]["rects"]) == 1:
                _, _, own_right, _ = union(mixed["textMetrics"]["rects"])
                child_left = child["rect"]["x"]
                if own_right > child_left:
                    problems.append(
                        f"容器自有文本右边界 {own_right:.1f}px 越过了子元素起点 {child_left:.1f}px："
                        "rects 混入了后代文本"
                    )

        # --- 3. 字体归属自洽：叶子文本元素的 glyphCount 之和 == 自有字符数 ---
        # 只对**叶子**文本元素成立。CDP 的 glyphCount 是该节点**子树**的字形总数
        # （见 browser-meta.fontMeasurement.glyphCountScope），所以「自己带词又包着
        # 子文本」的元素必须排除，另行验证。
        unattributed = []
        misattributed = []
        mixed_chars = 0
        for e in owning:
            chars = e["textMetrics"]["charCount"]
            fonts = e.get("fontsResolved") or []
            if not fonts:
                unattributed.append(f"#{e.get('index')} {(e.get('ownText') or '')[:16]!r}")
                continue
            glyphs = sum(f.get("glyphCount") or 0 for f in fonts)
            if e["textMetrics"].get("hasDescendantTextElement"):
                mixed_chars = glyphs   # 子树合计，见下方断言
                continue
            if glyphs != chars:
                misattributed.append(
                    f"#{e.get('index')} {(e.get('ownText') or '')[:16]!r}"
                    f" 字符 {chars} / 字形 {glyphs}"
                )
        if unattributed:
            problems.append("以下文本元素没有解析出实际字体（字体链仍是空的）：" + ", ".join(unattributed[:4]))
        if misattributed:
            problems.append(
                "字形数与字符数不符，说明字体被归属到了别的元素：" + "; ".join(misattributed[:4])
            )
        # 混合元素的 glyphCount 是子树合计：'Label'(5) + 空格 + 'Wrapped Words Here'(18) = 24。
        # 这条断言把「glyphCount 是子树口径」这件事钉住 —— 它解释了为什么上面的严格
        # 相等断言必须先排掉混合元素，也防止后人把 primaryFont 误当成「本元素文字的字体」。
        expected_subtree = (len("Label") + 1 + len("Wrapped Words Here")) if mixed else 0
        if mixed and mixed_chars != expected_subtree:
            problems.append(
                f"混合元素的 glyphCount 应为子树合计 {expected_subtree}，实际 {mixed_chars}"
                "（若 CDP 语义变成只算自有文本，请同步修正本用例与 glyphCountScope 说明）"
            )

        # --- 4. 渲染器自查 ---
        font_join = meta.get("fontJoin") or {}
        if not font_join:
            problems.append("browser-meta.json 缺少 fontJoin：无法证明标记下标与采集下标一致")
        else:
            if not font_join.get("ok"):
                problems.append(f"fontJoin.ok 为假：{json.dumps(font_join, ensure_ascii=False)[:200]}")
            if font_join.get("textMarkMismatchCount"):
                problems.append(
                    f"有 {font_join['textMarkMismatchCount']} 个元素的标记下标与采集下标不符："
                    f"{font_join.get('textMarkMismatches')}"
                )

        # --- 5. fixture 仍然在制造错位条件（防止用例空转） ---
        if not font_join:
            pass
        elif font_join.get("indexSpaceSkew", 0) <= 0:
            problems.append(
                "fixture 已不含被过滤掉的节点（indexSpaceSkew<=0），"
                "「DOM 序号 vs 过滤后下标」的错位条件不再存在，本用例已退化为空转："
                "请保留那个夹在文本元素之间的不可见节点"
            )

    for p in problems:
        print(p)
    if problems:
        return 1
    print("文本元素归属与范围正确：无容器冒充、无后代混入、字形数与字符数逐个相符、fontJoin 自查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
