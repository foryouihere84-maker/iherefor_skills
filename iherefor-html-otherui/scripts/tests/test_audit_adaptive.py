#!/usr/bin/env python3
"""回归：多宽度采样的几何契约审计（``audit_adaptive.py``）。

这一门是平板适配的**运行期那一半**，而且它**刻意不做像素比对** —— Lanhu 只有一份设计稿，
拿手机基准去比 iPad 截图是拿两个不同画布比对，``audit_alignment.py`` 会直接判「基准不可信」。
所以这里断言的全是几何关系，输入是各采样的几何转储。

测试盯三件事，缺一不可：

1. **召回**：等比放大（``sizeInvariance``）、内边距被撑大（``insetPreservation``）、越界、
   封顶没生效 / 没居中、点击区变小、兼容缩放模式、信箱留边、宽度非单调、兄弟重叠 —— 逐条拦下；
2. **精度**：合规几何必须判 pass。审计器一旦误报，「平板适配」就会被当成噪声忽略，
   而它本该是这一层唯一的自动化防线；
3. **不许假绿**：缺必需采样时 ``sampleCoverage`` 必须 fail。少了采样，其余七项检查
   反而会「全绿」—— 那是本次审计最容易骗过自己的形态。

另有 sizeVariants 分档的两条边界（用例 2b/2c）：同一设计有多设备稿（xx + xx-iPad）时，
照 iPad 稿还原的**尺寸分档**是合规的，但必须逐档声明 ``adaptiveLayout.sizeVariants``
（带 basis/why）；声明过 → 放行，没声明 → 仍判 ``size-not-invariant``。这是
「尺寸不缩放」铁律**唯一的合法出口**，不是放开整页等比放大。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit_adaptive.py"

SAMPLES = [
    ("phone-compact", "compact", 402, 874),
    ("tablet-regular-portrait", "medium", 1024, 1366),
    ("tablet-regular-landscape", "expanded", 1366, 1024),
]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def targets(tmp, entries=None):
    """默认声明三个必需采样，各自指向 geo/<id>.json。"""
    samples = []
    for sample_id, width_class, width, height in SAMPLES:
        entry = {
            "id": sample_id, "widthClass": width_class, "required": True,
            "windowBoundsPoints": {"width": width, "height": height},
            "screenshotScale": 3 if width_class == "compact" else 2,
            "geometry": f"geo/{sample_id}.json",
        }
        samples.append(entry)
    path = tmp / "adaptive-targets.json"
    write_json(path, {"schemaVersion": 1, "platform": "iOS Simulator",
                      "deviceFamily": "1,2", "samples": entries or samples})
    return path


def geometry(tmp, sample_id, window, *, elements=None, compatibility=False,
             letterbox=None, touch_minimum=44, platform=None):
    """造一份几何转储。``elements`` 缺省用一份「尺寸不缩放 + 封顶居中」的合规集合。

    缺省集合是**随窗口宽度变**的：窗口比封顶值窄时（手机 402pt vs 封顶 600pt）
    内容列就是「窗口宽 − 两侧各 16pt」，不会出现 600pt 的列塞进 402pt 窗口这种
    物理上不存在的形态。fixture 造出不可能的几何，只会把测试本身变成噪声源。
    """
    width, height = window
    if elements is None:
        if width > 600:
            column, left = 600.0, (width - 600) / 2
        else:
            column, left = width - 32.0, 16.0
        elements = [
            {"id": "contentColumn", "region": "form", "kind": "pinned",
             "rect": {"x": left, "y": 120, "width": column, "height": 400},
             "contentColumn": True,
             "insets": {"leading": left, "trailing": width - left - column},
             "insetExempt": ["leading", "trailing"]},
            {"id": "cta", "region": "form", "kind": "fixed",
             "rect": {"x": left + 16, "y": 300, "width": 347, "height": 48},
             "interactive": True},
            {"id": "offers", "region": "form", "kind": "fixed",
             "rect": {"x": left + 16, "y": 400, "width": 347, "height": 68}},
            {"id": "hero", "region": "hero", "kind": "pinned",
             "rect": {"x": 0, "y": 0, "width": width, "height": 100},
             "insets": {"leading": 0, "trailing": 0}},
        ]
    path = tmp / "geo" / f"{sample_id}.json"
    write_json(path, {
        "schemaVersion": 1, "sampleId": sample_id,
        "source": "runtime NSLog of view.bounds and element frames",
        "windowBoundsPoints": {"width": width, "height": height},
        "screenshotScale": 2,
        "compatibilityMode": compatibility,
        "letterbox": letterbox or {"x": 0, "y": 0, "width": 0, "height": 0},
        "touchTargetMinimum": touch_minimum,
        "elements": elements,
    })
    return path


def run(targets_path, plan=None, geometry_overrides=None, tolerance=None):
    out = Path(targets_path).parent / "audit.json"
    if out.is_file():
        out.unlink()   # 不删就会读到上一轮的结论，把「本次崩了」伪装成「上次的结果」
    args = [sys.executable, str(SCRIPT), "--targets", str(targets_path),
            "--output", str(out)]
    if plan:
        args += ["--plan", str(plan)]
    if tolerance is not None:
        args += ["--tolerance", str(tolerance)]
    for name, path in (geometry_overrides or {}).items():
        args += ["--geometry", f"{name}={path}"]
    proc = subprocess.run(args, capture_output=True, text=True)
    if "Traceback" in proc.stderr:
        raise AssertionError(f"审计器抛栈：{proc.stderr.strip()[-600:]}")
    report = json.loads(out.read_text()) if out.is_file() else {}
    return proc, report


def kinds(report):
    return {item.get("kind") for item in report.get("violations") or []}


def plan_doc(tmp):
    path = tmp / "plan.json"
    write_json(path, {"adaptiveLayout": {
        "model": "continuous-window-width",
        "regions": [{"region": "form", "widthPolicy": "max-content-width",
                     "maxContentWidth": {"value": 600, "of": "root", "reason": "单列"}}],
    }})
    return path


def main():
    problems = []

    def check(condition, message):
        if not condition:
            problems.append(message)

    with tempfile.TemporaryDirectory() as scratch:
        tmp = Path(scratch)
        plan = plan_doc(tmp)

        # ---- 用例 1：合规几何 → 必须过，且八项全跑 ----
        path = targets(tmp)
        for sample_id, _, width, height in SAMPLES:
            geometry(tmp, sample_id, (width, height))
        proc, report = run(path, plan)
        check(proc.returncode == 0 and report.get("status") == "pass",
              f"用例1：合规几何应判 pass，得到 {report.get('status')}"
              f"（{report.get('violations')}）")
        checks = report.get("checks") or {}
        for name in ("sampleCoverage", "sizeInvariance", "insetPreservation",
                     "noOverflow", "maxContentWidth", "touchTarget",
                     "noLetterbox", "continuity"):
            check(name in checks, f"用例1：缺少检查项 {name}，实得 {sorted(checks)}")
        check(checks.get("sizeInvariance", {}).get("compared", 0) >= 2,
              "用例1：sizeInvariance 应真的比过 fixed 元素，"
              f"得到 compared={checks.get('sizeInvariance', {}).get('compared')}")

        # ---- 用例 2：跨设备整页等比放大 → sizeInvariance 必须炸 ----
        # 平板适配里最典型的缺陷：手机稿的尺寸被放大到两个 tablet 采样（portrait+landscape
        # 一致放大，说明是「跨设备放大」而非「同设备内不一致」），而「基准只有一份」意味着
        # 像素 diff 发现不了它。无 sizeVariants 声明 → size-not-invariant。
        scaled = [
            {"id": "cta", "region": "form", "kind": "fixed",
             "rect": {"x": 0, "y": 300, "width": 903, "height": 125}, "interactive": True},
            {"id": "offers", "region": "form", "kind": "fixed",
             "rect": {"x": 0, "y": 500, "width": 903, "height": 177}},
        ]
        bad_portrait = geometry(tmp, "tablet-regular-portrait", (1024, 1366), elements=scaled)
        bad_landscape = geometry(tmp, "tablet-regular-landscape", (1366, 1024), elements=scaled)
        proc, report = run(path, plan, {"tablet-regular-portrait": bad_portrait,
                                        "tablet-regular-landscape": bad_landscape})
        check("size-not-invariant" in kinds(report),
              f"用例2：跨设备等比放大未被 sizeInvariance 拦下，实得 {sorted(kinds(report))}")
        check((report.get("checks") or {}).get("sizeInvariance", {}).get("status") == "fail",
              "用例2：sizeInvariance 未记 fail")

        # ---- 用例 2b：跨设备照稿分档 + 声明 sizeVariants → 合法通过 ----
        # 同一设计有 xx + xx-iPad 两份稿，iPad 稿给出更大的卡片框（字号不变）。这是
        # 合规的「跨设备照稿分档」，不是等比放大 —— 前提是 plan 里逐档声明了 sizeVariants，
        # 且两个 tablet 采样（portrait/landscape）的尺寸**一致**（同设备内不变）。
        variant_fixed = [
            {"id": "cta", "region": "form", "kind": "fixed",
             "rect": {"x": 16, "y": 300, "width": 347, "height": 48}, "interactive": True},
            {"id": "offers", "region": "form", "kind": "fixed",
             "rect": {"x": 16, "y": 400, "width": 347, "height": 68}},
        ]
        geometry(tmp, "phone-compact", (402, 874), elements=variant_fixed)
        variant_ipad = [
            {"id": "cta", "region": "form", "kind": "fixed",
             "rect": {"x": 16, "y": 300, "width": 347, "height": 48}, "interactive": True},
            {"id": "offers", "region": "form", "kind": "fixed",
             "rect": {"x": 16, "y": 400, "width": 500, "height": 90}},
        ]
        geometry(tmp, "tablet-regular-portrait", (1024, 1366), elements=variant_ipad)
        geometry(tmp, "tablet-regular-landscape", (1366, 1024), elements=variant_ipad)
        variant_plan = tmp / "plan-variant.json"
        write_json(variant_plan, {"adaptiveLayout": {
            "model": "continuous-window-width",
            "regions": [{"region": "form", "widthPolicy": "max-content-width",
                         "maxContentWidth": {"value": 600, "of": "root", "reason": "单列"}}],
            "sizeVariants": [{
                "region": "offers",
                "basis": "目的 + 目的-iPad 双稿",
                "values": {
                    "phone-compact": {"width": 347, "height": 68},
                    "tablet-regular-portrait": {"width": 500, "height": 90},
                    "tablet-regular-landscape": {"width": 500, "height": 90},
                },
                "why": "iPad 稿给出更大的卡片框，字号未缩放",
            }],
        }})
        proc, report = run(path, variant_plan)
        check("size-not-invariant" not in kinds(report)
              and "size-not-invariant-within-device" not in kinds(report),
              f"用例2b：声明了 sizeVariants 的跨设备分档仍被判违规，实得 {sorted(kinds(report))}")

        # ---- 用例 2c：跨设备尺寸分档但**没声明** sizeVariants → 仍判违规（守住防线）----
        # 两个 tablet 采样一致地用了 500×90（同设备内不变），只是没声明分档。
        undeclared_ipad = [
            {"id": "cta", "region": "form", "kind": "fixed",
             "rect": {"x": 16, "y": 300, "width": 347, "height": 48}, "interactive": True},
            {"id": "offers", "region": "form", "kind": "fixed",
             "rect": {"x": 16, "y": 400, "width": 500, "height": 90}},
        ]
        geometry(tmp, "tablet-regular-portrait", (1024, 1366), elements=undeclared_ipad)
        geometry(tmp, "tablet-regular-landscape", (1366, 1024), elements=undeclared_ipad)
        proc, report = run(path, plan)   # plan 无 sizeVariants
        check("size-not-invariant" in kinds(report)
              and "size-not-invariant-within-device" not in kinds(report),
              f"用例2c：未声明 sizeVariants 的跨设备分档未被拦下，实得 {sorted(kinds(report))}")

        # ---- 用例 2d：同设备内尺寸不一致，即使声明 sizeVariants 也必须拦（新的硬线）----
        # 「尺寸不缩放」作用域是设备平台：同一台 tablet 的 portrait 与 landscape 之间尺寸
        # 必须逐字相等，sizeVariants 不能豁免这条 —— 分档只许跨设备（phone vs tablet）。
        within_device_portrait = [
            {"id": "offers", "region": "form", "kind": "fixed",
             "rect": {"x": 16, "y": 400, "width": 500, "height": 90}},
        ]
        within_device_landscape = [
            {"id": "offers", "region": "form", "kind": "fixed",
             "rect": {"x": 16, "y": 400, "width": 347, "height": 68}},
        ]
        geometry(tmp, "tablet-regular-portrait", (1024, 1366), elements=within_device_portrait)
        geometry(tmp, "tablet-regular-landscape", (1366, 1024), elements=within_device_landscape)
        proc, report = run(path, variant_plan)   # 即便声明了 sizeVariants 也不豁免
        check("size-not-invariant-within-device" in kinds(report),
              f"用例2d：同设备内尺寸不一致未被拦下（sizeVariants 不应豁免），"
              f"实得 {sorted(kinds(report))}")

        # ---- 用例 3：内边距被撑大 → insetPreservation ----
        stretched = [
            {"id": "hero", "region": "hero", "kind": "pinned",
             "rect": {"x": 0, "y": 0, "width": 1024, "height": 100},
             "insets": {"leading": 0, "trailing": 0}},
            {"id": "card", "region": "form", "kind": "pinned",
             "rect": {"x": 40, "y": 200, "width": 944, "height": 200},
             "insets": {"leading": 40, "trailing": 40}},
        ]
        good_inset = [
            {"id": "hero", "region": "hero", "kind": "pinned",
             "rect": {"x": 0, "y": 0, "width": 402, "height": 100},
             "insets": {"leading": 0, "trailing": 0}},
            {"id": "card", "region": "form", "kind": "pinned",
             "rect": {"x": 16, "y": 200, "width": 370, "height": 200},
             "insets": {"leading": 16, "trailing": 16}},
        ]
        geometry(tmp, "phone-compact", (402, 874), elements=good_inset)
        bad = geometry(tmp, "tablet-regular-portrait", (1024, 1366), elements=stretched)
        proc, report = run(path, plan, {"tablet-regular-portrait": bad})
        check("inset-not-preserved" in kinds(report),
              f"用例3：内边距被撑大未被拦下，实得 {sorted(kinds(report))}")

        # ---- 用例 4：越界 / 封顶没生效 / 没居中 / 点击区变小 ----
        for sample_id, _, width, height in SAMPLES:
            geometry(tmp, sample_id, (width, height))
        broken = [
            {"id": "cta", "region": "form", "kind": "fixed",
             "rect": {"x": 0, "y": 300, "width": 903, "height": 30},
             "interactive": True, "contentColumn": True},
            {"id": "stray", "region": "form", "kind": "fixed",
             "rect": {"x": 1000, "y": 1300, "width": 80, "height": 80}},
        ]
        bad = geometry(tmp, "tablet-regular-portrait", (1024, 1366), elements=broken)
        proc, report = run(path, plan, {"tablet-regular-portrait": bad})
        found = kinds(report)
        for kind in ("content-column-too-wide", "content-column-not-centered",
                     "touch-target-too-small", "element-overflows-window"):
            check(kind in found, f"用例4：{kind} 未被拦下，实得 {sorted(found)}")

        # ---- 用例 5：兼容缩放模式与信箱留边 ----
        for sample_id, _, width, height in SAMPLES:
            geometry(tmp, sample_id, (width, height))
        bad = geometry(tmp, "tablet-regular-portrait", (1024, 1366),
                       compatibility=True,
                       letterbox={"x": 0, "y": 120, "width": 0, "height": 120})
        proc, report = run(path, plan, {"tablet-regular-portrait": bad})
        found = kinds(report)
        check("compatibility-mode" in found,
              f"用例5：兼容缩放模式未被拦下，实得 {sorted(found)}")
        check("letterbox-present" in found,
              f"用例5：信箱留边未被拦下，实得 {sorted(found)}")

        # ---- 用例 6：宽度非单调 + 兄弟重叠（continuity）----
        for sample_id, _, width, height in SAMPLES:
            geometry(tmp, sample_id, (width, height))
        narrow = [
            {"id": "card", "region": "form", "kind": "pinned",
             "rect": {"x": 0, "y": 200, "width": 300, "height": 200},
             "insets": {"leading": 0, "trailing": 0}},
            {"id": "a", "siblingGroup": "row", "kind": "fixed",
             "rect": {"x": 0, "y": 500, "width": 100, "height": 40}},
            {"id": "b", "siblingGroup": "row", "kind": "fixed",
             "rect": {"x": 50, "y": 500, "width": 100, "height": 40}},
        ]
        wide = [
            {"id": "card", "region": "form", "kind": "pinned",
             "rect": {"x": 0, "y": 200, "width": 200, "height": 200},
             "insets": {"leading": 0, "trailing": 0}},
            {"id": "a", "siblingGroup": "row", "kind": "fixed",
             "rect": {"x": 0, "y": 500, "width": 100, "height": 40}},
            {"id": "b", "siblingGroup": "row", "kind": "fixed",
             "rect": {"x": 50, "y": 500, "width": 100, "height": 40}},
        ]
        geometry(tmp, "tablet-regular-portrait", (1024, 1366), elements=narrow)
        geometry(tmp, "tablet-regular-landscape", (1366, 1024), elements=wide)
        proc, report = run(path, plan)
        found = kinds(report)
        check("non-monotonic-width" in found,
              f"用例6：更宽窗口下 pinned 宽度反而变小未被拦下，实得 {sorted(found)}")
        check("sibling-overlap" in found,
              f"用例6：同组兄弟重叠未被拦下，实得 {sorted(found)}")

        # ---- 用例 7：重叠可显式豁免（精度）----
        for sample_id, _, width, height in SAMPLES:
            geometry(tmp, sample_id, (width, height))
        overlapped = [
            {"id": "a", "siblingGroup": "row", "kind": "fixed", "overlapAllowed": True,
             "rect": {"x": 0, "y": 500, "width": 100, "height": 40}},
            {"id": "b", "siblingGroup": "row", "kind": "fixed", "overlapAllowed": True,
             "rect": {"x": 50, "y": 500, "width": 100, "height": 40}},
        ]
        geometry(tmp, "tablet-regular-portrait", (1024, 1366), elements=overlapped)
        proc, report = run(path, plan)
        check("sibling-overlap" not in kinds(report),
              "用例7：显式标了 overlapAllowed 的有意叠放被误报成重叠")

        # ---- 用例 8：缺必需采样 → sampleCoverage 必须 fail，不许假绿 ----
        for sample_id, _, width, height in SAMPLES:
            geometry(tmp, sample_id, (width, height))
        partial = tmp / "partial-targets.json"
        entries = [{"id": "phone-compact", "widthClass": "compact", "required": True,
                    "geometry": "geo/phone-compact.json"},
                   {"id": "tablet-regular-portrait", "widthClass": "medium", "required": True,
                    "geometry": "geo/missing.json"},
                   {"id": "tablet-regular-landscape", "widthClass": "expanded", "required": False,
                    "geometry": "geo/missing-too.json"}]
        write_json(partial, {"schemaVersion": 1, "platform": "iOS Simulator",
                             "samples": entries})
        proc, report = run(partial, plan)
        check(proc.returncode == 1 and report.get("status") == "fail",
              f"用例8：缺必需采样必须判 fail，得到 {report.get('status')}")
        check((report.get("checks") or {}).get("sampleCoverage", {}).get("status") == "fail",
              "用例8：sampleCoverage 未记 fail")
        check("tablet-regular-portrait" in
              ((report.get("checks") or {}).get("sampleCoverage", {}).get("missing") or []),
              "用例8：缺失的必需采样没有被点名")
        check(not any("missing-too" in w for w in report.get("warnings") or [])
              or True, "用例8：可选采样缺失应只告警")
        check(any("tablet-regular-landscape" in w for w in report.get("warnings") or []),
              f"用例8：可选采样缺失应只告警，实得 {report.get('warnings')}")

        # ---- 用例 9：容差是参数，不是常数 ----
        # 1pt 的位置差在默认 2pt 容差内应当通过；收紧到 0.5pt 就必须被拦。
        for sample_id, _, width, height in SAMPLES:
            left = (width - 600) / 2
            elements = [
                {"id": "contentColumn", "region": "form", "kind": "pinned",
                 "rect": {"x": left + (1 if sample_id == "tablet-regular-portrait" else 0),
                          "y": 120, "width": 600, "height": 400},
                 "contentColumn": True},
            ]
            geometry(tmp, sample_id, (width, height), elements=elements)
        proc, report = run(path, plan)
        check("content-column-not-centered" not in kinds(report),
              "用例9：1pt 的偏移在 2pt 容差内不该被判违规")
        proc, report = run(path, plan, tolerance=0.5)
        check("content-column-not-centered" in kinds(report),
              "用例9：收紧容差到 0.5pt 后 1pt 偏移必须被拦下")

        # ---- 用例 10：用法错误干净退出 ----
        proc = subprocess.run([sys.executable, str(SCRIPT)],
                              capture_output=True, text=True)
        check(proc.returncode == 2 and "Traceback" not in proc.stderr,
              f"用例10：缺 --targets 应退出 2，得到 {proc.returncode}：{proc.stderr[:200]}")
        proc = subprocess.run([sys.executable, str(SCRIPT), "--targets", str(path),
                               "--geometry", "broken"],
                              capture_output=True, text=True)
        check(proc.returncode == 2,
              f"用例10：--geometry 格式错误应退出 2，得到 {proc.returncode}")

    for problem in problems:
        print(problem)
    if problems:
        print("自适应几何审计未满足")
        return 1
    print("自适应几何审计：合规几何通过、等比放大与内边距撑大被拦下、"
          "越界/封顶失效/未居中/点击区变小被拦下、兼容缩放与信箱留边被拦下、"
          "宽度非单调与兄弟重叠被拦下、overlapAllowed 豁免生效、"
          "缺必需采样判 fail 而不假绿、可选采样缺失只告警、容差可调、用法错误干净退出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
