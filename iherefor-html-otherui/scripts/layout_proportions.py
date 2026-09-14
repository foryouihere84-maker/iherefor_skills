#!/usr/bin/env python3
"""把事实表里的区域位置转成「比例规格」，供原生布局实现使用。

**为什么需要它。** 组件之间的布局关系必须用比例表达，不能写成固定 pt。事实表里的
``rect`` 是「这一台设备上的绝对值」，把它写进原生约束就把布局钉死在这一台设备上 ——
换台设备就是错的，而它看起来「有出处、算过」，比一眼可疑的魔数更难发现。

**先说清 ``rect`` 在哪个坐标空间里，这是本脚本最容易出错的地方。** 渲染器是在
**设备视口**上渲染基准图的（HTML 会跟着 reflow），所以 ``rect`` 已经是设备点，
``rectInReference == rect * devicePixelRatio``。这意味着：

* 比例 = ``rect / viewport``，**不需要**再过一次 ``canvasTransform``；
* 再过一次就会把 scale 乘两遍 —— 这正是「多乘一层 scale」那类系统性偏移。

本脚本用上面那条恒等式**自动判定** ``rect`` 的坐标空间，判定不出来就拒绝继续，
而不是默默按某个空间算下去。需要按 Lanhu 画布空间算时用 ``--rect-space lanhu`` 显式指定。

**与 `canvas_map.py` 的分工**：坐标换算一律走 `canvas_map`，本脚本不自己写任何
``* scale``；它只负责把位置重新组织成实现侧要的比例形式。

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


def native_idiom(target_mode: str, region: str, relations) -> list:
    """按目标模式给出该区域的比例表达写法（提示，不代替 Agent 的工程判断）。"""
    lines = []
    for rel in relations:
        if rel["kind"] != "proportional":
            continue
        axis, ratio = rel["axis"], rel["ratio"]
        key = f"{region}.{axis}"
        base = "self.view" if rel["of"] == "root" else rel["of"]
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
            source = "height" if axis == "y" else "width"
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
    """
    if element.get("src") or element.get("assets"):
        return False
    if element.get("ownsText") or element.get("ownText"):
        return True
    height = (element.get("rect") or {}).get("height") or 0
    return bool(element.get("text")) and height <= TEXT_BLOCK_MAX_HEIGHT_PT


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

    regions, forbidden, skipped, warnings = [], [], [], []
    skipped_forbidden = []
    review_hints = []
    candidates = []
    for element in page_facts.get("elements") or []:
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

    for element in candidates:
        rect = element["rect"]
        region = region_label(element)
        ratios = {key: round(rect[axis] / basis[dim], 6) for key, axis, dim in (
            ("xRatio", "x", "width"), ("yRatio", "y", "height"),
            ("widthRatio", "width", "width"), ("heightRatio", "height", "height"))}
        ratios["centerXRatio"] = round((rect["x"] + rect["width"] / 2) / basis["width"], 6)
        ratios["centerYRatio"] = round((rect["y"] + rect["height"] / 2) / basis["height"], 6)

        # 设备空间下的绝对值：这才是可能被误写进代码的数字。
        if rect_space == "device":
            device_box = box_from(rect)
        else:
            device_box = transform.to_device(box_from(rect))

        relations = [
            {"id": f"{region}.x", "kind": "proportional", "axis": "x",
             "ratio": ratios["centerXRatio"], "of": "root",
             "note": "用中心比例而非左边缘比例：居中元素在容器宽度变化时中心不动"},
            {"id": f"{region}.y", "kind": "proportional", "axis": "y",
             "ratio": ratios["centerYRatio"], "of": "root", "note": "同上"},
            {"id": f"{region}.width", "kind": "proportional", "axis": "width",
             "ratio": ratios["widthRatio"], "of": "root"},
        ]
        text_driven = is_text_driven(element)
        inferred_block = (text_driven and not element.get("ownsText")
                          and not element.get("ownText"))
        if inferred_block:
            review_hints.append({
                "region": region, "index": element.get("index"),
                "hint": "这个盒子自己没有文本（ownsText=False），但子树里有文本且高度"
                        f"只有 {rect['height']:g}pt，判为文字块、高度按 intrinsic 处理。"
                        "如果它其实是个固定高度的容器（按钮底板、卡片），请改成 proportional。",
            })
        if text_driven:
            relations.append({
                "id": f"{region}.height", "kind": "intrinsic",
                "why": (f"高度 {rect['height']:g}pt 由字号与行高撑开；比例缩放会破坏排版"
                        "并让最小点击区失守" if not inferred_block else
                        f"盒子高度 {rect['height']:g}pt 且子树含文本，判为文字块：高度来自字体")})
        else:
            relations.append({"id": f"{region}.height", "kind": "proportional",
                              "axis": "height", "ratio": ratios["heightRatio"], "of": "root"})

        regions.append({
            "region": region, "index": element.get("index"),
            "kindSource": "proposed",
            "ratios": {k: ratios[k] for k in
                       ("xRatio", "yRatio", "centerXRatio", "centerYRatio",
                        "widthRatio", "heightRatio")},
            "relations": relations,
            "nativeIdiom": native_idiom(target_mode, region, relations),
        })

        # 禁止清单必须**同量纲配对**：绝对值与比例必须指同一个量。
        #
        # 早期版本把左/上边缘的绝对值配给了中心比例：``group_9.y`` 写成「320pt ->
        # 0.670481」，而 320 是上边缘、0.670481 是中心（586/874）。开发者照做会把
        # 元素整体下移半个高度 —— 这条「指导」本身就是错的。所以位置轴各出两条：
        # 中心比例配中心点绝对值，边缘比例配左/上边缘绝对值，各自闭合。
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
        "schemaVersion": 1,
        "targetMode": target_mode,
        "rectSpace": rect_space,
        "basis": basis,
        "regionCount": len(regions),
        "candidateCount": len(candidates),
        "forbiddenLiteralCount": len(forbidden),
        "skippedForbiddenCount": len(skipped_forbidden),
        "skippedForbidden": skipped_forbidden[:20],
        "reviewHints": review_hints[:20],
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
            "model": "proportional",
            "basis": "viewport" if rect_space == "device" else "canvas",
            "axisPolicy": "per-axis",
            "basisSize": basis,
            "regions": regions,
            "forbiddenLiterals": forbidden,
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
        print(f"比例基准：{props['basis']} {props['basisSize']['width']:g}x"
              f"{props['basisSize']['height']:g}")
        print(f"\n{diag['regionCount']} 个区域，"
              f"{len(props['forbiddenLiterals'])} 条绝对值被标记为不得写成字面量：")
        for region in props["regions"]:
            kinds = "/".join(f"{r.get('axis', 'h')}:{r['kind']}" for r in region["relations"])
            print(f"  {region['region']:<28} {kinds}")
        if props["forbiddenLiterals"]:
            print("\n禁止写进代码的绝对值（左边是探针设备上的值，右边是应当使用的比例）：")
            for item in props["forbiddenLiterals"][:10]:
                print(f"  {item['deviceDerivedPt']:>9.3f}pt  ->  "
                      f"{item['relation']} = {item['ratioInstead']}")
        if diag.get("skippedForbiddenCount"):
            print(f"\n（另有 {diag['skippedForbiddenCount']} 条接近原点的绝对值未列入禁止清单："
                  "0 在任何设备上都成立，列进去只会制造噪音）")
        for line in diag["warnings"]:
            print(f"\n[warn] {line}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
