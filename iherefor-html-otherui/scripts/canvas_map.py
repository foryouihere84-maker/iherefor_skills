#!/usr/bin/env python3
"""统一的画布坐标映射：Lanhu 画布 ↔ 目标设备点 ↔ 截图像素。

**这个模块是唯一允许做坐标换算的地方。** 分析代码（区域 diff、对齐审计、确定性
证据生成）必须 import 它，禁止自行写 ``x * scaleY`` 这类换算——历史上每多写一次
手算，就多一次「多乘一层 scale」的系统性偏移，而这类错误在整页 diff 数值上看不出
来，只能靠人肉对 bbox 才能发现。

三套坐标系（契约见 ``references/artifact-contract.md``）：

    lanhu      Lanhu 画布坐标（HTML viewport 的 CSS px，例如 393x852）
    device     目标设备点（iOS pt / Android dp，例如 402x874）
    pixels     截图像素（例如 1206x2622 = device x screenshotScale）

正向（lanhu -> device，``SKILL.md`` 已有的公式）：

    targetX = (lanhuX - letterbox.x) * scaleX + origin.x
    targetY = (lanhuY - letterbox.y) * scaleY + origin.y

逆向（device -> lanhu）就是同一组参数的代数反解，**不再是另一套约定**：

    lanhuX = (targetX - origin.x) / scaleX + letterbox.x
    lanhuY = (targetY - origin.y) / scaleY + letterbox.y

压缩策略默认 ``fit``：等比缩放并居中，``scaleX == scaleY == min(wRatio, hRatio)``。
``fill``（非等比拉伸）会把纵向/横向单独放大，使元素的**尺寸**与画布不一致；历史上
393x852 -> 402x874 时 fit=1.0229 / fill=1.0258 没有任何文档裁定，两处都「记录」了
策略却没有测试，于是 Agent 只能自己选，选完也没有任何机制发现选错。现在默认值是
可执行的、有回归测试的。

用法（命令行）：

    # 打印某个画布变换的正向与逆向结果
    python3 scripts/canvas_map.py --transform canvas-transform.json \\
        --forward 0,495,393,48 --box-to pixels

    # 取实现侧该用的比例形式（组件之间的布局关系必须用比例，不用绝对值）
    python3 scripts/canvas_map.py --runtime-device runtime-device.json --canvas 393x852 \\
        --forward 16,722,360,68 --box-to ratios

    # 自检（不依赖任何输入文件）
    python3 scripts/canvas_map.py --self-test

比例与绝对值的关系：``to_device`` 给的是**探针设备**上的绝对值，写进原生约束就把布局
钉死在这一台设备上；``to_ratios`` 给的是比例，在任何容器里都成立。二者在纵横比相同的
设备上等价，纵横比不同时只有比例是对的 —— ``axis_deviation()`` 量化这个差，并给出
「实现与审计能否沿用同一个模型」的结论。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

POLICIES = ("fit", "fill", "custom")

# 默认容差：位置按目标设备点计，比例按相对值计。
DEFAULT_POSITION_TOLERANCE_PT = 2.0
DEFAULT_SCALE_TOLERANCE = 0.002


class CanvasMapError(ValueError):
    """画布变换参数非法。"""


@dataclass(frozen=True)
class Box:
    """一个矩形。一律用 ``x, y, width, height``，不做 ltrb 与 wh 的隐式混用。"""

    x: float
    y: float
    width: float
    height: float

    def as_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def scaled(self, factor: float) -> "Box":
        return Box(self.x * factor, self.y * factor, self.width * factor, self.height * factor)

    def rounded(self, digits: int = 3) -> "Box":
        return Box(round(self.x, digits), round(self.y, digits),
                   round(self.width, digits), round(self.height, digits))


def box_from(value) -> Box:
    """接受 dict / 四元序列 / 已是 Box 的输入，统一成 Box。

    四元序列按 ``(x, y, width, height)`` 解释——与 ``Box`` 字段顺序一致。
    需要 ltrb 语义时请显式写 dict，或调用 ``box_from_ltrb``。
    """
    if isinstance(value, Box):
        return value
    if isinstance(value, dict):
        missing = [k for k in ("x", "y", "width", "height") if k not in value]
        if missing:
            raise CanvasMapError(f"box dict 缺少字段：{missing}")
        return Box(float(value["x"]), float(value["y"]),
                   float(value["width"]), float(value["height"]))
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return Box(*(float(v) for v in value))
    raise CanvasMapError(f"无法解析为 box：{value!r}")


def box_from_ltrb(left, top, right, bottom) -> Box:
    return Box(float(left), float(top), float(right) - float(left), float(bottom) - float(top))


class CanvasTransform:
    """一组画布变换参数，正向与逆向同时可用。

    构造后 ``scaleX/scaleY/origin/letterbox`` 即为最终值；``policy`` 只记录来源，
    不影响运算。校验规则：

    * ``fit``：必须等比，且 origin 必须等于居中所产生的偏移；
    * ``fill``：允许非等比，但必须给出 ``reason``；
    * ``custom``：必须显式给出 ``scaleX``/``scaleY``，不推导。
    """

    def __init__(self, canvas_width, canvas_height, device_width, device_height,
                 policy="fit", scale_x=None, scale_y=None, origin=None,
                 letterbox=None, reason=None, screenshot_scale=1):
        if canvas_width <= 0 or canvas_height <= 0:
            raise CanvasMapError("lanhu 画布尺寸必须为正")
        if device_width <= 0 or device_height <= 0:
            raise CanvasMapError("设备尺寸必须为正")
        if policy not in POLICIES:
            raise CanvasMapError(f"未知 policy：{policy!r}，可选 {POLICIES}")
        if screenshot_scale <= 0:
            raise CanvasMapError("screenshotScale 必须为正")

        self.canvas_width = float(canvas_width)
        self.canvas_height = float(canvas_height)
        self.device_width = float(device_width)
        self.device_height = float(device_height)
        self.policy = policy
        self.screenshot_scale = float(screenshot_scale)
        self.reason = reason

        ratio_x = self.device_width / self.canvas_width
        ratio_y = self.device_height / self.canvas_height

        if policy == "fit":
            uniform = min(ratio_x, ratio_y)
            scale_x = scale_y = uniform
            default_origin = ((self.device_width - self.canvas_width * uniform) / 2.0,
                              (self.device_height - self.canvas_height * uniform) / 2.0)
        elif policy == "fill":
            if not reason:
                raise CanvasMapError("policy=fill 必须给出 reason：非等比拉伸会改变元素尺寸")
            scale_x, scale_y = ratio_x, ratio_y
            default_origin = (0.0, 0.0)
        else:  # custom
            if scale_x is None or scale_y is None:
                raise CanvasMapError("policy=custom 必须显式给出 scaleX 与 scaleY")
            default_origin = (0.0, 0.0)

        self.scale_x = float(scale_x)
        self.scale_y = float(scale_y)
        if self.scale_x <= 0 or self.scale_y <= 0:
            raise CanvasMapError("scaleX/scaleY 必须为正")

        self.origin = (tuple(float(v) for v in origin) if origin
                       else (float(default_origin[0]), float(default_origin[1])))
        self.letterbox = (tuple(float(v) for v in letterbox) if letterbox else (0.0, 0.0))

        self.uniform = math.isclose(self.scale_x, self.scale_y, rel_tol=1e-9)

    # ---- 派生量 ----

    @property
    def ratio_x(self) -> float:
        return self.device_width / self.canvas_width

    @property
    def ratio_y(self) -> float:
        return self.device_height / self.canvas_height

    @property
    def content_box(self) -> Box:
        """画布内容在 device 坐标系里的实际占位。"""
        return Box(self.origin[0], self.origin[1],
                   self.canvas_width * self.scale_x, self.canvas_height * self.scale_y)

    @property
    def padding(self) -> dict:
        """等比居中后四边留下的空白（device 点）。

        ``fit`` 且居中时，短边两侧各有 (device - canvas*scale)/2 的空白；数值为 0
        表示该边没有留白。判读留白问题（图片一侧留白、组件断裂）时读这里，不要
        再自己拿设备尺寸减画布尺寸。"""
        content = self.content_box
        return {
            "left": round(content.x, 4),
            "top": round(content.y, 4),
            "right": round(self.device_width - content.right, 4),
            "bottom": round(self.device_height - content.bottom, 4),
            "max": round(max(content.x, content.y,
                             self.device_width - content.right,
                             self.device_height - content.bottom), 4),
        }

    @property
    def pixels(self) -> dict:
        return {"width": round(self.device_width * self.screenshot_scale),
                "height": round(self.device_height * self.screenshot_scale)}

    # ---- 正向：lanhu -> device ----

    def to_device(self, box) -> Box:
        src = box_from(box)
        return Box((src.x - self.letterbox[0]) * self.scale_x + self.origin[0],
                   (src.y - self.letterbox[1]) * self.scale_y + self.origin[1],
                   src.width * self.scale_x,
                   src.height * self.scale_y)

    # ---- 逆向：device -> lanhu ----

    def to_lanhu(self, box) -> Box:
        src = box_from(box)
        return Box((src.x - self.origin[0]) / self.scale_x + self.letterbox[0],
                   (src.y - self.origin[1]) / self.scale_y + self.letterbox[1],
                   src.width / self.scale_x,
                   src.height / self.scale_y)

    # ---- 正向/逆向：pixels <-> lanhu ----

    def to_pixels(self, box, source="lanhu") -> Box:
        """把 lanhu 或 device 坐标换算成截图像素坐标。"""
        device = self.to_device(box) if source == "lanhu" else box_from(box)
        return device.scaled(self.screenshot_scale)

    def from_pixels(self, box, target="lanhu") -> Box:
        """把截图像素坐标换算回 device 点或 lanhu 坐标。"""
        device = box_from(box).scaled(1.0 / self.screenshot_scale)
        return self.to_lanhu(device) if target == "lanhu" else device

    # ---- 比例：实现侧的表达方式 ----
    #
    # to_device 给出的是**探针设备**上的绝对值。把它写进原生约束，就等于把布局钉死在
    # 这一台设备上：换台设备这个数字就是错的，而它看起来「算过、有出处」，比一眼可疑的
    # 魔数更难发现。组件之间的布局关系一律用 to_ratios 的比例形式表达。

    def to_ratios(self, box) -> dict:
        """lanhu box -> 相对画布的比例。**实现侧用这个，不要用 to_device 的绝对值。**"""
        src = box_from(box)
        return {
            "xRatio": round(src.x / self.canvas_width, 6),
            "yRatio": round(src.y / self.canvas_height, 6),
            "widthRatio": round(src.width / self.canvas_width, 6),
            "heightRatio": round(src.height / self.canvas_height, 6),
            "centerXRatio": round((src.x + src.width / 2) / self.canvas_width, 6),
            "centerYRatio": round((src.y + src.height / 2) / self.canvas_height, 6),
            "rightRatio": round(src.right / self.canvas_width, 6),
            "bottomRatio": round(src.bottom / self.canvas_height, 6),
        }

    def from_ratios(self, ratios, container_width=None, container_height=None) -> Box:
        """比例 -> 任意容器内的坐标。容器尺寸缺省时用设备尺寸。

        有 ``xRatio`` / ``yRatio`` 时按边缘定位；只有 ``centerXRatio`` / ``centerYRatio``
        时按中心定位 —— 居中元素用中心比例表达比用左边缘比例更稳，左边缘会随宽度变化漂移。
        """
        width = float(self.device_width if container_width is None else container_width)
        height = float(self.device_height if container_height is None else container_height)
        box_width = float(ratios.get("widthRatio", 0.0)) * width
        box_height = float(ratios.get("heightRatio", 0.0)) * height
        if "xRatio" in ratios:
            x = float(ratios["xRatio"]) * width
        elif "centerXRatio" in ratios:
            x = float(ratios["centerXRatio"]) * width - box_width / 2
        else:
            raise CanvasMapError("比例缺少 xRatio 或 centerXRatio")
        if "yRatio" in ratios:
            y = float(ratios["yRatio"]) * height
        elif "centerYRatio" in ratios:
            y = float(ratios["centerYRatio"]) * height - box_height / 2
        else:
            raise CanvasMapError("比例缺少 yRatio 或 centerYRatio")
        return Box(x, y, box_width, box_height)

    def _axis_deviation(self, axis: str) -> float:
        """该轴上「本变换的映射」与「纯比例映射」的最大偏差（device 点）。

        两个映射都是直线：在画布中段相交、向两端分岔，所以最大值必落在画布两端 ——
        起点差为 origin，终点差为 device - (canvas * scale + origin)。

        ``fill``（origin 为 0、scale 取各轴比值）**就是**纯比例映射，因此这个值为 0。
        """
        if axis == "x":
            canvas, device = self.canvas_width, self.device_width
            scale, origin = self.scale_x, self.origin[0]
        else:
            canvas, device = self.canvas_height, self.device_height
            scale, origin = self.scale_y, self.origin[1]
        return max(abs(origin), abs(device - (canvas * scale + origin)))

    def axis_deviation(self) -> dict:
        """本变换与纯比例映射的最大偏差，以及二者能否互换。

        `fit` 会等比缩放置中并留下 letterbox，比例映射则逐轴铺满，两者因此不等价。
        偏差超过位置容差时，**实现必须用比例模型，而审计也必须用比例模型预测** ——
        否则就是拿 `fit` 的预测框去量一个按比例布局的界面，把模型差报成实现错误。
        """
        horizontal = self._axis_deviation("x")
        vertical = self._axis_deviation("y")
        worst = max(horizontal, vertical)
        interchangeable = worst <= DEFAULT_POSITION_TOLERANCE_PT
        return {
            "horizontalPt": round(horizontal, 4),
            "verticalPt": round(vertical, 4),
            "maxPt": round(worst, 4),
            "positionTolerancePt": DEFAULT_POSITION_TOLERANCE_PT,
            "interchangeable": interchangeable,
            "note": ("本变换与纯比例映射在位置容差内等价，审计可用本变换的预测框"
                     if interchangeable else
                     "二者不可互换：实现改用比例模型时，对齐审计也必须改用比例模型预测"),
        }

    # ---- 校验 ----

    def scale_ratio(self, measured_scale_y: float) -> float:
        """实测纵向比例相对契约比例的偏差（0.003 = 差 0.3%）。"""
        if self.scale_y == 0:
            raise CanvasMapError("scaleY 为 0")
        return measured_scale_y / self.scale_y - 1.0

    def as_dict(self) -> dict:
        return {
            "canvasSize": {"width": self.canvas_width, "height": self.canvas_height},
            "deviceSize": {"width": self.device_width, "height": self.device_height},
            "screenshotScale": self.screenshot_scale,
            "screenshotPixels": self.pixels,
            "policy": self.policy,
            "reason": self.reason,
            "uniformScale": self.uniform,
            "ratioX": round(self.ratio_x, 8),
            "ratioY": round(self.ratio_y, 8),
            "scaleX": round(self.scale_x, 8),
            "scaleY": round(self.scale_y, 8),
            "origin": {"x": self.origin[0], "y": self.origin[1]},
            "letterbox": {"x": self.letterbox[0], "y": self.letterbox[1]},
            "contentBox": self.content_box.rounded().as_dict(),
            "padding": self.padding,
            "axisDeviation": self.axis_deviation(),
            "coordinateMapper": {
                "forward": {"x": "(lanhuX - letterbox.x) * scaleX + origin.x",
                            "y": "(lanhuY - letterbox.y) * scaleY + origin.y",
                            "width": "lanhuWidth * scaleX",
                            "height": "lanhuHeight * scaleY"},
                "inverse": {"x": "(deviceX - origin.x) / scaleX + letterbox.x",
                            "y": "(deviceY - origin.y) / scaleY + letterbox.y",
                            "width": "deviceWidth / scaleX",
                            "height": "deviceHeight / scaleY"},
            },
        }


def transform_from_runtime_device(runtime_device: dict, canvas_width: float, canvas_height: float,
                                 policy: str = "fit", reason: str | None = None) -> CanvasTransform:
    """从 ``runtime-device.json`` 构造变换。设备尺寸一律取自运行时 API 返回值。"""
    points = runtime_device.get("screenBoundsPoints") or {}
    if not points.get("width") or not points.get("height"):
        raise CanvasMapError("runtime-device 缺少 screenBoundsPoints")
    scale = runtime_device.get("screenshotScale")
    if scale is None:
        pixels = runtime_device.get("screenshotPixels") or {}
        if pixels.get("width") and points.get("width"):
            scale = pixels["width"] / points["width"]
        else:
            raise CanvasMapError("runtime-device 缺少 screenshotScale，且无法由 screenshotPixels 推导")
    return CanvasTransform(canvas_width, canvas_height, points["width"], points["height"],
                           policy=policy, reason=reason, screenshot_scale=float(scale))


def transform_from_canvas_transform(payload: dict, screenshot_scale=None) -> CanvasTransform:
    """从实现计划里的 ``canvasTransform`` 构造变换。

    ``screenshot_scale`` 只在 payload 没写该字段时兜底（旧产物把 scale 放在
    ``runtime-device.json`` 里）。落盘产物应以 payload 为准，兜底值必须来自运行时 API。
    """
    canvas = payload.get("referenceCanvas") or payload.get("canvasSize") or {}
    device = payload.get("targetWindow") or payload.get("deviceSize") or {}
    if not canvas.get("width") or not device.get("width"):
        raise CanvasMapError("canvasTransform 缺少 referenceCanvas 或 targetWindow")
    scale_x = payload.get("scaleX")
    scale_y = payload.get("scaleY")
    policy = payload.get("policy")
    reason = payload.get("reason")
    if policy is None:
        # 旧写法把策略描述放在 fit 字段里。等比 -> fit；非等比 -> custom，并把原文
        # 当作 reason 带出来，而不是悄悄按 fit 放行。
        uniform = (scale_x and scale_y and math.isclose(scale_x, scale_y, rel_tol=1e-9))
        policy = "fit" if uniform else "custom"
        if not uniform and isinstance(payload.get("fit"), str):
            reason = reason or f"legacy fit 字段：{payload['fit']}"
    origin = payload.get("origin")
    if isinstance(origin, dict):
        origin = (origin.get("x", 0.0), origin.get("y", 0.0))
    letterbox = payload.get("letterbox")
    if isinstance(letterbox, dict):
        letterbox = (letterbox.get("x", 0.0), letterbox.get("y", 0.0))
    resolved_scale = payload.get("screenshotScale", screenshot_scale)
    if resolved_scale is None:
        raise CanvasMapError("canvasTransform 缺少 screenshotScale，且未提供兜底值")
    return CanvasTransform(canvas["width"], canvas["height"], device["width"], device["height"],
                           policy=policy, scale_x=scale_x, scale_y=scale_y, origin=origin,
                           letterbox=letterbox, reason=reason,
                           screenshot_scale=float(resolved_scale))


def bbox_of(items, key: str = "box") -> Box | None:
    """合并若干元素的外接矩形，用于把多个 view 归成同一视觉区域。"""
    boxes = [box_from(item[key] if isinstance(item, dict) and key in item else item)
             for item in items]
    if not boxes:
        return None
    left = min(b.x for b in boxes)
    top = min(b.y for b in boxes)
    right = max(b.right for b in boxes)
    bottom = max(b.bottom for b in boxes)
    return box_from_ltrb(left, top, right, bottom)


def region_diff(transform: CanvasTransform, lanhu_box, measured_device_box) -> dict:
    """预测框 vs 实测框的逐项差：位置偏移（device 点）+ 比例偏差。

    ``measured_device_box`` 必须是**实测到的** device 点坐标。若手上只有截图像素
    实测值，先用 ``transform.from_pixels(..., target='device')`` 换算，不要手算除以 scale。
    """
    predicted = transform.to_device(lanhu_box)
    measured = box_from(measured_device_box)
    dx = measured.x - predicted.x
    dy = measured.y - predicted.y
    ratio_x = measured.width / predicted.width if predicted.width else float("inf")
    ratio_y = measured.height / predicted.height if predicted.height else float("inf")
    return {
        "predicted": predicted.rounded().as_dict(),
        "measured": measured.rounded().as_dict(),
        "dx": round(dx, 3),
        "dy": round(dy, 3),
        "scaleRatioX": round(ratio_x, 6),
        "scaleRatioY": round(ratio_y, 6),
        "withinTolerance": (abs(dx) <= DEFAULT_POSITION_TOLERANCE_PT
                            and abs(dy) <= DEFAULT_POSITION_TOLERANCE_PT
                            and abs(ratio_x - 1) <= DEFAULT_SCALE_TOLERANCE
                            and abs(ratio_y - 1) <= DEFAULT_SCALE_TOLERANCE),
    }


# --------------------------------------------------------------------------
# 自检：把「正向 -> 逆向 -> 正向」的恒等性、fit 的等比性、fit/fill 的差异固定下来。
# --------------------------------------------------------------------------

def self_test() -> int:
    problems = []

    def check(condition, message):
        if not condition:
            problems.append(message)

    # 1. 等比：393x852 画布 -> 402x874 设备，fit 与 fill 必须给出不同但是可预测的值。
    fit = CanvasTransform(393, 852, 402, 874, policy="fit", screenshot_scale=3)
    check(math.isclose(fit.scale_x, 402 / 393), f"fit 的 scaleX 应为宽比 {402/393}")
    check(math.isclose(fit.scale_y, fit.scale_x), "fit 必须等比：scaleX == scaleY")
    check(math.isclose(fit.scale_x, 1.0229007633587786), f"fit 统一 scale 应为 1.02290…，得到 {fit.scale_x}")
    fill = CanvasTransform(393, 852, 402, 874, policy="fill", reason="demo", screenshot_scale=3)
    check(math.isclose(fill.scale_y, 874 / 852), "fill 的 scaleY 应为高比")
    check(not fill.uniform, "fill 不应被判为等比")
    check(abs(fill.scale_y - fit.scale_y) > 0.002,
          "这个画布/设备组合下 fit 与 fill 的纵向比例差必须可被观测到")
    check(math.isclose(fit.scale_y, 1.0229007633587786) and fit.padding["bottom"] > 0,
          "fit 等比后底部应留下与画布高度差对应的空白")

    # 2. 正向 -> 逆向 必须恒等（这是「分析代码不许手写换算」的依据）。
    for box in [(0, 0, 393, 852), (0, 495, 393, 48), (16.5, 722.25, 360, 68)]:
        rt = fit.to_lanhu(fit.to_device(box))
        for name, got, want in zip(("x", "y", "w", "h"),
                                   (rt.x, rt.y, rt.width, rt.height),
                                   box):
            check(math.isclose(got, want, abs_tol=1e-9),
                  f"正向+逆向不恒等：box={box} 的 {name} 得到 {got}，应为 {want}")

    # 3. 像素往返：pixels -> lanhu 与 lanhu -> pixels 也必须恒等。
    probe = (0, 495, 393, 48)
    px = fit.to_pixels(probe, source="lanhu")
    back = fit.from_pixels(px, target="lanhu")
    check(math.isclose(back.x, probe[0], abs_tol=1e-9), "像素往返 x 不恒等")
    check(math.isclose(back.height, probe[3], abs_tol=1e-9), "像素往返 height 不恒等")
    check(math.isclose(px.width, probe[2] * fit.scale_x * 3, abs_tol=1e-6),
          "pixels 换算必须同时含 scale 与 screenshotScale（历史上多乘/漏乘就在这里）")
    check(px.width < probe[2] * fit.ratio_y * 3,
          "fit 的横向像素宽度必须小于按高比拉伸的结果——这就是 fill 会引入的尺寸放大")
    check(fit.from_pixels(fit.to_pixels((0, 0, 10, 10))).width - 10 < 1e-9,
          "像素往返 width 不恒等")

    # 4. fill 必须要求 reason；custom 必须显式给 scale。
    for kwargs, label in ((dict(policy="fill"), "fill 缺少 reason"),
                          (dict(policy="custom"), "custom 缺少 scaleX/scaleY")):
        try:
            CanvasTransform(393, 852, 402, 874, **kwargs)
        except CanvasMapError:
            pass
        else:
            problems.append(f"{label} 未被拒绝")

    # 5. fit 的居中：四边留白必须与剩余空间一致，且顺带把「有没有留白」变成可观测量。
    pad = fit.padding
    # padding 输出按 4 位小数取整，断言容差跟着取 1e-3，不要把取整当成几何误差。
    check(abs(pad["bottom"] - (874 - 852 * fit.scale_y) / 2) < 1e-3,
          f"fit 的纵向留白应为剩余空间的一半（居中）：{pad}")
    check(pad["left"] == 0 and pad["right"] == 0,
          f"393x852 -> 402x874 是宽度受限，fit 时左右不应有留白：{pad}")
    check(abs(fit.content_box.height - 852 * fit.scale_y) < 1e-6,
          "contentBox 高度应等于画布高度乘统一 scale")
    check(abs(fit.content_box.width - 402) < 1e-6,
          "宽度受限时 contentBox 应恰好铺满设备宽度")

    # 6. region_diff 的容差判定：刚好压线必须算通过，超一点必须算失败。
    t = CanvasTransform(100, 100, 100, 100, policy="fit")
    ok = region_diff(t, (0, 50, 100, 10), (1.9, 51.9, 100, 10))
    check(ok["withinTolerance"], f"2pt 容差内的偏移应判通过：{ok}")
    bad = region_diff(t, (0, 50, 100, 10), (0, 50, 110, 10))
    check(not bad["withinTolerance"], f"10% 尺寸差应判失败：{bad}")

    # 7. 比例往返：比例形式必须与画布坐标一一对应，且与容器尺寸无关。
    # 比例按 6 位小数落盘，重建误差上界 = 画布边长 * 5e-7（852 上约 4.3e-4 pt），
    # 远小于任何有意义的布局容差；断言就按这个上界写，不要假装它是精确恒等。
    ratio_roundtrip_tol = max(fit.canvas_width, fit.canvas_height) * 5e-7
    for box in [(0, 0, 393, 852), (16.5, 722.25, 360, 68), (40, 620, 706, 380)]:
        ratios = fit.to_ratios(box)
        back = fit.from_ratios(ratios, fit.canvas_width, fit.canvas_height)
        for name, got, want in zip(("x", "y", "w", "h"),
                                   (back.x, back.y, back.width, back.height), box):
            check(abs(got - want) <= ratio_roundtrip_tol,
                  f"比例往返误差超过 6 位小数上界：box={box} 的 {name} 得到 {got}，应为 {want}")
    # 同一个比例在别的容器里必须等比缩放 —— 这正是「不用固定 pt」要买到的东西。
    ratios = fit.to_ratios((39.3, 42.6, 196.5, 85.2))
    wide = fit.from_ratios(ratios, 786, 1704)
    check(math.isclose(wide.width, 393.0, abs_tol=1e-6),
          f"容器加倍时比例宽度应加倍：{wide}")
    check(math.isclose(wide.x, 78.6, abs_tol=1e-6), f"比例 x 应随容器缩放：{wide}")
    # 中心比例对居中元素必须稳定：容器宽度变化时中心不动。
    centered = fit.to_ratios((96.5, 100, 200, 40))
    c1 = fit.from_ratios(centered, 1000, 1000)
    check(math.isclose(c1.x + c1.width / 2, 0.5 * 1000, abs_tol=1e-6),
          f"居中元素的中心比例应落在容器中心：{c1}")

    # 8. 比例模型与 fit 的偏差必须等于 letterbox，且据此给出「能否互换」的结论。
    dev = fit.axis_deviation()
    check(math.isclose(dev["verticalPt"], fit.padding["max"], abs_tol=1e-3),
          f"纵向偏差应等于 letterbox 厚度 {fit.padding['max']}，得到 {dev['verticalPt']}")
    check(dev["horizontalPt"] == 0,
          f"宽度受限时横向不应有偏差（fit 的 scaleX 恰为宽比）：{dev}")
    # 393x852 -> 402x874 的偏差 1.2443pt < 2pt 容差，所以这一对设备上两种模型可互换。
    check(dev["interchangeable"] and dev["maxPt"] < DEFAULT_POSITION_TOLERANCE_PT,
          f"该设备对的 fit 与比例模型偏差应在容差内：{dev}")
    # fill 的映射就是纯比例映射，偏差必须为 0 —— 这是「比例契约等价于 fill+无留白」的断言。
    fill_dev = fill.axis_deviation()
    check(fill_dev["maxPt"] == 0 and fill_dev["interchangeable"],
          f"fill 逐轴铺满即纯比例映射，偏差必须为 0：{fill_dev}")
    # 纵横比差异大的设备上必须判为不可互换，否则会把模型差报成实现错误。
    tall = CanvasTransform(393, 852, 393, 1704, policy="fit")
    tall_dev = tall.axis_deviation()
    check(not tall_dev["interchangeable"] and tall_dev["maxPt"] > 100,
          f"纵横比差异大时 fit 与比例模型必须判为不可互换：{tall_dev}")

    for problem in problems:
        print(problem)
    if problems:
        print("canvas_map 自检失败")
        return 1
    print("canvas_map 自检通过：等比默认、正逆恒等、像素往返、policy 校验、容差判定、比例往返与偏差")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transform", help="canvas-transform.json 或含 canvasTransform 的 JSON")
    ap.add_argument("--runtime-device", help="runtime-device.json（与 --transform 二选一）")
    ap.add_argument("--canvas", help="Lanhu 画布尺寸 WxH，配合 --runtime-device")
    ap.add_argument("--policy", default="fit", choices=POLICIES)
    ap.add_argument("--reason", help="policy=fill 时的理由")
    ap.add_argument("--self-test", action="store_true")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--box-to", choices=("device", "pixels", "lanhu", "ratios"),
                       help="对输入 box 做正向/逆向换算；ratios 给实现侧该用的比例形式")
    group.add_argument("--box-from-pixels", choices=("device", "lanhu"),
                       help="把输入 box 当作截图像素，换算回 device 或 lanhu")
    ap.add_argument("--forward", "--box", dest="box",
                    help="box 输入，dict JSON 或 x,y,width,height")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if args.transform:
        payload = json.loads(Path(args.transform).read_text())
        payload = payload.get("canvasTransform", payload)
        transform = transform_from_canvas_transform(payload)
    elif args.runtime_device:
        if not args.canvas:
            ap.error("--runtime-device 需要同时给出 --canvas WxH")
        width, _, height = args.canvas.partition("x")
        transform = transform_from_runtime_device(
            json.loads(Path(args.runtime_device).read_text()),
            float(width), float(height), policy=args.policy, reason=args.reason)
    else:
        ap.error("需要 --transform 或 --runtime-device，或使用 --self-test")

    result = {"canvasTransform": transform.as_dict()}
    if args.box:
        raw = args.box.strip()
        box = (json.loads(raw) if raw.startswith("{")
               else [float(v) for v in raw.split(",")])
        if args.box_from_pixels:
            target = args.box_from_pixels
            result["result"] = transform.from_pixels(box, target=target).rounded().as_dict()
            result["resultTarget"] = target
        else:
            target = args.box_to or "device"
            if target == "ratios":
                # 实现侧该用的形式。同时给出「本设备上的绝对值」，方便直接看出
                # 那个绝对值为什么不能写进代码。
                result["ratios"] = transform.to_ratios(box)
                result["absoluteOnThisDevice"] = transform.to_device(box).rounded().as_dict()
            else:
                if target == "pixels":
                    out = transform.to_pixels(box, source="lanhu")
                elif target == "device":
                    out = transform.to_device(box)
                else:
                    out = box_from(box)
                result["result"] = out.rounded().as_dict()
            result["resultTarget"] = target

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
