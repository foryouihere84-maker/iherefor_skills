#!/usr/bin/env python3
"""把 lanhu_get_design_document 的返回体解析成实现计划可直接引用的设计事实摘要。

背景：`lanhu_get_design_document` 是全量图层树 JSON（一个典型稿 105KB、94 节点），
**全量喂给 Agent 不划算**，但里面藏着写实现计划最贵的几类事实——父视图归属、字号、
字体、文本、颜色、描边、填充。在此之前这些全是 Agent 从渲染 DOM 反向推断出来的
（实现计划里每个 region 都是 ``kindSource: "agent-decided"``），推断即成本，判错即一轮门 2。

本脚本只做**解析与降噪**，产出紧凑 ``design-facts.json``，供第 3 步「目标实现计划」引用：

- ``hierarchy``：每个图层的真实父视图归属（``metadata.parentId`` / ``metadata.depth``），
  这是 ``layoutProportions.regions[].parentIndex`` 的权威来源——「父是谁」由查表得到，
  不再由 Agent 猜。
- ``typography``：字号 / 字体族 / 字重 / 文本 / 颜色，直接填 ``unsupported[typography]``
  归因与字号常量，不必靠 CDP ``getPlatformFontsForNode`` 或 ``advanceWidth`` 反推。
- ``borders`` / ``fills`` / ``shadows``：描边/填充/阴影的粗细与颜色，回答「描边是画在
  frame 上还是独立装饰层」——正是覆盖式装饰子视图吞点击、CSS border 内缩两个坑的判据。

**关键结构事实（踩过坑，勿再猜字段名）**：`layers[]` 是嵌套树（子层在 ``children``）；
``type`` 对文本/形状/组**全是 ``artboard``**，不能靠它切组件；文本在 ``style.typography``
（不在 ``style.text``）；``parentId``/``depth`` 在 ``metadata``（不在顶层）。

只读脚本：不改 MCP、不下载、不打印凭据。位置与坐标仍以浏览器事实表为准——这份摘要
回答「设计稿说应该什么样」，渲染事实回答「实际成了什么样」，两者互补而非替代。
"""
import argparse
import json
import sys
from collections import Counter


def _flatten(nodes, out):
    """按前序遍历展开 ``layers[]`` 嵌套树（子层在 ``children``）。"""
    for node in nodes or []:
        out.append(node)
        _flatten(node.get("children") or [], out)


def _color_text(color):
    """把 ``{r,g,b,a,value}`` 归一化成 ``value`` 字符串；缺省返回 None。"""
    if not isinstance(color, dict):
        return None
    value = color.get("value")
    if isinstance(value, str):
        return value
    rgba = color.get("r"), color.get("g"), color.get("b")
    if all(isinstance(v, (int, float)) for v in rgba):
        a = color.get("a", 1)
        r, g, b = (int(round(float(v))) for v in rgba)
        if isinstance(a, (int, float)) and float(a) < 1:
            return "rgba(%d,%d,%d,%.3g)" % (r, g, b, float(a))
        return "rgba(%d,%d,%d,1)" % (r, g, b)
    return None


def _num(v):
    return v if isinstance(v, (int, float)) else None


