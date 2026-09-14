#!/usr/bin/env python3
"""把事实表里的区域位置转成「尺寸与定位规格」，供原生布局实现使用。

**约束策略不是整页等比缩放，而是两条互相独立的轴**（见
``references/sizing-and-positioning.md``）：

* **尺寸轴** —— 控件尺寸保持设计稿的固定绝对大小，不随屏幕或容器比例缩放。
  分类判据是「这个值由谁闭合」：设计稿给出封闭值的用 ``fixed``；
  由与父视图的约束闭合的用 ``pinned``（贴边、占满、等分，**不带比例系数**）；
  由文字/图片决定的用 ``intrinsic``；确实随容器成比例变化的才用 ``proportional``。
* **位置轴** —— 位置由父子视图层级决定，基准是**直接父视图**，不是页面根。
  父容器为整屏画布时基准才是 ``root``，那是少数情形而非默认。

**为什么比例不能当默认。** 组件之间的布局关系必须能在任意设备上成立，把
``lanhuY = 132`` 换算成 ``132 * 1.0229 = 135.02pt`` 写进约束，就把关系钉死在这一台
设备上 —— 换台设备就是错的，而它「有出处、算过」，比一眼可疑的魔数更难发现。
但「比例」不是唯一的正确形式：设计稿说「按钮左右各 16pt」时，正确的实现是约束闭合，
写成 ``width = parent.width * 0.9186`` 在探针设备上同样对得上，却在 430pt 宽的设备上
给出 13.7pt 边距 —— 设计稿说的是 16。**贴父不等于比例。**

**先说清 ``rect`` 在哪个坐标空间里，这是本脚本最容易出错的地方。** 渲染器是在
**设备视口**上渲染基准图的（HTML 会跟着 reflow），所以 ``rect`` 已经是设备点，
``rectInReference == rect * devicePixelRatio``。这意味着：

* 比例 = ``rect / 父视图尺寸``，**不需要**再过一次 ``canvasTransform``；
* 再过一次就会把 scale 乘两遍 —— 这正是「多乘一层 scale」那类系统性偏移。

本脚本用上面那条恒等式**自动判定** ``rect`` 的坐标空间，判定不出来就拒绝继续，
而不是默默按某个空间算下去。需要按 Lanhu 画布空间算时用 ``--rect-space lanhu`` 显式指定。

**与 `canvas_map.py` 的分工**：坐标换算一律走 `canvas_map`，本脚本不自己写任何
``* scale``；它只负责把位置重新组织成实现侧要的形式。

用法：

    python3 scripts/layout_proportions.py \\
        --page-facts <page>/reference/page-facts.json \\
        --target-mode ios-uikit-objective-c \\
        --output <run>/plans/layout-proportions.json

退出码：0 = 正常；2 = 证据不足（缺事实表，或无法判定坐标空间）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from canvas_map import (  # noqa: E402
    CanvasMapError, box_from, transform_from_canvas_transform,
    transform_from_runtime_device,
)

# 参与比例化的最小边长（视口 CSS px）。太小的元素（分隔线、圆点）没有布局关系可言。
MIN_SIDE_PX = 8.0
DEFAULT_MAX_REGIONS = 24
# rectInReference == rect * dpr 的判定容差（图像像素）。
IDENTITY_TOLERANCE_PX = 1.5
# 低于这个绝对值的「设备推导值」不构成证据：0 永远等于 0，是设备无关的，
# 把它列进禁止清单只会让每个 ``0`` 都报一次警，把真信号淹掉。
MIN_MEANINGFUL_PT = 1.0
# 「≤这个高度 + 有文本」视为文字行/文字块，其高度由字体撑开而非容器比例。
TEXT_BLOCK_MAX_HEIGHT_PT = 48.0

# ---- 尺寸与定位分类的判据（全部是「贴边/居中」的吸附容差与量级阈值）----
#
# 这几个数不是调出来的，是「人写约束时的实际习惯」：设计稿给的内边距很少超过 64pt，
# 超过就不像内边距而像位置；控件（按钮、图标、输入框）的边长很少超过 120pt，
# 超过就属于容器/媒体区。判定错了要有救 —— 所有分类都带 ``kindSource`` 与可读理由，
# 并在拿不准时进 ``reviewHints``，由 Agent 复核而不是默默按某个类别生成约束。
EDGE_SNAP_TOL_PT = 1.5        # 贴边/等距的吸附容差
CENTER_SNAP_TOL_PT = 1.5      # 居中的吸附容差
NEAR_MISS_MAX_PT = 4.0        # 介于吸附容差与这个值之间 ⇒ 提示「接近但未命中」
DESIGN_INSET_MAX_PT = 64.0    # 内边距量级上限，超过就不像内边距
CONTROL_MAX_PT = 120.0        # 控件量级边长上限，超过就不像控件
# 单看一个偏移，32pt 以内像内边距，超过就说不准了（可能是布局位置）。区别这两者
# 需要一个更硬的证据：**同一父下多个兄弟共享同一个偏移值** —— 设计常量之所以是常量，
# 正因为它在多处复用。孤立的大偏移没有这个证据，降级为 proportional 并提示复核，
# 而不是凭「它小于 64」就断言是内边距（那会把布局位置写成约束，同样错）。
DESIGN_INSET_STRICT_PT = 32.0
SHARED_INSET_TOL_PT = 0.5     # 判定「共享同一偏移」的比较容差
# 设计常量都是「整数或半整数」：设计稿写 16、写 37.5，不写 16.3，更不写 53.921875。
# 所以偏移量/尺寸离整数（或半整数）超过这个容差，就说明它是**量出来的**
# （父容器尺寸减内容尺寸），不是设计稿写的。
#
# 这个容差必须很小，否则判据会失效：实测 ``text-group_13`` 宽 53.921875 距整数 54
# 只差 0.078，用 0.08 的容差就会被当成「设计稿写了 54」。小数部分恰好接近 0 的
# 二进制小数（.921875 = 59/64、.015625 = 1/64）在 CSS 布局里很常见，它们全是测量值。
# 留 0.01 是给浮点误差的余量：16pt 的边距在子像素布局下最多算成 16.000001。
INSET_ROUND_TOL_PT = 0.01
# 半整数（37.5pt 这类设计值）也要认。用「两倍之后是否接近整数」判，容差同步放大一倍。
DESIGN_VALUE_DENOMINATORS = (1, 2)


def is_design_value(value: float) -> bool:
    """这个数值像设计稿写的常量吗（整数或半整数）？

    设计常量都是人可以手写的数：4、8、12、16、24、37.5。而测量值带着小数尾巴 ——
    ``53.921875``、``78.015625``、``63.3906``。这些尾巴在 CSS 布局里非常常见：
    文本宽度由字形 advance 累加得来，几乎不可能凑巧落在整数上。

    所以「是整数/半整数」本身就是一条**独立的证据**，用来把「设计稿写死的值」与
    「量出来的值」分开。它不单独决定分类（44pt 的按钮和 44pt 的装饰条都是整数），
    但可以作为否决条件：小数尾巴 ⇒ 一定不是设计常量。
    """
    for denominator in DESIGN_VALUE_DENOMINATORS:
        scaled = value * denominator
        if abs(scaled - round(scaled)) <= INSET_ROUND_TOL_PT * denominator:
            return True
    return False
# 「外框」判定：挂在整屏画布下、且面积占到视口这个比例的元素，就是页面外框本身
# （Lanhu 导出页里的 ``.page``）。实测 393×852 = 视口的 95.3%，而第二大的是 36% ——
# 两者相差很远，所以这个阈值不是在悬崖边上挑数。
OUTER_FRAME_AREA_RATIO = 0.9
# 外框的某一轴占到视口这个比例，就按**铺满**处理，而不是「留了边距」。
# 依据是残留的来源：源页面按画布尺寸写死（实测宽 393、高 852），摆在 402×874 的
# 设备视口上就量出 9pt / 22pt 的空隙。那是**源产物的属性**，不是设计稿的内边距 ——
# 若照测量值写 ``trailing = 9``，实现里就凭空多出一条右边距，而它本来要表达「铺满」。
OUTER_FRAME_SPAN_RATIO = 0.9


def load_json(path):
    """读 JSON；文件不存在、读不了、不是 JSON，一律返回 None。

    这里不抛异常：路径写错属于**用法问题**，要和「坐标系判不出来」一样干净退出
    并给出可读原因，而不是甩一个 traceback —— 那会让调用方分不清是输入错了
    还是脚本坏了。
    """
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def parse_canvas(text: str):
    width, _, height = text.partition("x")
    return float(width), float(height)


def detect_rect_space(page_facts: dict) -> dict:
    """判定 ``rect`` 落在哪个坐标空间。

    渲染器在**设备视口**上渲染基准图，所以 ``rect`` 已经是设备点，且满足
    ``rectInReference == rect * devicePixelRatio``。这条恒等式就是判据：
    成立 ⇒ 设备空间（再过 canvasTransform 就会把 scale 乘两遍）；
    不成立 ⇒ 事实表不是这个渲染器产出的，或被人改过，必须显式指定空间。
    """
    viewport = page_facts.get("viewport") or {}
    dpr = viewport.get("devicePixelRatio")
    scroll_x, scroll_y = viewport.get("scrollX", 0), viewport.get("scrollY", 0)
    if not dpr:
        return {"space": None, "reason": "viewport 缺少 devicePixelRatio"}

    checked = matched = 0
    for element in page_facts.get("elements") or []:
        rect, in_ref = element.get("rect"), element.get("rectInReference")
        if not rect or not in_ref:
            continue
        checked += 1
        expected = {k: (rect[k] + (scroll_x if k == "x" else scroll_y)) * dpr
                    for k in ("x", "y", "width", "height")}
        if all(abs(expected[k] - in_ref[k]) <= IDENTITY_TOLERANCE_PX for k in expected):
            matched += 1

    if not checked:
        return {"space": None, "reason": "没有同时带 rect 与 rectInReference 的元素"}
    if matched == checked:
        return {"space": "device", "checked": checked,
                "reason": "rectInReference == rect * devicePixelRatio 全部成立，rect 是设备点"}
    return {"space": None, "checked": checked, "matched": matched,
            "reason": f"只有 {matched}/{checked} 个元素满足 rectInReference == rect * dpr，"
                      "无法判定 rect 的坐标空间；请用 --rect-space 显式指定"}


def native_idiom(target_mode: str, region: str, relations, parent_name: str) -> list:
    """按目标模式给出该区域的写法（提示，不代替 Agent 的工程判断）。

    ``fixed`` / ``pinned`` / ``intrinsic`` 三类**不带比例系数** —— 它们的正确写法是
    常量或约束，用比例原语反而是错的。这里按类别分派，就是为了让「什么该用比例」
    在生成建议的那一刻就是清楚的。
    """
    lines = []
    for rel in relations:
        kind, axis = rel["kind"], rel.get("axis")
        base = parent_name
        if kind == "fixed":
            if target_mode.startswith("ios-uikit"):
                anchor = {"width": "widthAnchor", "height": "heightAnchor"}.get(axis)
                lines.append(f"[{region}] {anchor}.constraint(equalToConstant: {rel['value']:g})"
                             f"   // {rel['id']} 设计值，不随容器缩放")
            elif target_mode == "ios-swiftui":
                dim = {"width": "width", "height": "height"}.get(axis)
                lines.append(f"[{region}] .frame({dim}: {rel['value']:g})"
                             f"   // {rel['id']} 设计值，不随容器缩放")
            elif target_mode.startswith("android-"):
                prop = {"width": "layout_width", "height": "layout_height"}.get(axis)
                lines.append(f'[{region}] {prop}="{rel["value"]:g}dp"'
                             f"   // {rel['id']} 设计值，不随容器缩放")
        elif kind == "pinned":
            edges = rel.get("edges") or ([rel["edge"]] if rel.get("edge") else [])
            insets = rel.get("insets") or {}
            uniform = rel.get("inset")
            if target_mode.startswith("ios-uikit"):
                for edge in edges:
                    anchor = {"leading": "leadingAnchor", "trailing": "trailingAnchor",
                              "top": "topAnchor", "bottom": "bottomAnchor",
                              "centerX": "centerXAnchor", "centerY": "centerYAnchor"}.get(edge)
                    base_anchor = anchor
                    if edge == "centerX":
                        base_anchor = "centerXAnchor"
                    elif edge == "centerY":
                        base_anchor = "centerYAnchor"
                    # 两侧可以不等距（设计稿左 23、右 32），所以每条边取自己的值，
                    # 不能拿一个「平均内边距」去凑。
                    value = insets.get(edge, uniform if uniform is not None else 0.0)
                    constant = f", constant: {value:g}" if value else ""
                    lines.append(f"[{region}] {anchor}.constraint(equalTo: {base}.{base_anchor}"
                                 f"{constant})   // {rel['id']} 贴边约束，不是比例")
            elif target_mode.startswith("android-"):
                edge_props = {"leading": "layout_constraintStart_toStartOf",
                              "trailing": "layout_constraintEnd_toEndOf",
                              "top": "layout_constraintTop_toTopOf",
                              "bottom": "layout_constraintBottom_toBottomOf",
                              "centerX": "layout_constraintStart_toStartOf",
                              "centerY": "layout_constraintTop_toTopOf"}
                for edge in edges:
                    value = insets.get(edge, uniform if uniform is not None else 0.0)
                    lines.append(f"[{region}] app:{edge_props.get(edge, 'layout_constraintStart_toStartOf')}"
                                 f'="{base}" 边距 {value:g}dp'
                                 f"   // {rel['id']} 贴边约束，不是比例")
            else:
                detail = "、".join(
                    f"{edge} {insets.get(edge, uniform or 0):g}" for edge in edges)
                lines.append(f"[{region}] {rel['id']} = 贴 {base} 的 {detail}"
                             "   // 贴边约束，不是比例")
        elif kind == "intrinsic":
            lines.append(f"[{region}] {rel['id']} 由内容撑开（{rel.get('why', '')[:40]}）"
                         "   // 不加尺寸约束")
        elif kind == "proportional":
            ratio, axis = rel["ratio"], rel["axis"]
            key = f"{region}.{axis}"
            if target_mode.startswith("ios-uikit"):
                if axis in ("width", "height"):
                    anchor = "widthAnchor" if axis == "width" else "heightAnchor"
                    lines.append(f"[{region}] {anchor}.constraint(equalTo: {base}.{anchor}, "
                                 f"multiplier: {ratio})   // {key}")
                else:
                    anchor = "centerYAnchor" if axis == "y" else "centerXAnchor"
                    base_anchor = "heightAnchor" if axis == "y" else "widthAnchor"
                    lines.append(f"[{region}] {anchor}.constraint(equalTo: {base}.{base_anchor}, "
                                 f"multiplier: {ratio})   // {key}")
            elif target_mode == "ios-swiftui":
                lines.append(f"[{region}] .containerRelativeFrame(."
                             f"{'vertical' if axis == 'y' else 'horizontal'}, "
                             f"alignment: .center) {{ length, _ in length * {ratio} }}   // {key}")
            elif target_mode.startswith("android-compose"):
                lines.append(f"[{region}] Modifier.fillMaxWidth({ratio}f) 或 "
                             f"BoxWithConstraints 内 constraints.maxHeight * {ratio}f   // {key}")
            elif target_mode.startswith("android-views"):
                if axis in ("x", "y"):
                    side = "Horizontal" if axis == "x" else "Vertical"
                    lines.append(f'[{region}] app:layout_constraint{side}_bias="{ratio}"   // {key}')
                else:
                    lines.append(f'[{region}] app:layout_constraintDimensionRatio="{ratio}"   // {key}')
            else:
                lines.append(f"[{region}] {key} = {ratio}（按该平台的相对布局原语表达）")
    return lines


def inset_is_design(value: float, shared=()) -> bool:
    """这个偏移量像「设计稿给的固定内边距」吗？（**位置轴**判据）

    三档证据，强度递进：

    * **必须是设计值**（``is_design_value``：整数或半整数）。设计稿写 4/8/12/16/20/24/32，
      不会写 ``63.3906``。实测里 ``text-group_1`` 的右侧残留是 63.3906 ——
      它是「父容器 237 减内容宽度」量出来的，一眼就是测量值而不是设计值。
      小数点是这类残留最省事的指纹：宽度多半由内容决定，而不是设计稿写的数字。
    * ``≤ DESIGN_INSET_STRICT_PT``（32pt）—— 小到不可能是别的意思。手机上一个盒子距父边
      32pt 以内，它就是在贴边，偏移量就是设计稿写的内边距。
    * 更大（至多 ``DESIGN_INSET_MAX_PT`` = 64pt）—— 单看一个值分不出「内边距」与「布局位置」。
      这时要**第二个证据**：同一父视图下多个兄弟共享同一个值。设计常量之所以是常量，
      正因为它在多处复用（实测里 ``group_1``/``group_2``/``group_3``/``text-wrapper_3``
      的左偏移都是 23）。孤立的大偏移没有这个证据，不替人拍板。

    **为什么只用在位置轴。** 位置轴只有一个偏移，才有「内边距 vs 布局位置」这个歧义；
    尺寸轴两侧同时给出偏移时没有第二种解释，判据见 ``insets_close_size``。
    这条分工是踩出来的：把第三档也套到尺寸轴上，等于要求每个贴父边的盒子都有兄弟
    复用同一个内边距，实测会把 ``paragraph_1``（26/44 的段落）从 ``pinned`` 降成
    ``intrinsic`` —— 段落不再随父容器变宽，方向是反的。
    """
    if not (0 <= value <= DESIGN_INSET_MAX_PT):
        return False
    if not is_design_value(value):
        return False
    if value <= DESIGN_INSET_STRICT_PT:
        return True
    return any(abs(value - s) <= SHARED_INSET_TOL_PT for s in shared)


def symmetric_insets_are_design(lead: float, trail: float) -> bool:
    """两侧偏移在容差内等距、都是设计值、且都在内边距量级内 ⇒ 判为设计内边距。

    **对称本身就是第二证据。** 设计稿写「左右各留 38」，量出来就是 38/38
    （实测 38/37，差 1pt 是子像素误差）—— 不需要再找第三个兄弟来证明这个 38
    是设计常量。这与「孤立的单侧 48pt」不是一回事：后者只出现一次，既可能是内边距
    也可能是布局位置，那时才需要兄弟共享旁证，否则不替人拍板。
    """
    return (abs(lead - trail) <= EDGE_SNAP_TOL_PT
            and 0 <= lead <= DESIGN_INSET_MAX_PT
            and 0 <= trail <= DESIGN_INSET_MAX_PT
            and is_design_value(lead) and is_design_value(trail))


def insets_close_size(lead: float, trail: float) -> bool:
    """尺寸轴上，两侧偏移是否**闭合**了这个尺寸（两侧都是设计值、都在内边距量级内）。

    判据比位置轴宽，这不是偷懒，是两个轴的可选答案数量不同：尺寸轴一旦两侧同时给出
    偏移，``width = parent.width - lead - trail`` 就是唯一说得通的形态，没有第二种解释；
    位置轴只有一个偏移，才是真正含糊的地方 —— 那个偏移既可能是内边距也可能是布局位置，
    所以 ``classify_position`` 要求它有兄弟复用（或两侧对称）来旁证。

    实测里 ``paragraph_1``（26/44）正是这条判据的用例：判成 ``pinned``，实现写
    ``leading = parent.leading + 26; trailing = parent.trailing - 44``，父容器变宽时
    段落跟着变宽 —— 这是段落该有的行为。若按位置轴那条更严的判据降级成 ``intrinsic``，
    实现会「不加宽度约束、由文字撑开」，段落就再也不跟着父容器长了。
    """
    return all(0 <= value <= DESIGN_INSET_MAX_PT and is_design_value(value)
               for value in (lead, trail))


def classify_size(lo: float, hi: float, parent_lo: float, parent_hi: float,
                  text_driven: bool, axis: str = "width",
                  outer_frame: bool = False) -> dict:
    """尺寸轴归类：``fixed`` / ``pinned`` / ``intrinsic`` / ``proportional``。

    判据是**这个值由谁闭合**，按证据强度依次判：

    0. **页面外框**（``outer_frame`` 且该轴占满视口）⇒ ``pinned`` 铺满。挂在整屏画布下、
       面积几乎等于视口的那个元素就是页面外框本身。它量出来的小残留往往不是设计边距，
       而是**源产物按画布尺寸写死**的副产物：实测 ``.page`` 是 393×852，摆在 402×874 的
       设备视口上就多出 9pt / 22pt 空隙。照 9 写 ``trailing = 9``，实现里就凭空长出一条
       右边距；而它本来要表达的是「铺满」。
    1. **两侧都贴父边** ⇒ ``pinned``。两条边各自带自己的内边距 —— 设计稿可以左右不等
       （实测 ``group_1..3`` 左 23、右 32），而「左右不等」正是比例化最容易出错的形态：
       写成 ``width = parent.width * 0.863184`` 在探针设备上对得上，换台设备就两边都错。
       判据见 ``insets_close_size``：尺寸轴不需要兄弟共享来旁证（理由写在那里）。
    2. **文字撑开** ⇒ ``intrinsic``。文字块的高度由字体决定；宽度同理 ——
       一个贴合文字的行，宽度是「这段文字恰好有多宽」，不是设计常量更不是比例。
       （实测 ``text_11`` 宽 116、``text-group_13`` 宽 53.9219：后者的小数点本身就说明
       它是量出来的，设计稿不会写 ``53.9219``。）
    3. **边长在控件量级** ⇒ ``fixed``：设计稿给的封闭值，直接写字面量。
    4. 其余 ⇒ ``proportional``，并标记待复核。

    **为什么纵向不照搬横向。** 横向「贴两边」几乎总是设计意图（全宽按钮、卡片留边距）；
    纵向「上下等距」却常常只是**父容器减内容高度的副产品** —— 实测 ``text-group_12``
    高 39、父容器高 68，上下各留 14.5，那不是「内边距 14.5」，而是「卡片 68 装了个 39 的内容」。
    若照 14.5 判 pinned，实现者会写 ``bottom = parent.bottom - 14.5``，父容器一变高，
    文字块高度就跟着变 —— 而它本该由字体撑开。

    所以纵向的判据换成**「它是不是文字撑开的」**：是文字块 ⇒ 纵向偏移是副产品，不判 pinned；
    不是文字块（卡片、容器）⇒ 上下偏移就是设计内边距，照判。这一条比「只在占满时判 pinned」
    准确得多：``上下各留 20pt 的卡片`` 与 ``被内容撑满的卡片`` 终于能分开了。

    ``fixed`` 用阈值兜底：从坐标上，「宽 44 的按钮」与「宽 = 容器 11% 的装饰条」在同一台设备上
    是同一个数，区分它们需要设计意图。所以这里按量级给**提议**，靠 ``kindSource`` 与
    ``reviewHints`` 把判断权交回给 Agent，而不是假装算准了。

    **媒体元素（图片/图标）不单独开口子。** 规范 `references/sizing-and-positioning.md` §2
    明确把「图标 24×24、头像 48×48」列为 ``fixed``（设计值不缩放），同时把「图片 frame」
    列为 ``pinned``（贴父派生）—— 区分这两者的只有**量级**，与「它是不是图片」无关。
    早期版本用「有 src/assets 就不判 fixed」一刀切，正好把设计稿里最典型的固定尺寸
    （图标、头像）判成了待复核的比例，方向是反的。
    """
    size = hi - lo
    lead, trail = lo - parent_lo, parent_hi - hi
    span = parent_hi - parent_lo
    round_value = is_design_value(size)

    if abs(lead) <= EDGE_SNAP_TOL_PT and abs(trail) <= EDGE_SNAP_TOL_PT:
        return {"kind": "pinned", "edges": ["leading", "trailing"],
                "insets": {"leading": 0.0, "trailing": 0.0}, "inset": 0.0,
                "why": "两侧都贴父边（占满）：值由约束闭合，写成比例会随父容器漂移"}
    if outer_frame and span > 0 and size >= span * OUTER_FRAME_SPAN_RATIO:
        return {"kind": "pinned", "edges": ["leading", "trailing"],
                "insets": {"leading": 0.0, "trailing": 0.0}, "inset": 0.0,
                "fullBleed": True,
                "why": f"页面外框，该轴占视口 {size / span * 100:.1f}% ⇒ 按**铺满**处理"
                       "（残留来自源页面按画布尺寸写死，不是设计稿的内边距）"}

    # ---- 两侧贴边：横向总是证据，纵向要看这个盒子是不是「被内容/固定值决定的」----
    #
    # 横向贴两边几乎总是设计意图（全宽按钮、卡片留边距），偏移量就是设计稿写的内边距。
    # 纵向不是：一个 24pt 的图标装在 68pt 的卡片里、上 16 下 28，那个 28 不是设计稿写的，
    # 是 ``68 − 16 − 24`` 算出来的。同样，文字块上下留 14.5 也是 ``68 − 39`` 的副产品。
    # 两类都不认纵向偏移；只有**大尺寸容器**的上下偏移才是真的设计内边距。
    vertical_insets_are_evidence = (not text_driven) and size > CONTROL_MAX_PT
    if axis == "width" or vertical_insets_are_evidence:
        left_ok = right_ok = insets_close_size(lead, trail)
    else:
        left_ok = right_ok = False
    if left_ok and right_ok:
        if abs(lead - trail) <= EDGE_SNAP_TOL_PT:
            # 两侧在容差内等距 ⇒ 设计意图是「左右各留同一个值」，量的差异是子像素误差。
            # 记一个数而不是「38/37」：后者会让实现者以为设计稿真的左右不等。
            mean = round((lead + trail) / 2, 4)
            return {"kind": "pinned", "edges": ["leading", "trailing"],
                    "insets": {"leading": mean, "trailing": mean}, "inset": mean,
                    "why": f"两侧各留 {mean:g}pt 内边距：值由内边距闭合，随父容器伸缩，"
                           "而内边距本身是设计常量"}
        insets = {"leading": round(lead, 4), "trailing": round(trail, 4)}
        return {"kind": "pinned", "edges": ["leading", "trailing"], "insets": insets,
                "why": f"两侧各贴父边、内边距 {lead:g}/{trail:g}pt：值由内边距闭合，"
                       "随父容器伸缩，而内边距本身是设计常量"}

    # ---- 横向：设计值优先于内容撑开 ----
    #
    # 顺序在这里是有讲究的。规范 §6 把「给按钮宽度也用比例」列为反例：按钮是控件，
    # 宽度是设计值。而一个按钮的宽度往往是**整数**（160 / 232 / 116），并且落在控件量级。
    # 反之，真正贴合文字的量出来几乎总是小数（实测 ``text-group_13`` 宽 53.9219）——
    # 字形的 advance width 不会凑巧是整数。所以「整数 + 控件量级」判 ``fixed``。
    #
    # 纵向不套这条：文字块的高度由字号与行高决定，而行高会被浏览器取整，
    # 于是「整数」在纵向证明不了任何事（实测文字块高度 16/27/31/32/39 大多是整数）。
    if axis == "width" and round_value and size <= CONTROL_MAX_PT:
        return {"kind": "fixed", "value": round(size, 4)}
    if text_driven:
        return {"kind": "intrinsic"}
    if size <= CONTROL_MAX_PT:
        return {"kind": "fixed", "value": round(size, 4)}
    if span <= 0:
        return {"kind": "proportional", "ratio": 0.0}
    return {"kind": "proportional", "ratio": round(size / span, 6), "needsReview": True}


def classify_position(lo: float, hi: float, parent_lo: float, parent_hi: float,
                      shared_insets=()) -> dict:
    """位置轴归类：``pinned``（贴边）/ ``centered`` / ``proportional``。

    优先级就是实现侧该有的优先级：**贴边 + 固定间距 > 居中 > 比例**。
    比例排最后不是因为它差，而是因为它最容易被滥用 —— 相对整页的比例在单页单设备上
    永远算得出来，于是组件挂错父视图、溢出容器的负坐标也能被一条比例「对齐」过去。

    ``centered`` 只在**明显不在边上**时才判（否则「左右各 16」会被读成居中，
    那样实现者只写 centerX，宽度就无从确定了）。

    ``shared_insets`` 是同一父视图下、同一轴**其它**兄弟出现过的偏移值集合
    （**不含元素自己**，见 ``analyse`` 里的构建处）。它让「贴边」这个判定有第二个
    证据来源：孤立的大偏移不像内边距（更像布局位置），降级为比例并提示复核，
    而不是凭量级就替人拍板。
    """
    lead, trail = lo - parent_lo, parent_hi - hi
    span = parent_hi - parent_lo
    fallback = {"kind": "proportional", "ratio": round((lo - parent_lo) / span, 6) if span else 0.0}
    for edge, value in (("leading", lead), ("trailing", trail)):
        if not (-EDGE_SNAP_TOL_PT <= value <= DESIGN_INSET_MAX_PT):
            continue
        # 两侧对称时不要求兄弟共享：一个盒子左右各 38pt，那个 38 显然是设计内边距。
        # 只有**孤立**的单侧大偏移才降级 —— 它既可能是内边距也可能是布局位置。
        symmetric = edge == "leading" and symmetric_insets_are_design(lead, trail)
        if value > DESIGN_INSET_STRICT_PT and not symmetric \
                and not inset_is_design(value, shared_insets):
            # 孤立的大偏移：可能是内边距，也可能是布局位置。比例表达在两种情况下都不会
            # 是灾难（大不了位置随父容器缩放），而错判成「固定内边距」会在父容器变形时
            # 顶死；所以这里给比例 + 提示，把判断权交回去。
            return dict(fallback, unanchoredInset=round(value, 4), nearEdge=edge)
        return {"kind": "pinned", "edge": edge, "inset": round(value, 4)}
    center_off = abs((lo + hi) / 2 - (parent_lo + parent_hi) / 2)
    if center_off <= CENTER_SNAP_TOL_PT:
        return {"kind": "centered", "edge": "center", "offset": round(center_off, 4)}
    if center_off <= NEAR_MISS_MAX_PT:
        # 差一点点居中：这几乎总是「设计稿上确实居中、测量有亚像素误差」，
        # 但也可能是「故意偏 3pt」的视觉修正。给提示让人定，别自己拍。
        return dict(fallback, nearMissCenter=round(center_off, 4))
    return fallback


def is_media_element(element: dict) -> bool:
    """这个元素**本身**是一张图吗（而不是「它身上有背景装饰」）？

    事实表把资源分成两种 ``role``（见 ``render_reference.mjs``）：

    * ``img`` —— 元素的 ``src``，或直接内容图；
    * ``background`` —— CSS ``background-image``，是**装饰**。

    两者必须分开，因为判据完全不同。实测里 ``text-group_12`` 是一个两行文字块
    （"Free trial enabled / Cancle anytime"，高 39），它身上挂着一张 ``background``
    背景图。早期版本对「有 assets」一律早退，于是这个文字块被判成了 ``fixed(39)`` ——
    高度本该由字体撑开，却被写成固定值；父容器或字号一变就散架。
    把背景装饰当成「这是个图片元素」，是把装饰当成了内容。
    """
    if element.get("src"):
        return True
    return any((asset or {}).get("role") != "background"
               for asset in (element.get("assets") or []))


def is_text_driven(element: dict) -> bool:
    """这个元素的大小是文字撑开的吗？

    文字撑开的尺寸不该比例化：比例缩放字号与行高会破坏排版，也会让最小点击区失守。
    位置仍然要比例化 —— 位置依赖容器尺寸，与内容无关。

    **为什么要看 ``text`` 而不只看 ``ownText``。** 实测里 ``text-wrapper_19`` 是
    ``flex-row justify-between`` 容器：``ownsText=False``、``ownText=""``，
    但 ``text`` 有内容。它 16pt 的高度完全由一行文字的字体决定。早期只看
    ``ownText`` 把它判成了 proportional，于是产出一条「16pt -> 比例 0.018307」的
    指导 —— 既把字体撑开的量当成了容器比例，又让每个标准边距 ``16`` 都撞进禁止清单。

    判据是**高度小 + 有文本**：手机上 ≤48pt 又有文本的盒子就是文字行/文字块，它的
    高度来自字体。反过来说，大容器（如整页 852pt 高）同样含文本，但它是布局容器，
    不能判成 intrinsic —— 高度阈值正是用来分开这两者的。

    图片元素（``is_media_element``）不适用上面两条：``<img>`` 的高度来自资源，
    不来自文本，即使它带了 alt 文本。而只挂着背景装饰的盒子仍然可能是文字块。
    """
    if is_media_element(element):
        return False
    if element.get("ownsText") or element.get("ownText"):
        return True
    height = (element.get("rect") or {}).get("height") or 0
    return bool(element.get("text")) and height <= TEXT_BLOCK_MAX_HEIGHT_PT


def size_of(rect: dict, dim: str) -> float:
    """从 ``rect`` 里取某个轴的边长。"""
    return float(rect["width"] if dim == "width" else rect["height"])


def region_label(element: dict) -> str:
    """给区域取一个可读名字：优先 id / className，其次文本，最后下标。

    事实表没有 ``region`` 字段（那是实现计划里的语义分组，渲染器无从得知），所以这里
    只能从 DOM 身份推导；``kindSource: proposed`` 提醒 Agent 这个名字需要自己确认。
    """
    for key in ("id", "className"):
        value = (element.get(key) or "").strip()
        if value:
            return value.split()[0].lstrip(".")[:32]
    text = (element.get("ownText") or "").strip()
    if text:
        return text[:24]
    return f"element_{element.get('index')}"


def analyse(page_facts: dict, transform, rect_space: str, target_mode: str,
            max_regions: int) -> dict:
    viewport = page_facts.get("viewport") or {}
    basis = ({"width": float(viewport["width"]), "height": float(viewport["height"])}
             if rect_space == "device" and viewport.get("width")
             else ({"width": float(transform.canvas_width), "height": float(transform.canvas_height)}
                   if transform else None))
    if not basis:
        raise CanvasMapError("无法确定比例基准尺寸")

    elements = page_facts.get("elements") or []
    by_index = {e.get("index"): e for e in elements}
    # 父视图信息来自渲染器（schemaVersion 3 起）：parentIndex 是最近可见祖先的下标，
    # null 表示直接父视图就是整屏画布。读不到时**不能假设层级已知** —— 旧事实表一律
    # 退回整屏画布基准，并如实告警，而不是默默当作「父就是画布」（那正是要修的错）。
    has_hierarchy = any("parentIndex" in e for e in elements)

    regions, forbidden, skipped, warnings = [], [], [], []
    skipped_forbidden = []
    review_hints = []
    pinned_insets = set()
    candidates = []
    for element in elements:
        rect = element.get("rect") or {}
        if not rect.get("width") or not rect.get("height"):
            continue
        if rect["width"] < MIN_SIDE_PX or rect["height"] < MIN_SIDE_PX:
            skipped.append({"index": element.get("index"), "reason": "side-too-small"})
            continue
        candidates.append(element)

    if len(candidates) > max_regions:
        # 按面积降序取前 N：小元素通常是被包含的细节，布局关系由大区域决定。
        candidates.sort(key=lambda e: -(e["rect"]["width"] * e["rect"]["height"]))
        skipped.extend({"index": e.get("index"), "reason": "over-max-regions"}
                       for e in candidates[max_regions:])
        candidates = candidates[:max_regions]

    def parent_key(element):
        """父视图的身份键：用于兄弟共享统计与关系里的 ofIndex。

        没有层级信息时一律取 ``None``（等于「父是整屏画布」），**不取 DOM 序号** ——
        那会得到错位编号，而错位只是个普通整数，不报错。
        """
        return element.get("parentIndex") if has_hierarchy else None

    if not has_hierarchy:
        warnings.append(
            "事实表没有父子层级字段（parentIndex，需 schemaVersion 3）：本次所有位置基准"
            "一律退回整屏画布，无法表达「相对直接父视图」的关系。带层级重新渲染后再生成规格，"
            "否则嵌套组件的内部布局会在父容器变尺寸时漂移。")

    # 先算出「父是谁」，供位置基准与尺寸基准共用。
    def parent_of(element):
        """返回 (父元素或 None, 父的 region 名, 基准标签)。父为 None 即整屏画布。"""
        parent_index = element.get("parentIndex")
        parent = by_index.get(parent_index) if has_hierarchy else None
        if parent is None:
            return None, "root", "root"
        return parent, region_label(parent), region_label(parent)

    def parent_box(element):
        """父视图的 (origin, span)。父不在事实表里时退回整屏画布，并如实体现在 basis 字段。"""
        parent, name, _ = parent_of(element)
        prect = (parent or {}).get("rect") or {}
        if prect.get("width") and prect.get("height"):
            return ({"x": float(prect["x"]), "y": float(prect["y"])},
                    {"width": float(prect["width"]), "height": float(prect["height"])},
                    name, "parent")
        return ({"x": 0.0, "y": 0.0},
                {"width": float(basis["width"]), "height": float(basis["height"])},
                "root", "viewport")

    # 页面外框：挂在整屏画布下、面积几乎等于视口的那个元素（Lanhu 导出页里的 ``.page``）。
    # 它的尺寸由**设备**决定（要铺满），不是设计稿给的值 —— 而它的测量值恰好等于画布尺寸，
    # 在别的设备上就会量出「右边 9pt / 下边 22pt」这样的残留。照残留写边距是凭空造出的错。
    viewport_area = float(basis["width"]) * float(basis["height"])
    outer_frame_index = None
    if viewport_area > 0:
        root_basis = [e for e in candidates
                      if has_hierarchy and e.get("parentIndex") is None or not has_hierarchy]
        if root_basis:
            biggest = max(root_basis, key=lambda e: e["rect"]["width"] * e["rect"]["height"])
            if biggest["rect"]["width"] * biggest["rect"]["height"] >= \
                    viewport_area * OUTER_FRAME_AREA_RATIO:
                outer_frame_index = biggest.get("index")

    # 兄弟共享统计：同一父视图下、同一轴同一侧出现过的偏移值。
    # 设计常量之所以是常量，因为它在多处复用 —— 这是「贴边」判定的第二个证据来源，
    # 单靠「数值小于 64」分不出内边距与布局位置。
    #
    # 桶里存 (元素下标, 值) 而不是裸值，为的是读取时能**排除元素自己**。
    # 这一点不是洁癖：元素自己的偏移量当然等于它自己，把自证当成「兄弟共享」，
    # 第二档证据（32..64pt 需要复用）就永远成立，于是「孤立大偏移降级为比例」
    # 那条分支成了死代码 —— 它的 reviewHint 是把判断权交回给 Agent 的唯一路径，
    # 而实测它在真实页面上一次都没触发过。
    inset_sharing = {}
    for element in candidates:
        origin, span, _, _ = parent_box(element)
        rect = element["rect"]
        for axis, lo, hi in (("x", rect["x"], rect["x"] + rect["width"]),
                             ("y", rect["y"], rect["y"] + rect["height"])):
            plo = origin[axis]
            phi = plo + span["width" if axis == "x" else "height"]
            for edge, value in (("leading", lo - plo), ("trailing", phi - hi)):
                if 0 - EDGE_SNAP_TOL_PT <= value <= DESIGN_INSET_MAX_PT:
                    bucket = inset_sharing.setdefault((parent_key(element), axis, edge), [])
                    bucket.append((element.get("index"), round(value, 4)))

    def shared_insets(element, axis) -> list:
        """同一父视图下**其它**兄弟在同一轴两侧的偏移值（不含元素自己）。"""
        key = parent_key(element)
        own = element.get("index")
        values = []
        for edge in ("leading", "trailing"):
            values.extend(value for index, value in inset_sharing.get((key, axis, edge), [])
                          if index != own)
        return values


    for element in candidates:
        rect = element["rect"]
        region = region_label(element)
        origin, span, of_name, basis_kind = parent_box(element)
        parent_index = element.get("parentIndex") if has_hierarchy else None

        # ratios 现在全部相对**父视图**：这才是实现侧能直接用的形式。
        # 相对整页算出来的比例在单页单设备上同样「对得上」，但父容器一变尺寸就漂移。
        local_x, local_y = rect["x"] - origin["x"], rect["y"] - origin["y"]
        ratios = {
            "xRatio": round(local_x / span["width"], 6),
            "yRatio": round(local_y / span["height"], 6),
            "widthRatio": round(rect["width"] / span["width"], 6),
            "heightRatio": round(rect["height"] / span["height"], 6),
        }
        ratios["centerXRatio"] = round((local_x + rect["width"] / 2) / span["width"], 6)
        ratios["centerYRatio"] = round((local_y + rect["height"] / 2) / span["height"], 6)

        # 设备空间下的绝对值：这才是可能被误写进代码的数字。
        if rect_space == "device":
            device_box = box_from(rect)
        else:
            device_box = transform.to_device(box_from(rect))

        text_driven = is_text_driven(element)
        inferred_block = (text_driven and not element.get("ownsText")
                          and not element.get("ownText"))

        relations = []
        # ---- 位置轴：贴边 > 居中 > 比例，基准是父视图 ----
        for axis, key, lo, hi in (("x", "x", rect["x"], rect["x"] + rect["width"]),
                                  ("y", "y", rect["y"], rect["y"] + rect["height"])):
            parent_lo = origin[axis]
            parent_hi = origin[axis] + span["width" if axis == "x" else "height"]
            shared = shared_insets(element, axis)
            placed = classify_position(lo, hi, parent_lo, parent_hi, shared)
            relation = {"id": f"{region}.{key}", "axis": key, "of": of_name,
                        "ofIndex": parent_index if basis_kind == "parent" else None,
                        "kind": placed["kind"]}
            if placed["kind"] == "pinned":
                relation.update({"edge": placed["edge"], "inset": placed["inset"],
                                 "note": "贴父边 + 固定间距：这是约束闭合，不是比例"})
                pinned_insets.add(placed["inset"])
            elif placed["kind"] == "centered":
                relation.update({"note": "与父视图居中对齐；用对齐锚点表达，不要各自算数值凑相等"})
            else:
                relation.update({"ratio": placed["ratio"],
                                 "note": "确属随父容器成比例变化的位置关系；基准是父视图，不是整页"})
                if "nearMissCenter" in placed:
                    review_hints.append({
                        "region": region, "index": element.get("index"),
                        "hint": f"该元素在{'水平' if axis == 'x' else '垂直'}方向距父视图居中"
                                f"仅差 {placed['nearMissCenter']:g}pt（容差 {CENTER_SNAP_TOL_PT}pt）："
                                "设计稿八成是居中，测量有亚像素误差。请确认是居中还是刻意偏移，"
                                "确认居中就把关系改成 centered。"})
                if "unanchoredInset" in placed:
                    side = {"x": {"leading": "左", "trailing": "右"},
                            "y": {"leading": "上", "trailing": "下"}}[axis][placed["nearEdge"]]
                    review_hints.append({
                        "region": region, "index": element.get("index"),
                        "hint": f"该元素距父视图{side}侧 {placed['unanchoredInset']:g}pt：超过 "
                                f"{DESIGN_INSET_STRICT_PT:g}pt 且没有兄弟共享同一个值，"
                                "所以判成了比例而不是固定内边距。如果设计稿写明这是固定边距，"
                                "请改成 pinned。"})
            relations.append(relation)

        # ---- 尺寸轴：pinned / intrinsic / fixed / proportional ----
        #
        # ``axis_text_driven`` 传的是**整个元素的文字属性**，不是「这个轴的文字属性」：
        # classify_size 内部靠它决定纵向偏移算不算设计内边距（文字块的上下留白是
        # 「父容器减内容高度」的副产品，不是设计稿写的内边距）。横向不走这条判据。
        for dim, key, lo, hi in (("width", "width", rect["x"], rect["x"] + rect["width"]),
                                 ("height", "height", rect["y"], rect["y"] + rect["height"])):
            parent_lo = origin["x" if dim == "width" else "y"]
            parent_hi = parent_lo + span[dim]
            sized = classify_size(lo, hi, parent_lo, parent_hi, text_driven,
                                  axis=dim,
                                  outer_frame=(element.get("index") == outer_frame_index))
            relation = {"id": f"{region}.{key}", "axis": dim, "of": of_name,
                        "ofIndex": parent_index if basis_kind == "parent" else None,
                        "kind": sized["kind"]}
            if sized["kind"] == "intrinsic":
                relation["why"] = (
                    f"{'高度' if dim == 'height' else '宽度'} {size_of(rect, dim):g}pt "
                    "由文字内容撑开；比例缩放会破坏排版并让最小点击区失守"
                    if not inferred_block else
                    f"盒子{'高度' if dim == 'height' else '宽度'} "
                    f"{size_of(rect, dim):g}pt 且子树含文本，判为文字块：尺寸来自字体")
                if inferred_block and dim == "height":
                    review_hints.append({
                        "region": region, "index": element.get("index"),
                        "hint": "这个盒子自己没有文本（ownsText=False），但子树里有文本且高度"
                                f"只有 {rect['height']:g}pt，判为文字块、高度按 intrinsic 处理。"
                                "如果它其实是个固定高度的容器（按钮底板、卡片），请改成 fixed。"})
            elif sized["kind"] == "pinned":
                relation.update({"edges": sized["edges"], "insets": sized["insets"],
                                 "why": sized["why"]})
                if sized.get("fullBleed"):
                    # 机器可读的「铺满」标记：实现侧要写的是 leading+trailing 两条零距约束，
                    # 而不是照量出来的残留写内边距。留在关系里比只写在 why 里可核。
                    relation["fullBleed"] = True
                if "inset" in sized:
                    relation["inset"] = sized["inset"]
                    pinned_insets.add(sized["inset"])
                else:
                    # 两侧不等距时把两个值都收进设计常量：它们都是设计稿给的，
                    # 汇总出来是为了让「允许写的字面量」有一份可复核的清单。
                    pinned_insets.update(sized["insets"].values())
            elif sized["kind"] == "fixed":
                relation.update({"value": sized["value"]})
                if sized["value"] > TEXT_BLOCK_MAX_HEIGHT_PT:
                    review_hints.append({
                        "region": region, "index": element.get("index"),
                        "hint": f"{key} {sized['value']:g}pt 被判为固定设计值（控件量级，"
                                f"≤{CONTROL_MAX_PT:g}pt）。如果它其实是个随容器伸缩的区域，"
                                "请改成 pinned 或 proportional。"})
            else:
                relation.update({"ratio": sized["ratio"],
                                 "note": "确属随父容器成比例变化的尺寸关系"})
            relations.append(relation)

        regions.append({
            "region": region, "index": element.get("index"),
            "parentIndex": parent_index,
            "parent": of_name,
            "basis": basis_kind,
            "kindSource": "proposed",
            "ratios": ratios,
            "relations": relations,
            "nativeIdiom": native_idiom(
                target_mode, region, relations,
                "self.view" if of_name == "root" else of_name),
        })

        # 绝对定位 + 溢出父容器：比例会跑出 [0,1]，那不是「比例」该管的范围。
        # 这类元素的坐标原点在 CSS 里是最近的 positioned 祖先，实现侧却是直接父视图，
        # 两者可能不同（事实表用 positioningContextIndex 记下来）。不替人决定，只提示。
        style_position = (element.get("style") or {}).get("position")
        outside = [k for k in ("xRatio", "yRatio", "widthRatio", "heightRatio")
                   if ratios[k] < -0.001 or ratios[k] > 1.001]
        if style_position in ("absolute", "fixed") and outside:
            context = element.get("positioningContextIndex")
            differs = "positioningContextIndex" in element and context != parent_index
            review_hints.append({
                "region": region, "index": element.get("index"),
                "hint": f"该元素是 {style_position} 定位且超出父视图范围（{', '.join(outside)} 超出 [0,1]）："
                        "比例表达对它不适用，请人工确认它在原生里的挂载父视图与锚点。"
                        + ("事实表显示它的坐标原点不是直接父视图（positioningContextIndex "
                           f"= {context}），实现时要么把它挂到那个祖先下，要么显式补上偏移。"
                           if differs else
                           "实测它的坐标原点与直接父视图一致，通常说明设计稿里就是刻意溢出"
                           "（如徽标压边、装饰超出），用父视图坐标 + 显式偏移实现。")})

        # 禁止清单只收 **proportional** 的关系，且必须**同量纲配对**。
        #
        # 两类修正都很关键：
        # * ``fixed`` 的 44pt、``pinned`` 的 16pt 是**应当写的**字面量（设计值/设计常量），
        #   把它们列进禁止清单就是让正确写法被判违规。旧版对非文字元素的 height 一律收录，
        #   正好会把「按钮高 44」拦下 —— 契约级变更必须一次改完，否则两边自相矛盾。
        # * 绝对值与比例必须指同一个量：早期把左/上边缘的绝对值配给了中心比例
        #   （``group_9.y`` 写成「320pt -> 0.670481」），开发者照做会把元素整体下移半个高度
        #   —— 这条「指导」本身就是错的。所以位置轴各出两条，各自闭合。
        device_center = {"x": device_box.x + device_box.width / 2,
                         "y": device_box.y + device_box.height / 2}
        forbidden_pairs = (
            ("x", "centerX", device_center["x"], ratios["centerXRatio"],
             "用中心锚点时写这个绝对值是错的"),
            ("x", "leading", device_box.x, ratios["xRatio"],
             "用 leading/左边缘锚点时写这个绝对值是错的"),
            ("y", "centerY", device_center["y"], ratios["centerYRatio"], ""),
            ("y", "top", device_box.y, ratios["yRatio"], ""),
            ("width", "width", device_box.width, ratios["widthRatio"], ""),
            ("height", "height", device_box.height, ratios["heightRatio"], ""),
        )
        for axis, anchor, absolute, ratio, hint in forbidden_pairs:
            relation = next((r for r in relations if r.get("axis") == axis), None)
            if relation is None or relation["kind"] != "proportional":
                continue
            if abs(absolute) < MIN_MEANINGFUL_PT:
                skipped_forbidden.append({
                    "relation": f"{region}.{anchor}", "deviceDerivedPt": round(absolute, 4),
                    "reason": "near-zero", "ratioInstead": ratio,
                    "detail": f"|{absolute:.4f}pt| < {MIN_MEANINGFUL_PT}pt：原点/亚像素级，"
                              "该值在任何设备上都成立，写成字面量不算错误"})
                continue
            why = (f"探针设备视口 {basis['width']:g}x{basis['height']:g} 上的绝对值，"
                   "换台设备即失效，不得写成字面量")
            forbidden.append({
                "relation": f"{region}.{anchor}",
                "deviceDerivedPt": round(absolute, 4),
                "why": f"{why}。{hint}" if hint else why,
                "ratioInstead": ratio,
            })

    if not regions:
        warnings.append("事实表里没有可用于比例化的元素：检查 page-facts.json 是否为空，"
                        f"或元素尺寸是否都小于 {MIN_SIDE_PX}px")

    diagnostics = {
        "tool": "layout_proportions.py",
        # 3 = 两轴口径：model 由 "proportional" 改为 "fixed-size-parent-relative-position"，
        # region 多了 basis/parentIndex/parent，relations 多了 fixed/pinned/intrinsic 三类。
        # 按 model 或 kind 取值的老读者在 v2 产物上会静默按旧语义解释，所以要能区分开。
        "schemaVersion": 3,
        "targetMode": target_mode,
        "rectSpace": rect_space,
        "basis": basis,
        "hierarchyAvailable": has_hierarchy,
        "regionCount": len(regions),
        "candidateCount": len(candidates),
        "forbiddenLiteralCount": len(forbidden),
        "skippedForbiddenCount": len(skipped_forbidden),
        "skippedForbidden": skipped_forbidden[:20],
        "reviewHints": review_hints[:20],
        # 贴边内边距是**设计常量**，应当写进实现计划的 designConstants 供复核；
        # 这里汇总出来省得 Agent 去源码里翻。0 不入列：0 是设备无关的，列进去是噪音。
        "pinnedInsets": sorted(v for v in pinned_insets if v),
        "skipped": skipped[:20],
        "warnings": warnings,
    }
    if transform is not None:
        deviation = transform.axis_deviation()
        diagnostics["canvasTransform"] = {
            "policy": transform.policy,
            "canvasSize": {"width": transform.canvas_width, "height": transform.canvas_height},
            "deviceSize": {"width": transform.device_width, "height": transform.device_height},
            "scaleX": round(transform.scale_x, 8), "scaleY": round(transform.scale_y, 8)}
        diagnostics["axisDeviation"] = deviation
        if not deviation["interchangeable"]:
            warnings.append(
                f"本设备对上 fit 映射与比例映射最大差 {deviation['maxPt']}pt，超过位置容差 "
                f"{deviation['positionTolerancePt']}pt：实现必须用比例模型，对齐审计也必须改用"
                "比例模型预测，否则会把模型差报成实现错误")

    return {
        "layoutProportions": {
            "model": "fixed-size-parent-relative-position",
            "basis": "viewport" if rect_space == "device" else "canvas",
            "axisPolicy": "per-axis",
            "basisSize": basis,
            "regions": regions,
            "forbiddenLiterals": forbidden,
            # 贴边内边距汇总：这些是设计常量，应当进实现计划的 designConstants。
            # 汇总出来是为了让「允许写的字面量」有一份可复核的清单，而不是
            # 让 Agent 自己猜哪些数字算设计常量。
            "designConstantCandidates": {
                "pinnedInsets": sorted(v for v in pinned_insets if v),
                "note": "贴边内边距与 fixed 尺寸都是应当写的设计值；把内边距填进 "
                        "designConstants，fixed 尺寸由 kind=fixed 的 value 自带",
            },
        },
        "diagnostics": diagnostics,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page-facts", required=True, help="页面级 reference/page-facts.json")
    ap.add_argument("--runtime-device", help="runtime-device.json（--rect-space lanhu 时需要）")
    ap.add_argument("--transform", help="含 canvasTransform 的 JSON")
    ap.add_argument("--canvas", help="Lanhu 画布尺寸 WxH（--rect-space lanhu 时需要）")
    ap.add_argument("--rect-space", choices=("auto", "device", "lanhu"), default="auto",
                    help="rect 所在的坐标空间；默认 auto，按 rectInReference == rect*dpr 判定")
    ap.add_argument("--target-mode", default="ios-uikit-objective-c",
                    help="目标输出模式，决定 nativeIdiom 的写法")
    ap.add_argument("--max-regions", type=int, default=DEFAULT_MAX_REGIONS)
    ap.add_argument("--output", help="写入该 JSON 路径")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    page_facts = load_json(args.page_facts)
    if not page_facts:
        print(f"无法读取事实表（文件不存在或不是 JSON）：{args.page_facts}", file=sys.stderr)
        return 2
    if not page_facts.get("elements"):
        print("事实表没有 elements：无法推导布局比例", file=sys.stderr)
        return 2

    detection = detect_rect_space(page_facts)
    if args.rect_space == "auto":
        if not detection.get("space"):
            print(f"无法判定 rect 的坐标空间：{detection.get('reason')}\n"
                  "用 --rect-space device 或 --rect-space lanhu 显式指定。"
                  "猜错会让 scale 被乘两遍，所以这里不猜。", file=sys.stderr)
            return 2
        rect_space = detection["space"]
    else:
        rect_space = args.rect_space
        if detection.get("space") and detection["space"] != rect_space:
            print(f"[warn] 事实表的证据指向 {detection['space']} 空间，但你指定了 {rect_space}；"
                  "按你的指定继续，请确认这不是「多乘一层 scale」", file=sys.stderr)

    transform = None
    if rect_space == "lanhu":
        try:
            if args.transform:
                payload = load_json(args.transform) or {}
                transform = transform_from_canvas_transform(
                    payload.get("canvasTransform", payload))
            elif args.runtime_device and args.canvas:
                width, height = parse_canvas(args.canvas)
                transform = transform_from_runtime_device(
                    load_json(args.runtime_device), width, height)
            else:
                print("--rect-space lanhu 需要 --transform，或 --runtime-device 配合 --canvas",
                      file=sys.stderr)
                return 2
        except CanvasMapError as error:
            print(f"画布变换构造失败：{error}", file=sys.stderr)
            return 2
        except (OSError, json.JSONDecodeError) as error:
            # 文件缺失/不是 JSON 属于用法问题，要和「坐标系判不出来」一样干净退出，
            # 不能抛 traceback —— 那会让调用方分不清是输入错了还是脚本坏了。
            print(f"读取画布变换输入失败：{error}", file=sys.stderr)
            return 2

    try:
        result = analyse(page_facts, transform, rect_space, args.target_mode,
                         args.max_regions)
    except CanvasMapError as error:
        print(f"比例推导失败：{error}", file=sys.stderr)
        return 2

    result["diagnostics"]["rectSpaceDetection"] = detection

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                     encoding="utf-8")

    if not args.quiet:
        diag = result["diagnostics"]
        props = result["layoutProportions"]
        print(f"rect 坐标空间：{rect_space}（{detection.get('reason')}）")
        print(f"整屏画布基准：{props['basis']} {props['basisSize']['width']:g}x"
              f"{props['basisSize']['height']:g}")
        print(f"父子层级：{'可用（位置基准为直接父视图）' if diag['hierarchyAvailable'] else '不可用（位置基准退回整屏画布）'}")
        counts = {}
        for region in props["regions"]:
            for rel in region["relations"]:
                counts[rel["kind"]] = counts.get(rel["kind"], 0) + 1
        print(f"\n{diag['regionCount']} 个区域，关系类别分布：" +
              "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        print("（fixed=设计值不缩放 / pinned=贴边约束 / intrinsic=内容撑开 / "
              "proportional=比例 / centered=对齐父视图中心）")
        for region in props["regions"]:
            parts = []
            for rel in region["relations"]:
                if rel["kind"] == "fixed":
                    parts.append(f"{rel['axis']}:fixed({rel['value']:g})")
                elif rel["kind"] == "pinned":
                    edges = rel.get("edges") or [rel.get("edge", "")]
                    insets = rel.get("insets") or {}
                    uniform = rel.get("inset")
                    if insets and len(set(insets.values())) > 1:
                        detail = "/".join(f"{insets.get(e, 0):g}" for e in edges)
                    else:
                        detail = f"{uniform if uniform is not None else 0:g}"
                    parts.append(f"{rel['axis']}:pinned({','.join(edges)} {detail})")
                elif rel["kind"] == "centered":
                    parts.append(f"{rel['axis']}:centered")
                elif rel["kind"] == "intrinsic":
                    parts.append(f"{rel['axis']}:intrinsic")
                else:
                    parts.append(f"{rel['axis']}:{rel.get('ratio')}")
            print(f"  {region['region']:<26} 基准={region['parent']:<20} {'  '.join(parts)}")
        if props["forbiddenLiterals"]:
            print("\n禁止写进代码的绝对值（探针设备上的值 -> 应当改用的表达；只涉及 proportional）：")
            for item in props["forbiddenLiterals"][:10]:
                print(f"  {item['deviceDerivedPt']:>9.3f}pt  ->  "
                      f"{item['relation']} = {item['ratioInstead']}")
        insets = props["designConstantCandidates"]["pinnedInsets"]
        if insets:
            print(f"\n识别到的贴边内边距（设计常量，建议填进 designConstants）："
                  f"{', '.join(f'{v:g}' for v in insets)}")
        if diag.get("skippedForbiddenCount"):
            print(f"\n（另有 {diag['skippedForbiddenCount']} 条接近原点的绝对值未列入禁止清单："
                  "0 在任何设备上都成立，列进去只会制造噪音）")
        if diag.get("reviewHints"):
            print(f"\n需要人工复核的 {len(diag['reviewHints'])} 条（脚本只提议，判断权在你）：")
            for hint in diag["reviewHints"][:6]:
                print(f"  · {hint['region']}：{hint['hint'][:96]}")
        for line in diag["warnings"]:
            print(f"\n[warn] {line}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
