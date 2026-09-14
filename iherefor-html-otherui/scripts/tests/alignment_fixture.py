#!/usr/bin/env python3
"""合成「已知真值」的对齐夹具：给 test_audit_alignment.py 造 ground truth。

为什么需要它。真实事故数据只能证明「审计说出了正确的话」，不能证明「审计的数学是对的」——
真实数据里没有 ground truth，谁也不知道真实的 dy 到底是多少。所以要另造一批**参数已知**
的图：先画一张基准图，再按已知的 ``(slope, intercept)`` 变形出实测图，然后要求审计把这两个
参数还原回来。还原不回来，说明匹配或拟合有 bug，而不是数据有问题。

坐标约定（与 audit_alignment.py 一致）：

* ``slope`` 是无量纲的 ``s - 1``：实测像素 y' = s * 基准像素 y。
  于是 ``dy_pt = (y' - y) / unit_scale = y_pt * (s - 1)``，正好是斜率。
* ``intercept`` 单位是设备点（pt），即平移量。
* 变形一律以像素为单位、绕 y=0 缩放再平移，这样真值可以直接写成
  ``y' = (1 + slope) * y + intercept * unit_scale``。
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

# 合成画布：够小以保证测试快，够复杂以保证模板唯一。
CANVAS_WIDTH = 200
CANVAS_HEIGHT = 400
SCREENSHOT_SCALE = 2

# 元素在 CSS px（= lanhu px，本夹具里 policy=fit 且比例 1.0）下的 rect。
# y 值刻意铺满整页，让线性拟合有足够杠杆。
ELEMENTS = [
    ("headline", "Dijital Plan", 16, 24, 168, 26),
    ("badge", "Yeni", 16, 62, 52, 20),
    ("card-weekly", "Haftalik plan 12.99", 16, 110, 168, 34),
    ("card-monthly", "Aylik plan 39.99", 16, 162, 168, 34),
    ("section-title", "Avantajlar", 16, 216, 120, 22),
    ("bullet-a", "Sinirsiz erisim", 24, 248, 140, 18),
    ("bullet-b", "Oncelikli destek", 24, 274, 140, 18),
    ("bullet-c", "Aile paylasimi", 24, 300, 140, 18),
    ("cta", "Devam Et", 16, 340, 168, 40),
    ("footer", "Kosullari kabul ediyorum", 16, 386, 168, 14),
]

# 每个元素用的笔画种子，让模板互不相同（否则匹配会歧义）。
def _glyph_paths(seed, inset=0.12):
    """生成一组确定性的线段，铺在单位方框内，且**墨迹质心恰好落在 (0.5, 0.5)**。

    为什么必须保证质心居中。真实 ``page-facts.json`` 的 ``textMetrics.rects`` 来自
    ``Range.getClientRects()``，量到的就是字形行盒，墨迹质心与行盒中心重合。夹具若不
    满足这一点，``domVsReference`` 会量到一个纯粹由夹具造成的「基准图与 DOM 不符」，
    测试就变成了在检验夹具的 bug。

    实现上踩过三次，都记下来免得回头重犯：

    1. 只把包围盒归一化 —— 不够。笔画长度随机，质心并不落在包围盒中心。
    2. 给每条线段补点对称镜像 —— 质心确实精确居中了，但图案变成中心对称，自相关出现
       强次峰，模板匹配的可信点从 9 个掉到 1 个，测试没法用。
    3. 在**归一化坐标**里按长度加权求质心再平移 —— 也不够。调用方把单位方框铺到
       272x24 这种 11:1 的框上时映射是各向异性的，一条在归一化空间里很短的线段映射到
       像素空间可能很长，于是「归一化空间的长度加权质心」和「像素空间的墨迹质心」不是
       一回事，实测偏了 19px。

    所以真正的做法在 ``_draw_element``：**在像素空间里**按线段面积（``pen*(L+pen)``，
    含端点圆帽）加权求质心，再以该质心为中心平移并等比缩放。本函数只负责给出原料。
    """
    rng = random.Random(seed * 977 + 13)
    count = 3 + seed % 4
    return [((rng.uniform(0.0, 1.0), rng.uniform(0.0, 1.0)),
             (rng.uniform(0.0, 1.0), rng.uniform(0.0, 1.0))) for _ in range(count)]


CONTENT_INSET = {"x": 2, "y": 3, "w": 4, "h": 6}  # 内容框相对元素框的内缩（CSS px）


def content_rect(left, top, width, height):
    """元素的内容框（CSS px），与 page_facts() 里 textMetrics.rects 保持一致。"""
    return (left + CONTENT_INSET["x"], top + CONTENT_INSET["y"],
            width - CONTENT_INSET["w"], height - CONTENT_INSET["h"])


def _draw_element(draw, left, top, width, height, seed):
    """在元素的内容框里画出确定性笔画，且墨迹质心严格落在内容框中心。

    见 ``_glyph_paths`` 的文档：质心必须在**像素空间**里算，因为单位方框到内容框的
    映射是各向异性的。
    """
    cx, cy, cw, ch = content_rect(left, top, width, height)
    ox, oy = cx * SCREENSHOT_SCALE, cy * SCREENSHOT_SCALE
    sw, sh = cw * SCREENSHOT_SCALE, ch * SCREENSHOT_SCALE
    pen = max(2, int(round(SCREENSHOT_SCALE * 1.5)))

    # 1) 原始线段 → 像素空间（相对内容框左上角）。
    segments = [((x0 * sw, y0 * sh), (x1 * sw, y1 * sh))
                for (x0, y0), (x1, y1) in _glyph_paths(seed)]
    # 2) 按线段面积加权求质心。细线段像素面积 ≈ pen*(L+pen)：乘 pen 是长度项，
    #    再加一个 pen 是圆帽项 —— 短线段上圆帽占比很大，漏掉它就会偏。
    total = mx = my = 0.0
    for (x0, y0), (x1, y1) in segments:
        weight = math.hypot(x1 - x0, y1 - y0) + pen
        total += weight
        mx += weight * (x0 + x1) / 2
        my += weight * (y0 + y1) / 2
    if total <= 0:
        return
    mx, my = mx / total, my / total
    # 3) 平移到质心为原点；之后所有变换都绕原点做，质心就保持在原点。
    centered = [((x0 - mx, y0 - my), (x1 - mx, y1 - my)) for (x0, y0), (x1, y1) in segments]
    pad = pen
    span_x = max(abs(x) for segment in centered for x, _ in segment) or 1.0
    span_y = max(abs(y) for segment in centered for _, y in segment) or 1.0
    scale = min((sw / 2 - pad) / span_x, (sh / 2 - pad) / span_y)
    scale = max(scale, 1e-6)
    # 4) 等比缩放到内容框内（等比 ⇒ 图案不变形，且质心仍在原点 ⇒ 仍居中）。
    for (x0, y0), (x1, y1) in centered:
        draw.line((ox + sw / 2 + x0 * scale, oy + sh / 2 + y0 * scale,
                   ox + sw / 2 + x1 * scale, oy + sh / 2 + y1 * scale),
                  fill=(20, 20, 24), width=pen)


def reference_image():
    """画基准图（reference.png 的合成替身）。"""
    width = CANVAS_WIDTH * SCREENSHOT_SCALE
    height = CANVAS_HEIGHT * SCREENSHOT_SCALE
    image = Image.new("RGB", (width, height), (246, 246, 248))
    draw = ImageDraw.Draw(image)
    for index, (_, _, left, top, w, h) in enumerate(ELEMENTS):
        _draw_element(draw, left, top, w, h, index)
    return image


def page_facts():
    """合成 page-facts.json，结构与 render_reference.mjs 输出一致。"""
    elements = []
    for index, (name, text, left, top, w, h) in enumerate(ELEMENTS):
        cx, cy, cw, ch = content_rect(left, top, w, h)
        elements.append({
            "index": index,
            "tag": "div",
            "className": name,
            "text": text,
            "rectInReference": {
                "x": left * SCREENSHOT_SCALE, "y": top * SCREENSHOT_SCALE,
                "width": w * SCREENSHOT_SCALE, "height": h * SCREENSHOT_SCALE,
            },
            # textMetrics 以 CSS px 记录（与真实产出对齐），比 rect 略收一点，
            # 模拟「有内容的实际排版区域比元素框小」。
            "textMetrics": {
                "charCount": len(text),
                "lineCount": 1,
                "advanceWidth": float(cw),
                "totalInlineWidth": float(cw),
                "rects": [{"x": cx, "y": cy, "width": cw, "height": ch}],
            },
            "style": {"fontSize": f"{max(10, h // 2)}px", "fontFamily": "Synthetic Sans"},
        })
    return {
        "schemaVersion": 2,
        "url": "file:///synthetic/index.html",
        "viewport": {
            "width": CANVAS_WIDTH, "height": CANVAS_HEIGHT,
            "devicePixelRatio": SCREENSHOT_SCALE,
        },
        "image": {"width": CANVAS_WIDTH * SCREENSHOT_SCALE,
                  "height": CANVAS_HEIGHT * SCREENSHOT_SCALE},
        "elements": elements,
        "referenceImage": {"fullyOpaque": False, "opaqueRatio": 1.0,
                           "bounds": {"x": 0, "y": 0,
                                      "width": CANVAS_WIDTH * SCREENSHOT_SCALE,
                                      "height": CANVAS_HEIGHT * SCREENSHOT_SCALE}},
    }


def warp(reference, slope=0.0, intercept_pt=0.0, unit_scale=SCREENSHOT_SCALE,
         shift_x_pt=0.0):
    """按 ``y' = (1+slope)*y + intercept_pt*unit_scale`` 变形出「实测图」。

    ``shift_x_pt`` 可额外制造**纯横向**平移（x' = x + shift_x_pt*unit_scale）。
    默认 0，即横向不动 —— 多数用例只检验纵向，横向留作未被污染的对照。需要单独
    检验横向错位（例如「超容差的到底是哪个方向」这类结论文案）时才打开它。
    注意搜索半径默认 12pt，横向平移要留在这个范围内才配得上。
    """
    width, height = reference.size
    scale = 1.0 + slope
    shift_px = intercept_pt * unit_scale
    shift_x_px = shift_x_pt * unit_scale
    out = reference.crop((0, 0, width, height))
    # 用仿射变换精确实现缩放 + 平移（PIL 的 a/b/c/d/e/f 是**逆**变换系数：
    # 目标像素 (x, y) 取自源像素 (a*x + b*y + c, d*x + e*y + f)）。
    out = out.transform(
        (width, height), Image.AFFINE,
        (1.0, 0.0, -shift_x_px, 0.0, 1.0 / scale, -shift_px / scale),
        resample=Image.BILINEAR, fillcolor=(246, 246, 248),
    )
    return out.convert("RGB")


def transform_json(scale_x=1.0, scale_y=1.0):
    """构造 canvasTransform：合成夹具里 lanhu 画布即设备尺寸，比例可指定。"""
    return {
        "canvasTransform": {
            "referenceCanvas": {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT},
            "targetWindow": {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT},
            "policy": "fit",
            "scaleX": scale_x, "scaleY": scale_y,
            "origin": {"x": 0.0, "y": 0.0},
            "letterbox": {"x": 0.0, "y": 0.0},
            "screenshotScale": SCREENSHOT_SCALE,
            "reason": "合成夹具：画布与设备同尺寸",
        }
    }


def runtime_device():
    return {
        "platform": "Synthetic",
        "device": "fixture",
        "screenBoundsPoints": {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT},
        "rootViewBoundsPoints": {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT},
        "scaleX": 1.0, "scaleY": 1.0,
        "screenshotPixels": {"width": CANVAS_WIDTH * SCREENSHOT_SCALE,
                             "height": CANVAS_HEIGHT * SCREENSHOT_SCALE},
        "screenshotScale": SCREENSHOT_SCALE,
    }


def write_case(directory: Path, slope=0.0, intercept_pt=0.0, shift_x_pt=0.0):
    """落盘一个 case：reference.png / actual.png / page-facts.json / canvas-transform.json。"""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    reference = reference_image()
    reference.save(directory / "reference.png")
    warp(reference, slope=slope, intercept_pt=intercept_pt,
         shift_x_pt=shift_x_pt).save(directory / "actual.png")
    (directory / "page-facts.json").write_text(
        json.dumps(page_facts(), ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / "canvas-transform.json").write_text(
        json.dumps(transform_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    return directory


if __name__ == "__main__":
    import sys
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/alignment-fixture")
    for name, slope, intercept in (("aligned", 0.0, 0.0),
                                   ("const-shift", 0.0, 5.0),
                                   ("scale-1p003", 0.003, 0.0),
                                   ("scale-and-shift", 0.0025, 4.0)):
        write_case(target / name, slope=slope, intercept_pt=intercept)
        print(f"wrote {target / name}  slope={slope} intercept={intercept}pt")
