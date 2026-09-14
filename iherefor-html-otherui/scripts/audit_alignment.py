#!/usr/bin/env python3
"""元素级对齐审计：DOM 事实、基准图、实测截图三者到底谁和谁不符。

**为什么需要这个脚本。** 契约要求基准图与设备截图「同源」，但校验手段只有
「PNG 像素尺寸相等」。尺寸相等 ≠ 内容对齐：一次事故里两张图都是 1206x2622，
检查全绿，内容却整体差 6–21pt 且随 y 递增（典型坐标系/比例不一致）。当时没有任何
机制能说出「参考图与 DOM 不符」，只能手写 numpy 反推，几轮就耗光了预算。

更关键的是：**「基准图与 DOM 不符」和「App 与基准图不符」是两个不同的故障**，
需要相反的动作。只看整页 diff 数值无法区分，而这正是当时卡住的地方。本脚本把两种
比较分别做出来，并给出「该信哪个」的结论：

    A. domVsReference  DOM 事实表 vs 基准图内容
       —— 不符 ⇒ 基准本身不可信（渲染 viewport/scale 与事实表采集时不一致），
          先重修基准，**不要**照着基准图调 App 代码。
    B. referenceVsActual  基准图 vs 目标 App 实测截图
       —— 不符 ⇒ 基准可信，问题在 App 实现侧，按区域改代码。

用法：

    python3 scripts/audit_alignment.py \\
        --reference pages/<page>/reference/reference.png \\
        --actual    pages/<page>/runs/<run>/actual/app.png \\
        --page-facts pages/<page>/reference/page-facts.json \\
        --runtime-device pages/<page>/runs/<run>/runtime-device.json \\
        --output    pages/<page>/runs/<run>/diff/alignment.json

退出码：0 = 两者都在容差内；1 = 存在超容差偏移；2 = 证据不足，无法判定。

坐标换算一律走 ``canvas_map``；本脚本不自己写任何 ``* scale`` —— 手写换算正是
事故里那次「多乘一层 scaleY」的来源。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from canvas_map import (  # noqa: E402
    CanvasMapError, box_from, box_from_ltrb, transform_from_canvas_transform,
    transform_from_runtime_device,
)

try:
    from PIL import Image, ImageChops, ImageFilter, ImageStat
except ImportError:  # pragma: no cover
    sys.exit("需要 Pillow：pip install -r requirements.txt")

DEFAULT_RADIUS_PT = 12.0        # 元素级模板搜索半径（设备点）
DEFAULT_BAND_RADIUS_PT = 28.0   # 带级搜索半径：比元素级大，才能覆盖整页累积漂移
DEFAULT_POSITION_TOLERANCE_PT = 2.0
DEFAULT_SCALE_TOLERANCE = 0.002
DEFAULT_R2_MIN = 0.5            # 拟合低于此值不据以断定「比例不一致」
DEFAULT_T_MIN = 3.0             # 斜率 t 统计量下限（信噪比；见 linear_fit 的注释）
DEFAULT_PEAK_RATIO = 1.25       # 最优峰/次优峰最小比值，低于此判为匹配歧义
DEFAULT_INK_THRESHOLD = 24      # 边缘强度认定墨迹的下限（0-255）
DEFAULT_INK_OWN_MIN = 0.5       # 框内墨迹占搜索窗墨迹的最低比例
DEFAULT_INK_COVERAGE_MIN = 0.01 # 预测框内墨迹覆盖度下限
DEFAULT_INK_MISSING_RATIO = 0.3 # 少内容元素占比达到此值即判基准不可信
DEFAULT_DOM_TOLERANCE_PT = 4.0  # 基准图墨迹 vs DOM 预测框的容许偏移（含字形固有偏置）
MIN_REGION_PX = 24              # 参与匹配的最小边长（图像像素）
COARSE = 4                      # 粗搜索降采样倍率

STATUS_ORDER = {"aligned": 0, "unmeasurable": 1, "needs-review": 2}


# --------------------------------------------------------------------------
# 图像与数学工具
# --------------------------------------------------------------------------

def edge_map(image):
    """边缘强度图。

    用边缘而不是原始灰度做匹配：抗锯齿、字体栅格化、轻微色偏都会污染灰度匹配，
    但不会移动边缘的位置。这与 ``compare_reference.py`` 的 structural/texture 拆分
    依据同一套事实（差异像素是否落在边缘带上）。
    """
    return image.convert('L').filter(ImageFilter.FIND_EDGES)


def mean_abs_diff(a, b):
    if a.size != b.size:
        raise ValueError(f"尺寸不一致：{a.size} vs {b.size}")
    return ImageStat.Stat(ImageChops.difference(a, b)).sum[0] / (a.size[0] * a.size[1])


def pixels_of(image):
    """取像素序列。

    Pillow 14 起废弃 ``Image.getdata()``，改叫 ``get_flattened_data()``；这里兼顾两者，
    免得跟着 Pillow 版本走。
    """
    getter = getattr(image, "get_flattened_data", None) or image.getdata
    return getter()


class Matcher:
    """边缘图上的模板匹配：降采样粗搜 + 全分辨率细化到 1px。

    同时给出 ``peakRatio``（最优峰与足够远的次优峰之比）。小文本模板在整页里常有
    多个同样像的位置；没有这一项，「匹配歧义」会被伪装成「几何偏移」进入拟合。
    """

    def __init__(self, reference_edge, actual_edge, coarse=COARSE):
        self.ref = reference_edge
        self.act = actual_edge
        self.coarse = coarse
        self.ref_c = reference_edge.resize(
            (max(1, reference_edge.size[0] // coarse), max(1, reference_edge.size[1] // coarse)),
            Image.BOX)
        self.act_c = actual_edge.resize(
            (max(1, actual_edge.size[0] // coarse), max(1, actual_edge.size[1] // coarse)),
            Image.BOX)

    @staticmethod
    def _search(tpl, window):
        tw, th = tpl.size
        scored = []
        for dy in range(0, window.size[1] - th + 1):
            for dx in range(0, window.size[0] - tw + 1):
                scored.append((mean_abs_diff(tpl, window.crop((dx, dy, dx + tw, dy + th))), dx, dy))
        scored.sort(key=lambda item: item[0])
        return scored

    @staticmethod
    def _peak_ratio(scored, separation):
        if not scored:
            return None
        best = scored[0]
        for score, dx, dy in scored[1:]:
            if max(abs(dx - best[1]), abs(dy - best[2])) >= separation:
                return score / best[0] if best[0] > 0 else float('inf')
        return float('inf')

    def _shift_score(self, template, base, full, fx, fy):
        """模板平移到 ``base + (fx, fy)`` 后的匹配代价；越界返回 ``None``。"""
        candidate = (base[0] + fx, base[1] + fy, base[2] + fx, base[3] + fy)
        if candidate[0] < 0 or candidate[1] < 0 or candidate[2] > full[0] or candidate[3] > full[1]:
            return None
        return mean_abs_diff(template, self.act.crop(candidate))

    def _refine(self, template, base, full, fx, fy, center):
        """抛物线插值把位移细化到亚像素。

        整数像素位移会把 dy 量化成 0.5pt（unit_scale=2 时），而全页比例差在窄画布上
        总共才有 1pt 量级——量化噪声可以把真实斜率淹没或放大两倍。代价面在极小值附近
        近似抛物线，用左右/上下三点就能把顶点位置还原到亚像素。
        """
        out_x, out_y = float(fx), float(fy)
        left = self._shift_score(template, base, full, fx - 1, fy)
        right = self._shift_score(template, base, full, fx + 1, fy)
        if left is not None and right is not None:
            denom = left - 2 * center + right
            if denom > 1e-9:
                delta = 0.5 * (left - right) / denom
                if abs(delta) <= 1.0:
                    out_x = fx + delta
        up = self._shift_score(template, base, full, fx, fy - 1)
        down = self._shift_score(template, base, full, fx, fy + 1)
        if up is not None and down is not None:
            denom = up - 2 * center + down
            if denom > 1e-9:
                delta = 0.5 * (up - down) / denom
                if abs(delta) <= 1.0:
                    out_y = fy + delta
        return out_x, out_y

    def match(self, box, radius_px, min_overlap=0.6):
        """在目标图里找回 ``box``（以参考图为坐标系的模板框）。

        返回 ``(dx, dy, score, overlap, peak_ratio)``；目标位置 = box + (dx, dy)。
        ``dx``/``dy`` 是**亚像素**浮点位移。``None`` 表示模板超出图像或可见比例过低
        （元素可能整体不在目标图里）。
        """
        k = self.coarse
        radius_c = max(1, math.ceil(radius_px / k))
        l, t = int(box.x) // k, int(box.y) // k
        r, b = max(int(box.right) // k, l + 1), max(int(box.bottom) // k, t + 1)
        w, h = self.act_c.size
        wl, wt = max(0, l - radius_c), max(0, t - radius_c)
        wr, wb = min(w, r + radius_c), min(h, b + radius_c)
        if wr - wl < r - l or wb - wt < b - t:
            return None
        scored = self._search(self.ref_c.crop((l, t, r, b)), self.act_c.crop((wl, wt, wr, wb)))
        if not scored:
            return None
        coarse_score, dx, dy = scored[0]
        peak_ratio = self._peak_ratio(scored, separation=2)
        bx, by = int((wl + dx - l) * k), int((wt + dy - t) * k)

        base = (int(box.x), int(box.y), int(box.right), int(box.bottom))
        template = self.ref.crop(base)
        full = self.act.size
        best = (coarse_score, bx, by)
        for fy in range(by - k, by + k + 1):
            for fx in range(bx - k, bx + k + 1):
                value = self._shift_score(template, base, full, fx, fy)
                if value is not None and value < best[0]:
                    best = (value, fx, fy)

        _, fx, fy = best
        dx_f, dy_f = self._refine(template, base, full, fx, fy, best[0])
        tx, ty = int(round(dx_f)), int(round(dy_f))
        visible_w = max(0, min(base[2] + tx, full[0]) - max(base[0] + tx, 0))
        visible_h = max(0, min(base[3] + ty, full[1]) - max(base[1] + ty, 0))
        overlap = (visible_w * visible_h) / max(1, (base[2] - base[0]) * (base[3] - base[1]))
        if overlap < min_overlap:
            return None
        return dx_f, dy_f, best[0], overlap, peak_ratio


def linear_fit(points):
    """最小二乘 ``y = slope*x + intercept``，附 R²、残差 RMS 与斜率的 t 统计量。

    为什么要多给一个 ``t``：只看 ``R²`` 判「斜率是否真实」在窄画布上会翻车。位移在
    整数像素上量化、点数又少时，``R²`` 会被量化噪声压到 0.5 以下，于是一个真实存在的
    0.3% 比例差会被判成「没有缩放」。``R²`` 同时依赖 y 的跨度，换了画布高度结论就变，
    不适合当阈值。``t = slope / se(slope)`` 是信噪比，量纲无关、不受 y 跨度影响：
    斜率相对自己的标准误足够大才算数。
    """
    n = len(points)
    if n < 2:
        return None
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    if sxx == 0:
        return None
    sxy = sum((p[0] - mx) * (p[1] - my) for p in points)
    slope = sxy / sxx
    intercept = my - slope * mx
    ss_res = sum((p[1] - (slope * p[0] + intercept)) ** 2 for p in points)
    ss_tot = sum((p[1] - my) ** 2 for p in points)
    # 残差标准误 → 斜率标准误。n == 2 时自由度 0，se 不可估，置 0 让调用方回退到
    # 「只有斜率大小」的判断（并在 options 层要求更多点）。
    se_slope = 0.0
    if n > 2:
        se_slope = math.sqrt(max(ss_res, 0.0) / (n - 2) / sxx)
    t_stat = slope / se_slope if se_slope > 1e-12 else float('inf') if slope else 0.0
    return {"slope": slope, "intercept": intercept,
            "r2": 1 - ss_res / ss_tot if ss_tot else 1.0,
            "rms": math.sqrt(ss_res / n), "n": n,
            "seSlope": se_slope, "t": t_stat}


# --------------------------------------------------------------------------
# 输入装载与区域构建
# --------------------------------------------------------------------------

def load_json(path):
    return json.loads(Path(path).read_text())


def label_of(element):
    """给区域起个能对上号的名字。

    顺序很重要：**先看本元素自己承载的文本**（ownText），再看它的图片资源，最后才
    退回聚合文本 ``text``。``text`` 是 innerText，会把后代文本一起算进来，于是
    ``<div class="group_6">``（一个背景图容器）会显示成「Restore Choose Your Plan」，
    让人误以为审计在量一段文字、在追究一个文字偏移 —— 而它其实是个背景图区域。
    这种「标签与对象不符」会直接把人带偏，所以宁可显示资源名。
    """
    own = (element.get("ownText") or "").strip().replace("\n", " ")
    if own:
        return own[:28]
    assets = element.get("assets") or []
    if assets:
        path = assets[0].get("path") or assets[0].get("url") or "asset"
        return f"▣{Path(str(path)).name[:24]}"
    if element.get("src"):
        return f"▣{Path(str(element['src'])).name[:24]}"
    text = (element.get("text") or "").strip().replace("\n", " ")
    if text:
        return f"[容器]{text[:22]}"
    return f"<{(element.get('className') or element.get('tag') or '?')[:26]}>"


def text_union_box(element, dpr):
    """元素 ``textMetrics.rects`` 的并集（基准图像素）。无 rects 时返回 None。"""
    rects = (element.get("textMetrics") or {}).get("rects") or []
    if not rects:
        return None
    left = min(r["x"] for r in rects) * dpr
    top = min(r["y"] for r in rects) * dpr
    right = max(r["x"] + r["width"] for r in rects) * dpr
    bottom = max(r["y"] + r["height"] for r in rects) * dpr
    return box_from_ltrb(left, top, right, bottom)


def normalize_text(value):
    """去掉所有空白后的文本，用于判断「包含关系」。"""
    return re.sub(r"\s+", "", value or "")


def minimal_text_elements(elements, dpr):
    """只保留「最小文本承载盒」，丢弃祖先容器伪装的文本元素。

    ``innerText`` 会把后代文本一起算进来，于是每个祖先容器都成了一个「有 291 个字符、
    21 段 rect」的伪文本元素 —— 它的 rect 并集只是子元素矩形的凑合，不是任何一次真实
    排版的结果。拿它做预测会得到横跨整屏的框，把「DOM 与基准图是否一致」整个污染掉：
    一次实测里 clean 基准被判成中位偏移 5pt，全部来自这些伪元素。

    修正后的 ``render_reference.mjs`` 直接给出 ``ownsText``，可据此立刻排除。对旧版
    渲染器产出的、只有 ``textMetrics`` 的事实表，用文本包含关系兜底：

    * 若另一个文本元素的文本（去空白后）是本元素文本的**真子串**，本元素就是祖先；
    * 文本相同时，``rects`` 段数更多的那一个是外层包装容器。

    之所以不能用「矩形包含」判断：祖先的 rect 并集经常比子元素的并集还窄（子元素有
    负坐标或溢出），几何包含并不可靠；而文本包含是定义性的 —— 祖先的文本必然包含
    后代的文本。
    """
    texts = []
    for element in elements:
        metrics = element.get("textMetrics") or {}
        if metrics.get("charCount", 0) <= 1:
            continue
        if element.get("ownsText") is False:
            continue
        box = text_union_box(element, dpr)
        if box is None:
            continue
        texts.append({
            "element": element,
            "box": box,
            "text": normalize_text(element.get("ownText") or element.get("text")),
            "rects": len(metrics.get("rects") or []),
        })

    kept = []
    for item in texts:
        text, rects = item["text"], item["rects"]
        is_ancestor = False
        for other in texts:
            if other is item or not other["text"]:
                continue
            if other["text"] == text:
                # 同一段文本被外层容器重复承载：留 rects 段数更少的那个。
                if other["rects"] < rects:
                    is_ancestor = True
                    break
                continue
            # 更短的文本被本元素包含 ⇒ 本元素是它的祖先容器。
            if len(other["text"]) < len(text) and other["text"] in text:
                # 仅当两者位置确实重叠，才认定是嵌套而不是同一段文字出现在别处。
                a, b = item["box"], other["box"]
                if (a.x <= b.right and b.x <= a.right
                        and a.y <= b.bottom and b.y <= a.bottom):
                    is_ancestor = True
                    break
        if not is_ancestor:
            kept.append(item["element"])
    return kept


def content_box(element, dpr):
    """元素的「有内容」外接框（基准图像素）。

    直接拿元素 rect 当模板会让大片空白参与匹配，把最佳位移拉偏。有文本时用
    ``textMetrics.rects``（实测排版结果）的并集，否则退回 ``rectInReference``。
    """
    rect = element.get("rectInReference")
    if not rect:
        return None
    box = text_union_box(element, dpr)
    if box is not None and box.width >= MIN_REGION_PX and box.height >= MIN_REGION_PX:
        return box
    return box_from(rect)


def build_regions(page_facts, image_size, limit):
    """挑出可定位的元素。先剔除祖先容器伪装的文本元素，再按叶优先去重。"""
    dpr = ((page_facts.get("viewport") or {}).get("devicePixelRatio")) or 1
    raw_elements = page_facts.get("elements") or []
    text_elements = {id(item) for item in minimal_text_elements(raw_elements, dpr)}
    candidates = []
    for element in raw_elements:
        has_text = (element.get("textMetrics") or {}).get("charCount", 0) > 1
        if has_text and id(element) not in text_elements:
            continue
        has_asset = bool(element.get("assets"))
        if not (has_text or has_asset):
            continue
        rect = element.get("rectInReference") or {}
        if rect.get("width", 0) < MIN_REGION_PX or rect.get("height", 0) < MIN_REGION_PX:
            continue
        box = content_box(element, dpr)
        if box is None or box.width < MIN_REGION_PX or box.height < MIN_REGION_PX:
            continue
        if box.right > image_size[0] or box.bottom > image_size[1]:
            continue
        candidates.append({"element": element, "box": box})

    leaves = []
    for item in candidates:
        box = item["box"]
        contained = any(
            other is not item
            and other["box"].x <= box.x + 1 and other["box"].y <= box.y + 1
            and other["box"].right >= box.right - 1 and other["box"].bottom >= box.bottom - 1
            and other["box"].width * other["box"].height > box.width * box.height * 1.5
            and (other["element"].get("textMetrics") or {}).get("charCount", 0) <= 1
            for other in candidates)
        if not contained:
            leaves.append(item)

    leaves.sort(key=lambda item: (item["box"].y, item["box"].x))
    if limit and len(leaves) > limit:
        step = len(leaves) / limit
        leaves = [leaves[int(i * step)] for i in range(limit)]
    return leaves


def band_boxes(image_size, count, max_height_px):
    """把基准图切成若干条横向带。

    带级匹配比元素级稳健：单带内有大量内容、又足够矮，带内局部漂移可忽略，于是
    「带间 offset 的差异」能干净地反映整页比例。元素级在比例差较大时会大量歧义
    （模板被拉伸后就对不上了），此时带级是唯一还能量出斜率的证据。
    """
    height = image_size[1]
    step = height / count
    boxes = []
    for i in range(count):
        top = int(i * step)
        bottom = int(min(height, top + min(step, max_height_px)))
        if bottom - top < MIN_REGION_PX:
            continue
        boxes.append((f"band_{i}", box_from_ltrb(0, top, image_size[0], bottom)))
    return boxes


# --------------------------------------------------------------------------
# 单次比较与汇总
# --------------------------------------------------------------------------

def compare(predictions, matcher, reference_size, options, radius_px, context_px):
    """把一组预测框在目标图里逐一找回。"""
    rows = []
    for item in predictions:
        box = item["box"]
        # 给模板加一圈上下文：纯文字小框在整页里往往不唯一，带上周边结构才能定位。
        # 位移是刚体平移，扩框不改变 dx/dy 的含义。
        probe = box_from_ltrb(max(0, box.x - context_px), max(0, box.y - context_px),
                              min(reference_size[0], box.right + context_px),
                              min(reference_size[1], box.bottom + context_px))
        found = matcher.match(probe, radius_px)
        base = {
            "index": item.get("index"), "label": item.get("label") or "?",
            "tag": item.get("tag"), "className": item.get("className"),
            "boxPx": box.rounded().as_dict(),
            "yCenterPx": round((box.y + box.bottom) / 2, 2),
        }
        if not found:
            rows.append({**base, "matched": False, "confidence": "none",
                         "reason": "模板可见比例不足（元素可能整体不在目标图里）"})
            continue
        dx, dy, score, overlap, peak = found
        ambiguous = peak is not None and peak < options.peak_ratio
        rows.append({**base, "matched": True, "confidence": "low" if ambiguous else "high",
                     "dxPx": dx, "dyPx": dy, "matchScore": round(score, 4),
                     "overlap": round(overlap, 4),
                     "peakRatio": round(peak, 3) if peak is not None else None})
    return rows


def summarize(rows, unit_scale, options, label, band_fit=None):
    """把逐元素结果压成拟合 + 分带表 + 状态。``unit_scale`` 是 图像像素/设备点。

    ``band_fit`` 是同一张图上的带级稳健拟合结果（可选）。元素级在比例差较大时模板被
    拉伸、匹配会大量歧义，此时带级是唯一还能量出斜率的证据；两者不一致时以带级为准。
    """
    trustworthy = [r for r in rows if r["matched"] and r["confidence"] == "high"]
    ambiguous = [r for r in rows if r.get("confidence") == "low"]
    unmatched = [r for r in rows if not r["matched"]]
    unit = "pt" if unit_scale else "px"
    out = {
        "label": label, "unit": unit,
        "elementCount": len(rows), "trustworthyCount": len(trustworthy),
        "ambiguousCount": len(ambiguous), "unmatchedCount": len(unmatched),
    }
    # 统一补上设备点数值，方便直接和契约里的 pt 对照。
    for row in rows:
        if row["matched"]:
            row["dxPt"] = round(row["dxPx"] / unit_scale, 3) if unit_scale else row["dxPx"]
            row["dyPt"] = round(row["dyPx"] / unit_scale, 3) if unit_scale else row["dyPx"]
    out["elements"] = rows

    if len(trustworthy) < 3:
        out.update({"status": "unmeasurable", "reason": "too-few-trustworthy-matches",
                    "detail": (f"可信匹配只有 {len(trustworthy)} 个"
                               f"（歧义 {len(ambiguous)}、未匹配 {len(unmatched)}），无法拟合位移趋势")})
        return out

    points = [(r["yCenterPx"], r["dyPx"]) for r in trustworthy]
    if unit_scale:
        points = [(y / unit_scale, dy / unit_scale) for y, dy in points]
    fit = linear_fit(points)
    out["offsetFit"] = {
        "model": "dy = slope * y + intercept", "unit": unit,
        "slope": round(fit["slope"], 6), "intercept": round(fit["intercept"], 3),
        "impliedScale": round(1 + fit["slope"], 6),
        "r2": round(fit["r2"], 4), "rmsResidual": round(fit["rms"], 3), "n": fit["n"],
        # 斜率的信噪比：量纲无关，比 R² 更适合当阈值（见 linear_fit 的注释）。
        "seSlope": round(fit["seSlope"], 6),
        "t": round(fit["t"], 3) if math.isfinite(fit["t"]) else None,
    }

    ordered = sorted(trustworthy, key=lambda r: r["yCenterPx"])
    bands = []
    count = max(2, min(options.bands, len(ordered)))
    for i in range(count):
        chunk = ordered[i * len(ordered) // count:(i + 1) * len(ordered) // count]
        if not chunk:
            continue
        divisor = unit_scale or 1
        y0 = chunk[0]["boxPx"]["y"] / divisor
        y1 = (chunk[-1]["boxPx"]["y"] + chunk[-1]["boxPx"]["height"]) / divisor
        bands.append({
            "band": f"band_{i}", "yRange": [round(y0, 1), round(y1, 1)],
            "meanDy": round(sum(r["dyPt"] for r in chunk) / len(chunk), 3),
            "meanDx": round(sum(r["dxPt"] for r in chunk) / len(chunk), 3),
            "members": [f"#{r['index']} {r['label']}" for r in chunk],
        })
    out["bands"] = bands

    max_dx = max(abs(r["dxPt"]) for r in trustworthy)
    max_dy = max(abs(r["dyPt"]) for r in trustworthy)
    # 把「是谁超的容差」一并记下来，供 conclude() 直接引用。曾经 conclude 自己再扫一遍
    # 全量 elements（含低置信行），于是同一个 12pt 横向错位在两处被归到不同元素上
    # （#37 Terms 与 #34 Try For Free，11.988 vs 12.003）——同一事实两个说法。
    worst_dx = max(trustworthy, key=lambda r: abs(r["dxPt"]))
    worst_dy = max(trustworthy, key=lambda r: abs(r["dyPt"]))
    out["extremes"] = {"maxAbsDx": round(max_dx, 3), "maxAbsDy": round(max_dy, 3),
                       "positionTolerance": options.position_tolerance, "unit": unit,
                       "mostDx": {"index": worst_dx["index"], "label": worst_dx["label"],
                                  "dxPt": worst_dx["dxPt"]},
                       "mostDy": {"index": worst_dy["index"], "label": worst_dy["label"],
                                  "dyPt": worst_dy["dyPt"]}}

    # ---- 缩放判定：斜率大小 + 拟合可信度，二者都要 ----
    slope = fit["slope"]
    scale_signal = abs(slope) > options.scale_tolerance
    # 元素级斜率是否可信：t 信噪比达标，或 R² 达标；或者带级独立给出同向的缩放信号。
    band_slope = (band_fit or {}).get("slope")
    band_signal = band_slope is not None and abs(band_slope) > options.scale_tolerance
    quality = abs(fit["t"]) >= DEFAULT_T_MIN or fit["r2"] >= DEFAULT_R2_MIN
    out["scaleSignal"] = {
        "elementSlope": round(slope, 6), "elementT": out["offsetFit"]["t"],
        "elementTrustworthy": bool(scale_signal and quality),
        "bandSlope": band_slope, "bandSignal": bool(band_signal),
    }

    if scale_signal and quality:
        out.update({"status": "needs-review", "reason": "scale-mismatch",
                    "detail": (f"隐含比例 {1 + slope:.5f}"
                               f"（偏离 1.0 达 {slope * 100:+.3f}%，R²={fit['r2']:.2f}，"
                               f"t={fit['t']:.1f}）；"
                               "位移随 y 线性变化，属缩放/坐标系不一致，不是单纯平移")})
    elif scale_signal and band_signal:
        # 元素级自己不够硬，但带级独立复现了同向缩放信号 —— 这是真信号，不是噪声。
        out.update({"status": "needs-review", "reason": "scale-mismatch",
                    "detail": (f"元素级斜率 {slope:+.6f} 的拟合可信度不足"
                               f"（t={fit['t']:.1f}，R²={fit['r2']:.2f}，点少或模板歧义），"
                               f"但带级独立给出 slope={band_slope:+.6f}"
                               f"（隐含比例 {1 + band_slope:.5f}）：斜率超容差且被两套估计复现，"
                               "判为缩放/坐标系不一致")})
    elif scale_signal:
        # 斜率超容差，但两套估计都没能证实它。不下结论，交给人看：这可能是真实的小比例差
        # 被量化噪声掩盖（窄画布上总位移本来就小），也可能是匹配噪声。
        out.update({"status": "needs-review", "reason": "scale-signal-weak-fit",
                    "detail": (f"斜率 {slope:+.6f}（隐含比例 {1 + slope:.5f}）超容差 "
                               f"{options.scale_tolerance}，但元素级 t={fit['t']:.1f}、R²={fit['r2']:.2f} "
                               "不足以判定，带级也未复现。"
                               "窄画布上真实的 0.3% 比例差总位移只有 1pt 量级，会被量化噪声掩盖；"
                               "若目标设备更高，请用该设备的整页截图重跑，或人工复核画布缩放策略")})
    elif max(abs(fit["intercept"]), max_dy, max_dx) > options.position_tolerance:
        # 触发量是三个数里的最大值，**报的时候必须报那一个**。曾经这里只报纵向的
        # intercept 与 max_dy，而触发它的是横向 max_dx，于是输出成
        # 「常数位移 +0.00pt（最大 0.01pt），超容差 2.0pt」—— 自相矛盾，看的人会先
        # 怀疑工具坏了，从而放过一个真实的横向错位（那次是页脚 Terms 差 12pt）。
        offender_dx = max(trustworthy, key=lambda r: abs(r["dxPt"]))
        offender_dy = max(trustworthy, key=lambda r: abs(r["dyPt"]))
        segments = []
        if abs(fit["intercept"]) > options.position_tolerance or max_dy > options.position_tolerance:
            segments.append(f"纵向 常数位移 {fit['intercept']:+.2f}{unit}"
                            f"（各元素最大 {max_dy:.2f}{unit}，出自 #{offender_dy['index']} {offender_dy['label']}）")
        if max_dx > options.position_tolerance:
            segments.append(f"横向 各元素最大 {max_dx:.2f}{unit}"
                            f"（出自 #{offender_dx['index']} {offender_dx['label']}）")
        out.update({"status": "needs-review", "reason": "constant-offset",
                    "detail": "；".join(segments) + f"，超容差 {options.position_tolerance}{unit}"})
    elif fit["rms"] > options.position_tolerance:
        out.update({"status": "needs-review", "reason": "scatter-exceeds-tolerance",
                    "detail": (f"位移离散度 {fit['rms']:.2f}{unit} 超容差："
                               "各区域各自不同，需逐区域排查")})
    else:
        out.update({"status": "aligned"})
    return out


def ink_probe(reference_edges, predictions, radius_px, options):
    """量基准图里每个 DOM 预测框位置上的**实际墨迹**在哪。

    为什么不能用模板匹配来做这件事。模板若取自 ``reference.png`` 自身再回
    ``reference.png`` 里找，恒等位置必然得分 0、``(dx, dy)`` 恒为 ``(0, 0)``，
    ``status`` 永远 ``aligned``。那是个恒真式，只会输出「DOM 与基准图一致」的假保证
    —— 正是这次事故里那种「所有检查全绿但内容错位」的成因。要判断基准图是否忠于
    DOM 事实，必须**从图里独立测量**，再和预测框比。

    每项输出：

    * ``inkCoverage``：预测内容框内被墨迹覆盖的面积比例。DOM 说这里有文字、图上却
      空白 ⇒ 基准不是在采集事实表时的那个 viewport/scale 下渲染的。
    * ``ownInkRatio``：墨迹落在预测框内的量 / 框外搜索窗内的总量。偏低说明邻居的
      墨迹污染了质心，该点不可用于拟合。
    * ``dxPx`` / ``dyPx``：墨迹质心 − 预测框中心（按边缘强度加权，天然亚像素）。
      正常情况应接近 0，允许字形的固有偏置（降部、字距）带来的几像素常数偏差。
    """
    threshold = options.ink_threshold
    full_w, full_h = reference_edges.size
    rows = []
    for item in predictions:
        box = item["box"]
        wl = max(0, int(box.x - radius_px))
        wt = max(0, int(box.y - radius_px))
        wr = min(full_w, int(math.ceil(box.right + radius_px)))
        wb = min(full_h, int(math.ceil(box.bottom + radius_px)))
        base = {"index": item.get("index"), "label": item.get("label") or "?",
                "tag": item.get("tag"), "className": item.get("className"),
                "boxPx": box.rounded().as_dict(),
                "yCenterPx": round((box.y + box.bottom) / 2, 2)}
        if wr - wl < 4 or wb - wt < 4:
            rows.append({**base, "matched": False, "confidence": "none",
                         "reason": "预测框超出基准图或过小"})
            continue

        data = list(pixels_of(reference_edges.crop((wl, wt, wr, wb))))
        win_w = wr - wl
        # 预测框在窗口内的相对区间。
        ix0, iy0 = int(box.x) - wl, int(box.y) - wt
        ix1, iy1 = int(round(box.right)) - wl, int(round(box.bottom)) - wt
        inner_w = max(0, ix1 - ix0)
        inner_h = max(0, iy1 - iy0)

        total_weight = 0.0
        inner_weight = 0.0
        inner_pixels = 0
        sum_x = 0.0
        sum_y = 0.0
        for position, value in enumerate(data):
            if value < threshold:
                continue
            py, px = divmod(position, win_w)
            weight = float(value)
            total_weight += weight
            sum_x += weight * px
            sum_y += weight * py
            if ix0 <= px < ix1 and iy0 <= py < iy1:
                inner_weight += weight
                inner_pixels += 1

        if total_weight <= 0:
            rows.append({**base, "matched": True, "confidence": "high",
                         "inkCoverage": 0.0, "ownInkRatio": 0.0,
                         "dxPx": None, "dyPx": None,
                         "reason": "预测框内及其周边没有任何墨迹（DOM 说有内容，图上却没有）"})
            continue

        area = max(1, inner_w * inner_h)
        coverage = inner_pixels / area
        centroid_x = sum_x / total_weight + wl
        centroid_y = sum_y / total_weight + wt
        dx = centroid_x - (box.x + box.right) / 2
        dy = centroid_y - (box.y + box.bottom) / 2
        own_ratio = inner_weight / total_weight
        rows.append({**base, "matched": True,
                     "confidence": "high" if own_ratio >= options.ink_own_min else "low",
                     "inkCoverage": round(coverage, 5), "ownInkRatio": round(own_ratio, 3),
                     "dxPx": round(dx, 3), "dyPx": round(dy, 3)})
    return rows


def summarize_ink(rows, unit_scale, options, label):
    """把墨迹探针结果压成「基准图是否忠于 DOM 事实」的判定。"""
    unit = "pt" if unit_scale else "px"
    probed = [r for r in rows if r["matched"]]
    # 覆盖度必须在**所有探到的元素**上统计，不能只看能算出质心的那些。内容整体偏出
    # 搜索窗时，恰好就是量不出质心的情况；若把这些行丢掉，最严重的故障反而会被算成
    # 「证据不足」，而不是「该有内容的地方没有内容」—— 那正是这次事故里最需要的判词。
    usable = [r for r in probed if r["confidence"] == "high" and r.get("dxPx") is not None]
    out = {"label": label, "unit": unit, "elementCount": len(rows),
           "probedCount": len(probed), "usableCount": len(usable), "elements": rows}
    if not probed:
        out.update({"status": "unmeasurable", "reason": "no-ink-probes",
                    "detail": "没有任何元素的预测框落在基准图内，无法探测"})
        return out

    for row in usable:
        row["dxPt"] = round(row["dxPx"] / unit_scale, 3) if unit_scale else row["dxPx"]
        row["dyPt"] = round(row["dyPx"] / unit_scale, 3) if unit_scale else row["dyPx"]

    covered = [r for r in probed if r["inkCoverage"] >= options.ink_coverage_min]
    missing = [r for r in probed if r["inkCoverage"] < options.ink_coverage_min]
    missing_ratio = len(missing) / len(probed)
    out["coverage"] = {
        "threshold": options.ink_coverage_min,
        "withInk": len(covered), "withoutInk": len(missing),
        "missingRatio": round(missing_ratio, 3),
        "missingElements": [f"#{r['index']} {r['label']}" for r in missing],
    }

    # 判定顺序：先看「该有内容的地方有没有内容」，这是最硬的证据（且不依赖任何阈值
    # 调参）；再看位移趋势。
    if missing_ratio >= options.ink_missing_ratio:
        out.update({"status": "needs-review", "reason": "content-missing-at-predicted-position",
                    "detail": (f"{len(missing)}/{len(probed)} 个元素在 DOM 预测的位置上"
                               f"量不到墨迹（覆盖度 < {options.ink_coverage_min}）："
                               "基准图不是在采集 page-facts 时的 viewport/scale 下渲染的")})
        return out

    if len(usable) < 3:
        out.update({"status": "unmeasurable", "reason": "too-few-clean-ink-probes",
                    "detail": (f"能干净定位的墨迹探针只有 {len(usable)} 个"
                               f"（探到 {len(probed)} 个，其余被相邻元素墨迹污染）；"
                               "无法拟合位移趋势，请放宽 --ink-own-min 或人工核查")})
        return out

    points = [(r["yCenterPx"], r["dyPx"]) for r in usable]
    if unit_scale:
        points = [(y / unit_scale, dy / unit_scale) for y, dy in points]
    fit = linear_fit(points)
    out["offsetFit"] = {
        "model": "dy = slope * y + intercept", "unit": unit,
        "slope": round(fit["slope"], 6), "intercept": round(fit["intercept"], 3),
        "impliedScale": round(1 + fit["slope"], 6),
        "r2": round(fit["r2"], 4), "rmsResidual": round(fit["rms"], 3), "n": fit["n"],
        "seSlope": round(fit["seSlope"], 6),
        "t": round(fit["t"], 3) if math.isfinite(fit["t"]) else None,
    }
    max_dx = max(abs(r["dxPt"]) for r in usable)
    max_dy = max(abs(r["dyPt"]) for r in usable)
    # 用**中位数**判定，不用最大值。墨迹质心相对元素框中心天然带一个字形偏置
    # （降部、字距、图标内边距方向、相邻元素的墨迹渗入搜索窗），个别元素偏 3–6pt 是
    # 正常的。而「基准渲染时的 viewport/scale 不对」会让**所有**元素一起偏，中位数
    # 恰好抓这种整体位移，且不被一两个离群元素拉爆。
    all_offsets = sorted([abs(r["dxPt"]) for r in usable] + [abs(r["dyPt"]) for r in usable])
    median_offset = all_offsets[len(all_offsets) // 2] if all_offsets else 0.0
    out["extremes"] = {"maxAbsDx": round(max_dx, 3), "maxAbsDy": round(max_dy, 3),
                       "medianAbsOffset": round(median_offset, 3),
                       "tolerance": options.dom_tolerance, "unit": unit}

    if abs(fit["slope"]) > options.scale_tolerance and (
            abs(fit["t"]) >= DEFAULT_T_MIN or fit["r2"] >= DEFAULT_R2_MIN):
        out.update({"status": "needs-review", "reason": "scale-mismatch",
                    "detail": (f"基准图内容相对 DOM 预测框存在缩放：隐含比例 "
                               f"{1 + fit['slope']:.5f}（偏离 1.0 达 {fit['slope'] * 100:+.3f}%，"
                               f"R²={fit['r2']:.2f}）")})
    elif median_offset > options.dom_tolerance:
        out.update({"status": "needs-review", "reason": "constant-offset",
                    "detail": (f"基准图内容相对 DOM 预测框系统性偏移"
                               f"（中位偏移 {median_offset:.2f}{unit}，"
                               f"最大 dx={max_dx:.2f}{unit}、dy={max_dy:.2f}{unit}，"
                               f"超容差 {options.dom_tolerance}{unit}）")})
    else:
        out.update({"status": "aligned"})
    return out


def band_summary(matcher, image_size, unit_scale, options, radius_px):
    rows = []
    for name, box in band_boxes(image_size, options.bands, options.band_height * (unit_scale or 1)):
        found = matcher.match(box, radius_px, min_overlap=0.8)
        if not found:
            rows.append({"band": name, "matched": False, "boxPx": box.rounded().as_dict()})
            continue
        dx, dy, score, overlap, peak = found
        rows.append({"band": name, "matched": True, "boxPx": box.rounded().as_dict(),
                     "dxPx": round(dx, 3), "dyPx": round(dy, 3),
                     "matchScore": round(score, 4),
                     "peakRatio": round(peak, 3) if peak is not None else None,
                     "dxPt": round(dx / unit_scale, 3) if unit_scale else round(dx, 3),
                     "dyPt": round(dy / unit_scale, 3) if unit_scale else round(dy, 3),
                     "confidence": "low" if (peak is not None and peak < options.peak_ratio) else "high"})
    usable = [r for r in rows if r["matched"] and r["confidence"] == "high"]
    result = {"elements": rows, "usableCount": len(usable)}
    if len(usable) < 3:
        result.update({"status": "unmeasurable", "reason": "too-few-usable-bands"})
        return result
    points = [(r["boxPx"]["y"] + r["boxPx"]["height"] / 2, r["dyPx"]) for r in usable]
    if unit_scale:
        points = [(y / unit_scale, dy / unit_scale) for y, dy in points]
    fit = linear_fit(points)
    result["offsetFit"] = {
        "model": "dy = slope * y + intercept", "unit": "pt" if unit_scale else "px",
        "slope": round(fit["slope"], 6), "intercept": round(fit["intercept"], 3),
        "impliedScale": round(1 + fit["slope"], 6),
        "r2": round(fit["r2"], 4), "rmsResidual": round(fit["rms"], 3), "n": fit["n"],
        "seSlope": round(fit["seSlope"], 6),
        "t": round(fit["t"], 3) if math.isfinite(fit["t"]) else None,
    }
    # 带级是「更稳的估计」而非「更多的点」：它样本少但每个样本都基于大量内容，
    # 所以判定规则与元素级一致（斜率超容差 + 信噪比达标）。
    significant = (abs(fit["slope"]) > options.scale_tolerance
                   and (abs(fit["t"]) >= DEFAULT_T_MIN or fit["r2"] >= DEFAULT_R2_MIN))
    if significant:
        result.update({"status": "needs-review", "reason": "scale-mismatch"})
    elif abs(fit["intercept"]) > options.position_tolerance:
        result.update({"status": "needs-review", "reason": "constant-offset"})
    elif fit["rms"] > options.position_tolerance:
        result.update({"status": "needs-review", "reason": "scatter-exceeds-tolerance"})
    else:
        result.update({"status": "aligned"})
    return result


# --------------------------------------------------------------------------
# 主体
# --------------------------------------------------------------------------

def audit(options):
    reference = Image.open(options.reference).convert('RGBA')
    actual = Image.open(options.actual).convert('RGBA')
    page_facts = load_json(options.page_facts) if options.page_facts else None
    runtime_device = load_json(options.runtime_device) if options.runtime_device else None

    result = {
        "schemaVersion": 1,
        "reference": str(Path(options.reference).resolve()),
        "actual": str(Path(options.actual).resolve()),
        "referenceSize": {"width": reference.size[0], "height": reference.size[1]},
        "actualSize": {"width": actual.size[0], "height": actual.size[1]},
        "positionTolerancePt": options.position_tolerance,
        "scaleTolerance": options.scale_tolerance,
        "warnings": [],
        "comparisons": {},
    }

    # ---- 画布变换：只用于把 DOM 坐标映射到设备点、以及判断基准是否在设备画布上 ----
    transform, transform_source = None, None
    try:
        if options.transform:
            payload = load_json(options.transform)
            payload = payload.get("canvasTransform", payload)
            transform = transform_from_canvas_transform(
                payload, screenshot_scale=(runtime_device or {}).get("screenshotScale"))
            transform_source = str(options.transform)
        elif runtime_device:
            canvas = options.canvas
            if not canvas:
                viewport = (page_facts or {}).get("viewport") or {}
                if viewport.get("width"):
                    canvas = f"{viewport['width']}x{viewport['height']}"
            if canvas:
                cw, _, ch = canvas.partition("x")
                transform = transform_from_runtime_device(runtime_device, float(cw), float(ch),
                                                         policy=options.policy, reason=options.reason)
                transform_source = "runtime-device + canvas"
    except CanvasMapError as error:
        result["warnings"].append(f"画布变换不可用：{error}")

    unit_scale = transform.screenshot_scale if transform else None
    result["unitScalePxPerPt"] = unit_scale
    if transform:
        result["canvasTransform"] = transform.as_dict()
        result["canvasTransformSource"] = transform_source

    device_pixels = (runtime_device or {}).get("screenshotPixels")
    if device_pixels:
        on_canvas = reference.size == (device_pixels["width"], device_pixels["height"])
        result["referenceOnDeviceCanvas"] = on_canvas
        if not on_canvas:
            result["warnings"].append(
                f"基准图 {reference.size[0]}x{reference.size[1]} 不在设备画布上"
                f"（screenshotPixels {device_pixels['width']}x{device_pixels['height']}）："
                "像素级比较不具证据效力，必须先按设备画布重渲染基准")
    else:
        result["warnings"].append("未提供 runtime-device.json 的 screenshotPixels，无法确认基准是否在设备画布上")

    if page_facts is None:
        result.update({"status": "unmeasurable", "reason": "missing-page-facts",
                       "detail": "没有 page-facts.json，无法做元素级定位，也无法判断基准与 DOM 是否一致",
                       "verdict": "补齐页面级 reference/page-facts.json 后重跑；仅比像素总数不足以判定对齐。"})
        return result, 2

    regions = build_regions(page_facts, reference.size, options.max_regions)
    if not regions:
        result.update({"status": "unmeasurable", "reason": "no-regions",
                       "detail": "事实表里没有可用于模板匹配的元素",
                       "verdict": "检查 page-facts.json 是否为空或元素尺寸过小。"})
        return result, 2

    context_px = options.context * (unit_scale or 1.0)
    radius_px = options.radius * (unit_scale or 1.0)
    band_radius_px = options.band_radius * (unit_scale or 1.0)
    result.update({"radiusPx": round(radius_px, 3), "bandRadiusPx": round(band_radius_px, 3),
                   "contextPx": round(context_px, 3), "regionCount": len(regions)})

    # domVsReference 走墨迹探针，不用模板匹配（见 ink_probe 的文档说明）。
    matcher_actual = Matcher(edge_map(reference), edge_map(actual))

    # ---- 全图最佳位移：元素级之前先看一眼整体平移 ----
    inset = int(radius_px) + 2
    if reference.size[0] > 4 * inset and reference.size[1] > 4 * inset:
        probe = box_from_ltrb(inset, inset, reference.size[0] - inset, reference.size[1] - inset)
        found = matcher_actual.match(probe, radius_px, min_overlap=0.9)
        if found:
            dx, dy, score, _, peak = found
            result["globalShift"] = {
                "dxPx": dx, "dyPx": dy, "score": round(score, 4),
                "peakRatio": round(peak, 3) if peak is not None else None,
                "dxPt": round(dx / unit_scale, 3) if unit_scale else None,
                "dyPt": round(dy / unit_scale, 3) if unit_scale else None,
                "interpretation": "把整张基准图整体平移这个量后与实测图最相似",
            }

    predictions = [{"index": item["element"].get("index"),
                    "label": label_of(item["element"]),
                    "tag": item["element"].get("tag"),
                    "className": item["element"].get("className"),
                    "box": item["box"]} for item in regions]

    # ---- A. DOM 事实 vs 基准图 ----
    # 注意：这里**不能**用模板匹配。模板若取自 reference 自身再回 reference 里找，
    # 恒等位置必然得分 0，(dx, dy) 恒为 (0, 0)，永远是 aligned —— 那是个恒真式，
    # 只会给出「DOM 与基准图一致」的假保证。正确做法是量基准图里**实际墨迹**在哪，
    # 再和 DOM 预测的框比。见 ink_probe 的文档。
    rows_dom = ink_probe(edge_map(reference), predictions, radius_px, options)
    dom_vs_reference = summarize_ink(rows_dom, unit_scale, options,
                                    "domVsReference：page-facts 预测框 vs reference.png 实际墨迹")
    dom_vs_reference["predictedFrom"] = "page-facts.json: elements[].rectInReference（优先 textMetrics.rects）"
    dom_vs_reference["measuredFrom"] = "reference.png 的墨迹质心（非模板匹配）"
    result["comparisons"]["domVsReference"] = dom_vs_reference

    # ---- B. 基准图 vs 实测图 ----
    if reference.size != actual.size:
        result["comparisons"]["referenceVsActual"] = {
            "label": "referenceVsActual", "status": "unmeasurable", "reason": "size-mismatch",
            "detail": (f"基准图 {reference.size[0]}x{reference.size[1]} 与实测图 "
                       f"{actual.size[0]}x{actual.size[1]} 尺寸不同，无法做位移分析"),
        }
    else:
        # 带级稳健拟合先算：元素级在比例差较大时会大量歧义，此时它是斜率的主证据，
        # 需要提前交给 summarize 做交叉印证。
        band_actual = band_summary(matcher_actual, reference.size, unit_scale,
                                   options, band_radius_px)
        rows_actual = compare(predictions, matcher_actual, reference.size, options,
                              radius_px, context_px)
        ref_vs_actual = summarize(rows_actual, unit_scale, options,
                                  "referenceVsActual：以同一预测框，在 actual 里找回",
                                  band_fit=band_actual.get("offsetFit"))
        ref_vs_actual["predictedFrom"] = "reference.png 内的元素位置（与 domVsReference 同一组框）"
        ref_vs_actual["target"] = "actual（本次 run 的目标 App 原始截图）"
        ref_vs_actual["bandRobust"] = band_actual
        result["comparisons"]["referenceVsActual"] = ref_vs_actual

    result.update(conclude(result))
    return result, {"aligned": 0, "needs-review": 1, "unmeasurable": 2}[result["status"]]


def worst(statuses):
    return max(statuses, key=lambda s: STATUS_ORDER.get(s, 2))


def conclude(result):
    dom = result["comparisons"]["domVsReference"]
    ref = result["comparisons"].get("referenceVsActual")
    status = worst([dom["status"]] + ([ref["status"]] if ref else ["unmeasurable"]))

    # 量不出来时不要冒充「一致」。基准可信度是未知，不是通过。
    if dom["status"] == "unmeasurable":
        return {
            "status": "unmeasurable", "reason": "baseline-vs-dom-unmeasurable",
            "trust": "未知（基准是否忠于 DOM 无法判定）",
            "nextAction": "补齐 page-facts 里可定位的元素，或放宽 --ink-own-min 后重跑",
            "verdict": ("**无法判定基准图是否忠于 DOM**："
                        f"{dom.get('detail') or dom.get('reason')}。"
                        "在补上这层证据之前，referenceVsActual 的结论只能当参考。"),
        }

    # 基准图自己就和 DOM 不符时，基准不可信 —— 这是最容易被忽略、也最容易带偏整轮修复的形态。
    if dom["status"] != "aligned":
        return {
            "status": status, "reason": "baseline-disagrees-with-dom",
            "trust": "DOM（事实表）",
            "nextAction": "重渲染基准并重新批准，然后重跑本审计",
            "verdict": (
                "**基准图与 DOM 事实不符，基准本身不可信**"
                f"（{dom.get('detail') or dom.get('reason')}）。"
                "此时不要照着基准图调 App 代码：先确认渲染基准时的 viewport/scale 与"
                "page-facts 采集时一致（--viewport-from runtime-device.json），"
                "重渲染并重新批准基准，再比较实测截图。"),
        }

    if ref is None or ref["status"] == "unmeasurable":
        return {
            "status": status, "reason": "reference-vs-actual-unmeasurable",
            "trust": "DOM 与基准图（二者一致）",
            "nextAction": "补齐同源实测截图后重跑",
            "verdict": (f"DOM 与基准图一致，但基准图与实测图无法比较："
                        f"{ref.get('detail') if ref else '缺少实测图'}"),
        }

    fit = ref.get("offsetFit")
    if ref["status"] == "aligned":
        return {
            "status": "aligned", "trust": "三者一致",
            "nextAction": "可以进入其他闸门（编译 / 测试 / 资源）",
            "verdict": (f"三方一致：DOM、基准图、实测截图的元素位置都在容差内"
                        f"（最大偏移 {ref['extremes']['maxAbsDy']}pt）。"),
        }

    if ref.get("reason") == "scale-signal-weak-fit":
        return {
            "status": status, "reason": "scale-signal-weak-fit",
            "trust": "DOM 与基准图（二者一致）；比例结论待定",
            "nextAction": ("在目标设备上重跑一次，或人工核对 canvasTransform 的 policy"
                           "（fill 会单独放大约束方向）"),
            "verdict": (
                "**基准图可信，但比例差证据不足以下结论**：元素级斜率超容差"
                f"（{fit['slope']:+.6f}，隐含比例 {fit['impliedScale']:.5f}），"
                f"然而 t={fit['t']}、R²={fit['r2']:.2f}，带级也没复现。"
                "窄画布上真实的 0.3% 比例差总位移只有 1pt 量级，会被量化噪声掩盖。"
                "**不要**据此直接改代码；先用目标设备的整页截图重跑本审计，"
                "或在目标设备上量一个已知高度的元素来确认比例。"),
        }

    if ref.get("reason") == "scale-mismatch":
        extra = ""
        band_fit = (ref.get("bandRobust") or {}).get("offsetFit")
        if band_fit and abs(band_fit["slope"] - fit["slope"]) > result["scaleTolerance"]:
            extra = (f" 带级稳健拟合给出 slope={band_fit['slope']:.5f}"
                     f"（隐含比例 {band_fit['impliedScale']:.5f}，R²={band_fit['r2']:.2f}）；"
                     "元素级与带级不一致时以带级为准（元素级在小文本上易歧义）。")
        return {
            "status": status, "reason": "scale-mismatch",
            "trust": "DOM 与基准图（二者一致）",
            "nextAction": "核对 mapper 与 canvasTransform policy，改 App 代码；不要动基准",
            "verdict": (
                "**基准图可信，问题在 App 实现侧**：基准图与 DOM 一致，而实测截图相对"
                f"基准图整体发生了缩放（隐含比例 {fit['impliedScale']:.5f}，偏离 1.0 达 "
                f"{fit['slope'] * 100:+.3f}%，R²={fit['r2']:.2f}，t={fit['t']}）。"
                "这不是随机误差，是坐标系/比例不一致：按区域检查映射用的 scale、"
                "canvasTransform 的 policy（fill 会单独放大约束方向），以及各子视图"
                "是否复用了同一 mapper。" + extra),
        }

    if ref.get("reason") == "constant-offset":
        max_dx = ref["extremes"]["maxAbsDx"]
        max_dy = ref["extremes"]["maxAbsDy"]
        tol = result["positionTolerancePt"]
        # 与 summarize 同样的问题：结论里也必须报**真正超容差的那个方向**。
        # 只报纵向会让「横向差 12pt」看起来像「位移 0.00pt 却报错」。
        # 归因直接取 summarize 记录的 extremes.mostDx/mostDy，不要再自己扫一遍，
        # 否则同一处错位会在两处被算到不同元素头上。
        most_dx = ref["extremes"].get("mostDx") or {}
        most_dy = ref["extremes"].get("mostDy") or {}
        parts = []
        if max_dy > tol or abs(fit["intercept"]) > tol:
            parts.append(f"纵向最大 {max_dy:.2f}pt"
                         + (f"（#{most_dy['index']} {most_dy['label']}）" if most_dy else ""))
        if max_dx > tol:
            parts.append(f"横向最大 {max_dx:.2f}pt"
                         + (f"（#{most_dx['index']} {most_dx['label']}）" if most_dx else ""))
        return {
            "status": status, "reason": "constant-offset",
            "trust": "DOM 与基准图（二者一致）",
            "nextAction": "按平移类根因排查：safe-area、contentInsetAdjustmentBehavior、父容器起点",
            "verdict": (
                "**基准图可信，问题在 App 实现侧**："
                + "；".join(parts)
                + f"，超容差 {tol}pt（纵向拟合斜率 {fit['slope'] * 100:+.3f}%，"
                  f"R²={fit['r2']:.2f} ⇒ 位移近似常数，属平移类问题，不是缩放问题）。"
                  "横向错位优先看是否把多个元素塞进了同一个控件（例如把页脚三项并成"
                  "一个 label 用空格排版），纵向错位优先看父容器起点与安全区。"),
        }

    return {
        "status": status, "reason": ref.get("reason"),
        "trust": "DOM 与基准图（二者一致）",
        "nextAction": "逐区域排查；优先看 extremes 最大的元素所在区域",
        "verdict": (
            "**基准图可信，问题在 App 实现侧**：各元素位移不一致"
            f"（离散度 {fit['rms']:.2f}pt，R²={fit['r2']:.2f}，最大 "
            f"{ref['extremes']['maxAbsDy']}pt）。没有统一位移规律 ⇒ 需逐区域看，"
            "通常是局部布局或资源映射问题。"),
    }


# --------------------------------------------------------------------------

def print_summary(result):
    print(f"reference {result['referenceSize']['width']}x{result['referenceSize']['height']}"
          f"  actual {result['actualSize']['width']}x{result['actualSize']['height']}"
          f"  容差 {result['positionTolerancePt']}pt")
    if result.get("unitScalePxPerPt"):
        print(f"换算：1pt = {result['unitScalePxPerPt']}px（canvasTransform.screenshotScale）")
    if result.get("referenceOnDeviceCanvas") is False:
        print("！基准图不在设备画布上 —— 像素比较不具证据效力")
    for warning in result.get("warnings") or []:
        print(f"警告: {warning}")

    for key in ("domVsReference", "referenceVsActual"):
        section = result["comparisons"].get(key)
        if not section:
            continue
        print(f"\n===== {key} =====")
        if section.get("status") not in ("unmeasurable",):
            unit = section.get("unit", "px")
            scale = result.get("unitScalePxPerPt") or 1
            rows = section.get("elements") or []
            ink_rows = bool(rows) and "inkCoverage" in rows[0]
            if rows and ink_rows:
                print(f"{'元素':<30}{'y_center(' + unit + ')':>14}{'dx(' + unit + ')':>10}"
                      f"{'dy(' + unit + ')':>10}{'覆盖度':>9}{'自有':>7}")
                for row in rows:
                    y = row["yCenterPx"] / scale
                    flag = ' ' if row.get("confidence") == "high" else '~'
                    dx = row.get("dxPt")
                    dy = row.get("dyPt")
                    box = (f"{dx:>10.2f}{dy:>10.2f}" if dx is not None and dy is not None
                           else f"{'无墨迹':>20}")
                    print(f"{(flag + (row['label'] or ''))[:29]:<30}{y:>14.1f}{box}"
                          f"{row.get('inkCoverage', 0):>9.4f}{row.get('ownInkRatio', 0):>7.2f}")
            elif rows:
                print(f"{'元素':<30}{'y_center(' + unit + ')':>14}{'dx(' + unit + ')':>10}"
                      f"{'dy(' + unit + ')':>10}{'peak':>7}{'score':>8}")
                for row in rows:
                    y = row["yCenterPx"] / scale
                    if not row["matched"]:
                        print(f"{(row['label'] or '')[:29]:<30}{y:>14.1f}{'-':>10}{'-':>10}{'-':>7}{'未匹配':>8}")
                        continue
                    flag = ' ' if row["confidence"] == "high" else '~'
                    peak = row["peakRatio"] if row["peakRatio"] is not None else 0
                    print(f"{(flag + (row['label'] or ''))[:29]:<30}{y:>14.1f}"
                          f"{row['dxPt']:>10.2f}{row['dyPt']:>10.2f}{peak:>7.2f}{row['matchScore']:>8.1f}")
            coverage = section.get("coverage")
            if coverage:
                print(f"墨迹覆盖：{coverage['withInk']} 个有内容、{coverage['withoutInk']} 个"
                      f"在预测位置量不到内容（占比 {coverage['missingRatio']:.0%}）")
                if coverage["missingElements"]:
                    print(f"  量不到内容的元素：{', '.join(coverage['missingElements'][:8])}")
            fit = section.get("offsetFit")
            if fit:
                t_text = f"{fit['t']:.1f}" if fit.get("t") is not None else "n/a"
                print(f"拟合 dy = {fit['slope']:.6f}*y + {fit['intercept']:+.2f}（{fit['unit']}）"
                      f"  隐含比例 {fit['impliedScale']:.6f}  R²={fit['r2']:.3f}  "
                      f"t={t_text}  rms={fit['rmsResidual']:.2f}  n={fit['n']}")
            for band in section.get("bands") or []:
                print(f"  {band['band']}: y={band['yRange'][0]:.0f}-{band['yRange'][1]:.0f}{unit} "
                      f"meanDy={band['meanDy']:+.2f} meanDx={band['meanDx']:+.2f} "
                      f"({len(band['members'])} 个)")
            band = section.get("bandRobust")
            if band and band.get("offsetFit"):
                fit = band["offsetFit"]
                print(f"带级稳健拟合：slope={fit['slope']:.6f} 隐含比例={fit['impliedScale']:.6f} "
                      f"R²={fit['r2']:.3f} n={fit['n']}（可用带 {band['usableCount']}）")
        print(f"→ status={section['status']}"
              + (f" reason={section.get('reason')}" if section.get("reason") else "")
              + (f" | {section['detail']}" if section.get("detail") else ""))

    print(f"\n总体 status={result['status']}"
          + (f" reason={result['reason']}" if result.get("reason") else ""))
    if result.get("trust"):
        print(f"该信谁：{result['trust']}")
    if result.get("verdict"):
        print(f"\n{result['verdict']}")
    if result.get("nextAction"):
        print(f"下一步：{result['nextAction']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--reference', required=True, help='基准截图（页面级 reference/reference.png）')
    ap.add_argument('--actual', required=True, help='本次 run 的目标 App 原始截图')
    ap.add_argument('--page-facts', required=True, help='页面级 reference/page-facts.json')
    ap.add_argument('--runtime-device', help='本次 run 的 runtime-device.json')
    ap.add_argument('--transform', help='canvas-transform.json 或含 canvasTransform 的 JSON')
    ap.add_argument('--canvas', help='Lanhu 画布尺寸 WxH；不给则取 page-facts 的 viewport')
    ap.add_argument('--policy', default='fit', choices=('fit', 'fill', 'custom'))
    ap.add_argument('--reason', help='policy=fill 时的理由')
    ap.add_argument('--output', required=True, help='写入对齐审计 JSON')
    ap.add_argument('--radius', type=float, default=DEFAULT_RADIUS_PT,
                    help=f'元素级模板搜索半径（设备点，默认 {DEFAULT_RADIUS_PT}）')
    ap.add_argument('--band-radius', type=float, default=DEFAULT_BAND_RADIUS_PT,
                    help=f'带级搜索半径（设备点，默认 {DEFAULT_BAND_RADIUS_PT}）：'
                         '整页累积漂移可能远超元素级半径')
    ap.add_argument('--band-height', type=float, default=40.0,
                    help='带级模板高度上限（设备点，默认 40）：太高会吃进漂移')
    ap.add_argument('--context', type=float, default=4.0,
                    help='元素模板的上下文边距（设备点，默认 4.0）：小文本模板在整页里'
                         '往往不唯一，带上周边结构才能唯一确定位置')
    ap.add_argument('--peak-ratio', type=float, default=DEFAULT_PEAK_RATIO,
                    help=f'最优峰/次优峰最小比值（默认 {DEFAULT_PEAK_RATIO}），低于此判为匹配歧义')
    ap.add_argument('--position-tolerance', type=float, default=DEFAULT_POSITION_TOLERANCE_PT,
                    help=f'位置容差（设备点，默认 {DEFAULT_POSITION_TOLERANCE_PT}）')
    ap.add_argument('--scale-tolerance', type=float, default=DEFAULT_SCALE_TOLERANCE,
                    help=f'比例容差（相对值，默认 {DEFAULT_SCALE_TOLERANCE}）')
    ap.add_argument('--max-regions', type=int, default=18, help='最多审计多少个元素（默认 18）')
    ap.add_argument('--ink-threshold', type=int, default=DEFAULT_INK_THRESHOLD,
                    help=f'边缘强度达到多少算墨迹，0-255（默认 {DEFAULT_INK_THRESHOLD}）')
    ap.add_argument('--ink-own-min', type=float, default=DEFAULT_INK_OWN_MIN,
                    help=f'框内墨迹占搜索窗墨迹的最低比例，低于此判为邻居污染（默认 {DEFAULT_INK_OWN_MIN}）')
    ap.add_argument('--ink-coverage-min', type=float, default=DEFAULT_INK_COVERAGE_MIN,
                    help=f'预测框内墨迹覆盖度下限，低于此视为图上这里没内容（默认 {DEFAULT_INK_COVERAGE_MIN}）')
    ap.add_argument('--ink-missing-ratio', type=float, default=DEFAULT_INK_MISSING_RATIO,
                    help=f'多少比例的元素该有内容却没有即判基准不可信（默认 {DEFAULT_INK_MISSING_RATIO}）')
    ap.add_argument('--dom-tolerance', type=float, default=DEFAULT_DOM_TOLERANCE_PT,
                    help=f'基准图墨迹相对 DOM 预测框的允许偏移，单位 pt（默认 {DEFAULT_DOM_TOLERANCE_PT}）')
    ap.add_argument('--bands', type=int, default=6, help='分成几个带（默认 6）')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    result, code = audit(args)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    if not args.quiet:
        print_summary(result)
    return code


if __name__ == '__main__':
    sys.exit(main())
