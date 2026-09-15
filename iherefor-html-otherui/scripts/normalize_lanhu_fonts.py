#!/usr/bin/env python3
"""把 Lanhu 导出的 CSS 里「系统不存在的字体族名」替换成真实存在的族名，供基准渲染前执行。

背景：Lanhu 导出的 CSS 常见 ``font-family: AvenirLT-Medium`` / ``AvenirLT-Black``
这种**带 LT 后缀**的裸族名。系统里装的是 ``Avenir-Medium`` / ``Avenir-Black``
（不带 LT），于是 Chromium 找不到该族、又因为没有泛型兜底，回落到默认衬线字体
Times。更糟的是：回落是**静默的**——DOM 与基准图用同一套回落字体，互相对得上，
对齐审计判 ``aligned``，于是「基准图自洽地错」，照着它去对齐 App 只会越改越偏。

实测（「目的」页 image_id=cc79645f）：8 个元素命中 Times-Roman，其中包括主标题
``How can we help you?``（24px, AvenirLT-Black）。把 ``AvenirLT-`` 改成 ``Avenir-``
后重渲染，Times 归零，Avenir Medium(101 glyphs) / Avenir Black(20) / Avenir Heavy(8)
全部正确命中。

本脚本只做**确定性的字面替换**：扫描下载的 ``index.css``（以及 ``common.css``），
把表里的「坏族名 → 好族名」逐条替换。它**不猜**——只处理表里明确列出的映射；
表里没有的族名原样保留，交给后续 ``audit_fonts.py`` 审计去发现。

为什么是脚本而不是让 Agent 手工 sed：规则是确定的，且这一步在「下载 → 渲染」之间，
漏了它基准图就带着错误字体渲染，后续所有 diff 都在跟错误基准比。脚本化保证不漏。

只改 CSS 文本、不下载、不打印凭据。替换后应重跑 ``render_reference.mjs`` 重新渲染、
重新测量（这一步由固定调用链强制，不在本脚本职责内）。
"""
import argparse
import re
import sys
from pathlib import Path

# 已知的「系统不存在的族名 → 系统里真实存在的族名」。
# 只放**确定**的映射；不确定的不放（留给 audit_fonts.py 去发现）。
# 键用 CSS 里实际出现的字符串（可能带引号），值是不带引号的真实族名。
FONT_NAME_REPLACEMENTS = {
    "AvenirLT-Black": "Avenir-Black",
    "AvenirLT-Medium": "Avenir-Medium",
    "AvenirLT-Heavy": "Avenir-Heavy",
    "AvenirLT-Book": "Avenir-Book",
    "AvenirLT-Roman": "Avenir-Roman",
    "AvenirLT-Light": "Avenir-Light",
    "AvenirLT-Oblique": "Avenir-Oblique",
}


def normalize(css_text):
    """把 CSS 文本里所有已知坏族名替换成好族名，返回 (新文本, 替换记录)。"""
    replacements = []
    for bad, good in FONT_NAME_REPLACEMENTS.items():
        # 只做字面替换；`bad` 里不含正则元字符，但稳妥起见用 re.escape 并计数。
        pattern = re.compile(re.escape(bad))
        new_text, n = pattern.subn(good, css_text)
        if n:
            replacements.append({"from": bad, "to": good, "count": n})
            css_text = new_text
    return css_text, replacements


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="把 Lanhu 导出 CSS 里系统不存在的字体族名替换成真实族名（基准渲染前执行）")
    ap.add_argument("--source", required=True,
                    help="下载的设计源码目录（含 index.css / common.css）")
    ap.add_argument("--css", action="append", default=None,
                    help="额外要处理的 CSS 文件路径（可重复）；缺省处理 index.css 与 common.css")
    ap.add_argument("--output", help="JSON 替换报告输出路径；缺省打印到 stdout（人类可读）")
    args = ap.parse_args(argv)

    src = Path(args.source)
    css_files = [src / "index.css", src / "common.css"]
    if args.css:
        css_files += [Path(p) for p in args.css]

    total = []
    for css_file in css_files:
        if not css_file.exists():
            continue
        text = css_file.read_text(encoding="utf-8")
        new_text, repl = normalize(text)
        if repl:
            css_file.write_text(new_text, encoding="utf-8")
            total.append({"file": str(css_file), "replacements": repl})

    if args.output:
        import json
        report = {"processedFiles": [t["file"] for t in total],
                  "replacements": total,
                  "replacementCount": sum(r["count"] for t in total for r in t["replacements"])}
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
        print("font normalize report written to %s" % args.output)
        return 0

    if not total:
        print("未发现需要替换的字体族名（无需处理）")
        return 0

    print("已替换字体族名：")
    for t in total:
        print("  %s:" % t["file"])
        for r in t["replacements"]:
            print("    %s -> %s （%d 处）" % (r["from"], r["to"], r["count"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