def build_facts(document):
    """从 design_document 返回体产出紧凑事实摘要 dict。"""
    layers = []
    _flatten(document.get("layers") or [], layers)

    by_id = {}
    roots = []
    for node in layers:
        nid = node.get("id")
        if nid is not None:
            by_id[nid] = node
        # 根层 = metadata.parentId 为 None 且深度为 0 的顶层节点
        meta = node.get("metadata") or {}
        if meta.get("parentId") is None and meta.get("depth") == 0:
            roots.append(node)

    typography = []
    borders = []
    fills = []
    shadows = []
    for node in layers:
        style = node.get("style") or {}
        meta = node.get("metadata") or {}
        common = {
            "id": node.get("id"),
            "name": node.get("name"),
            "rect": node.get("rect"),
            "parentId": meta.get("parentId"),
            "depth": meta.get("depth"),
        }
        if style.get("typography"):
            ty = style["typography"]
            row = dict(common)
            row.update({
                "text": ty.get("text"),
                "fontFamily": ty.get("fontFamily"),
                "fontSize": _num(ty.get("fontSize")),
                "fontWeight": _num(ty.get("fontWeight")),
                "lineHeight": _num(ty.get("lineHeight")),
                "letterSpacing": _num(ty.get("letterSpacing")),
                "textAlign": ty.get("textAlign"),
                "color": _color_text(ty.get("color")),
            })
            typography.append(row)
        if style.get("borders"):
            borders.append({"id": node.get("id"), "name": node.get("name"),
                            "borders": style["borders"]})
        if style.get("fills"):
            fills.append({"id": node.get("id"), "name": node.get("name"),
                          "fills": style["fills"]})
        if style.get("shadows"):
            shadows.append({"id": node.get("id"), "name": node.get("name"),
                            "shadows": style["shadows"]})

    depth_counter = Counter(
        ((n.get("metadata") or {}).get("depth") for n in layers if (n.get("metadata") or {}).get("depth") is not None)
    )
    visible_false = sum(
        1 for n in layers if (n.get("style") or {}).get("visible") is False
    )
    export_image = sum(
        1 for n in layers if (n.get("metadata") or {}).get("hasExportImage")
    )

    return {
        "source": {
            "name": document.get("name"),
            "imageId": document.get("imageId"),
            "projectId": document.get("projectId"),
            "canvas": document.get("canvas"),
        },
        "summary": {
            "layerCount": len(layers),
            "rootCount": len(roots),
            "typographyCount": len(typography),
            "borderCount": len(borders),
            "fillCount": len(fills),
            "shadowCount": len(shadows),
            "visibleFalseCount": visible_false,
            "exportImageCount": export_image,
            "depthDistribution": dict(sorted(depth_counter.items())),
        },
        "roots": [{"id": n.get("id"), "name": n.get("name")} for n in roots],
        "hierarchy": [
            {
                "id": n.get("id"),
                "name": n.get("name"),
                "parentId": (n.get("metadata") or {}).get("parentId"),
                "depth": (n.get("metadata") or {}).get("depth"),
            }
            for n in layers
        ],
        "typography": typography,
        "borders": borders,
        "fills": fills,
        "shadows": shadows,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="把 lanhu_get_design_document 解析成紧凑设计事实摘要")
    ap.add_argument("--document", required=True,
                    help="lanhu_get_design_document 返回体 JSON 文件路径")
    ap.add_argument("--output", help="JSON 摘要输出路径；缺省打印到 stdout（人类可读摘要）")
    args = ap.parse_args(argv)

    with open(args.document, encoding="utf-8") as fh:
        document = json.load(fh)

    facts = build_facts(document)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(facts, fh, ensure_ascii=False, indent=2)
        print("design-facts.json written to %s" % args.output)
        return 0

    # 人类可读摘要（stdout 默认不是 JSON，解析 stdout 会 ValueError —— 与
    # check_layout_proportions.py 的约定一致：JSON 必须走 --output）
    s = facts["summary"]
    print("设计稿: %s (%s)" % (facts["source"]["name"], facts["source"]["imageId"]))
    print("画布: %s" % facts["source"]["canvas"])
    print("图层 %d 个 | 根层 %d | 文本 %d | 描边 %d | 填充 %d | 阴影 %d"
          % (s["layerCount"], s["rootCount"], s["typographyCount"],
             s["borderCount"], s["fillCount"], s["shadowCount"]))
    print("不可见层 %d | 含导出图 %d" % (s["visibleFalseCount"], s["exportImageCount"]))
    print("层级分布: %s" % s["depthDistribution"])
    print("文本层:")
    for row in facts["typography"]:
        print('  "%s" -> %s(%spt) %s' % (
            row["text"], row["fontFamily"], row["fontSize"], row["color"]))
    print("描边层:")
    for row in facts["borders"]:
        widths = [b.get("width") for b in row["borders"]]
        print("  %s: %s" % (row["name"], widths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
