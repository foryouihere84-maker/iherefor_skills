#!/usr/bin/env python3
"""把 lanhu_get_design_document 的返回体解析成实现计划可直接引用的设计事实摘要。

背景：`lanhu_get_design_document` 是全量图层树 JSON（一个典型稿 105KB、94 节点），
**全量喂给 Agent 不划算**，但里面藏着写实现计划最贵的几类事实——父视图归属、字号、
字体、文本、颜色、描边、填充。在此之前这些全是 Agent 从渲染 DOM 反向推断出来的
（实现计划里每个 region 都是 ``kindSource: "agent-decided"``），推断即成本，判错即一轮门 2。

本脚本只做**解析与降噪**，产出紧凑 ``design-facts.json``，供第 3 步「目标实现计划」引用：

- ``hierarchy``：每个图层的真实父视图归属。**由 ``children`` 嵌套推导（``metadata.parentId``
  实测全为 null，不可靠）**。这是 ``layoutProportions.regions[].parentIndex`` 的权威来源。
- ``typography``：字号 / 字体族 / 字重 / 文本 / 颜色。**字号已按 ``canvas.scale`` 还原**，
  因为 document 把字号除了 scale（实测 scale=2 稿里所有 fontSize=7，但下载 HTML 里真实
  字号是 14）。字体族名做过 normalize（``AvenirLT-*`` → ``Avenir-*``，带 LT 后缀的族名
  系统里不存在）。
- ``borders`` / ``fills`` / ``shadows``：描边/填充/阴影的粗细与颜色，回答「描边是画在
  frame 上还是独立装饰层」——正是覆盖式装饰子视图吞点击、CSS border 内缩两个坑的判据。

**关键结构事实（踩过坑，勿再猜字段名）**：`layers[]` 是嵌套树（子层在 ``children``）；
``type`` 对文本/形状/组**全是 ``artboard``**，不能靠它切组件；文本在 ``style.typography``
（不在 ``style.text``）；``depth`` 在 ``metadata``，但 ``metadata.parentId`` **不可靠**
（实测全 null），父视图归属要按 ``children`` 树推导。

**坐标与字号的 scale 语义不一致（务必注意）**：``rect`` 坐标是**未缩放**的画布点坐标
（实测最大 393×852 = 画布尺寸）；但 ``typography.fontSize`` 是**除过 ``canvas.scale`` 的**。
本脚本只还原 fontSize（坐标为真、字号待还原），并在输出里保留 ``canvas.scale`` 与
``fontSizeRaw``，让下游能追溯。

只读脚本：不改 MCP、不下载、不打印凭据。位置与坐标仍以浏览器事实表为准——这份摘要
回答「设计稿说应该什么样」，渲染事实回答「实际成了什么样」，两者互补而非替代。
"""
import argparse
import json
import sys
from collections import Counter

# 带 LT 后缀的字体族名系统里不存在（AvenirLT-Medium/Black），Chromium 会回落。
# 基准渲染与原生侧都以去 LT 后的族名为准。
_FONT_NORMALIZE = {
    "AvenirLT-Medium": "Avenir-Medium",
    "AvenirLT-Black": "Avenir-Black",
    "AvenirLT-Heavy": "Avenir-Heavy",
}


def _walk(nodes, out):
    """按前序遍历展开 ``layers[]`` 嵌套树（子层在 ``children``）。"""
    for node in nodes or []:
        out.append(node)
        _walk(node.get("children") or [], out)


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


def _derive_parent_ids(nodes):
    """按 ``children`` 嵌套推导每个节点的父 id（``metadata.parentId`` 不可靠）。

    返回 dict：node_id -> parent_id（根层为 None）。图真树里父就是唯一包含它的祖先；
    无论 metadata.parentId 是否为空，都以 children 树为准。
    """
    parent = {}

    def assign(parent_id, kid_nodes):
        for kid in kid_nodes or []:
            kid_id = kid.get("id")
            if kid_id is not None:
                parent[kid_id] = parent_id
            assign(kid_id, kid.get("children"))

    assign(None, nodes)
    return parent


def build_facts(document):
    """从 design_document 返回体产出紧凑事实摘要 dict。"""
    layers = []
    _walk(document.get("layers") or [], layers)

    canvas = document.get("canvas") or {}
    scale = canvas.get("scale")
    scale = float(scale) if isinstance(scale, (int, float)) and scale > 0 else None

    # 父视图归属：按 children 树推导（metadata.parentId 实测全 null，不可靠）
    parent_of = _derive_parent_ids(document.get("layers") or [])

    # 根层判定仍用 metadata.depth == 0（depth 实测可靠），parentId 只作兜底参考
    roots = []
    for node in layers:
        meta = node.get("metadata") or {}
        if meta.get("depth") == 0:
            roots.append(node)

    typography = []
    borders = []
    fills = []
    shadows = []
    for node in layers:
        style = node.get("style") or {}
        meta = node.get("metadata") or {}
        nid = node.get("id")
        common = {
            "id": nid,
            "name": node.get("name"),
            "rect": node.get("rect"),
            "parentId": parent_of.get(nid),
            "depth": meta.get("depth"),
        }
        if style.get("typography"):
            ty = style["typography"]
            font_family = ty.get("fontFamily")
            normalized = _FONT_NORMALIZE.get(font_family, font_family)
            raw_size = _num(ty.get("fontSize"))
            row = dict(common)
            row.update({
                "text": ty.get("text"),
                "fontFamily": normalized,
                "fontFamilyRaw": font_family,
                "fontWeight": _num(ty.get("fontWeight")),
                "lineHeight": _num(ty.get("lineHeight")),
                "letterSpacing": _num(ty.get("letterSpacing")),
                "textAlign": ty.get("textAlign"),
                "color": _color_text(ty.get("color")),
            })
            if raw_size is not None:
                row["fontSize"] = raw_size * scale if scale else raw_size
                row["fontSizeRaw"] = raw_size
            else:
                row["fontSize"] = None
                row["fontSizeRaw"] = None
            typography.append(row)
        if style.get("borders"):
            borders.append({"id": nid, "name": node.get("name"),
                            "borders": style["borders"]})
        if style.get("fills"):
            fills.append({"id": nid, "name": node.get("name"),
                          "fills": style["fills"]})
        if style.get("shadows"):
            shadows.append({"id": nid, "name": node.get("name"),
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
            "canvas": canvas,
        },
        "scale": {
            "canvasScale": scale,
            "fontSizeScaled": bool(scale and scale != 1),
            "note": "rect 坐标未缩放（画布点坐标）；fontSize 已按 canvas.scale 还原，fontSizeRaw 是 document 原文",
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
                "parentId": parent_of.get(n.get("id")),
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
    sc = facts["scale"]
    print("设计稿: %s (%s)" % (facts["source"]["name"], facts["source"]["imageId"]))
    print("画布: %s（尺度还原：%s）" % (facts["source"]["canvas"], sc))
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
