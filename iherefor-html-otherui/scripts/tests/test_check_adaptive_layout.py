#!/usr/bin/env python3
"""回归：宽度轴（平板 / 大屏 / 分屏）的静态核对。

``check_adaptive_layout.py`` 是 ``check_layout_proportions.py`` 的姊妹：那个管尺寸轴与
位置轴，这个管宽度轴。**两边都要有「必须过 / 必须挂」** —— 只验合规会漏掉召回，
只验违规会把「照设计稿做」判成错的。

每一条断言都对应一类真实会踩的坑，所以测试里同时盯两头：

* **召回**：``UIScreen.main.bounds``、``DisplayMetrics``、方向锁、``UIRequiresFullScreen``、
  声明封顶却没封顶原语、声明网格却写死列数 —— 都要被点名；
* **精度**：``view.bounds``、``values-sw600dp``、``maxContentWidth``、``full-bleed``
  这些**正确做法**不得被误报。误报比漏报更伤：它会训练出「看到告警就忽略」的习惯。

计划层同样两头都查：``stretch-full-width`` 必须挂（单列拉满是本契约要拦的头号问题），
而 ``full-bleed`` / ``max-content-width`` / ``grid`` / ``pane`` 必须过。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_adaptive_layout.py"


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path, payload):
    write(path, json.dumps(payload, indent=2, ensure_ascii=False))


def good_plan():
    """一份合规的宽度轴声明：四个采样覆盖三个宽度档。"""
    return {
        "adaptiveLayout": {
            "model": "continuous-window-width",
            "windowSamples": [
                {"id": "phone-compact", "widthClass": "compact",
                 "width": 393, "height": 852},
                {"id": "tablet-regular-portrait", "widthClass": "medium",
                 "width": 1024, "height": 1366},
                {"id": "tablet-regular-landscape", "widthClass": "expanded",
                 "width": 1366, "height": 1024},
                {"id": "phone-regular-landscape", "widthClass": "medium",
                 "width": 852, "height": 393, "required": False},
            ],
            "firstLevelWidthClass": "compact",
            "regions": [
                {"region": "hero", "widthPolicy": "full-bleed",
                 "reason": "HTML 事实为四边贴 0"},
                {"region": "form", "widthPolicy": "max-content-width",
                 "maxContentWidth": {"value": 600, "of": "root",
                                     "reason": "单列表单拉满会破坏阅读节奏"}},
            ],
            "forbiddenAdaptations": ["uniform-scale", "stretch-full-width", "font-scale"],
        }
    }


GOOD_SWIFT = """
import UIKit

final class FormView: UIView {
    private let contentMaxWidth: CGFloat = 600

    override func layoutSubviews() {
        super.layoutSubviews()
        // 用自身 bounds 而不是 UIScreen.main：分屏与自由窗口下后者返回整块屏
        let columnWidth = min(bounds.width, contentMaxWidth)
        _ = columnWidth
    }
}
"""


def run(plan, source=None, extra=None, plan_only=False):
    report_path = Path(plan).with_suffix(".report.json")
    if report_path.is_file():
        report_path.unlink()   # 不删就会读到上一轮的结论，把「本次崩了」伪装成「上次的结果」
    args = [sys.executable, str(SCRIPT), "--plan", str(plan), "--output", str(report_path)]
    if plan_only:
        args.append("--plan-only")
    for root in source or []:
        args += ["--source", str(root)]
    args += extra or []
    proc = subprocess.run(args, capture_output=True, text=True)
    if "Traceback" in proc.stderr:
        raise AssertionError(f"校验器抛栈：{proc.stderr.strip()[-600:]}")
    report = json.loads(report_path.read_text()) if report_path.is_file() else {}
    return proc, report


def kinds(report):
    return {item.get("kind") for item in report.get("violations") or []}


def main():
    problems = []

    def check(condition, message):
        if not condition:
            problems.append(message)

    with tempfile.TemporaryDirectory() as scratch:
        tmp = Path(scratch)
        src = tmp / "src"

        # ---- 用例 1：合规计划 + 合规源码 → 必须过 ----
        plan = tmp / "plan.json"
        write_json(plan, good_plan())
        write(src / "FormView.swift", GOOD_SWIFT)
        proc, report = run(plan, [src])
        check(proc.returncode == 0 and report.get("status") == "pass",
              f"用例1：合规声明与源码应判 pass，得到 {report.get('status')}"
              f"（{report.get('violations')}）：{proc.stdout[:300]}")
        check(report.get("checkedFiles") == 1,
              f"用例1：应核对到 1 个源码文件，得到 {report.get('checkedFiles')}")

        # ---- 用例 2：未声明宽度轴 → 不硬判，但必须说出来 ----
        none_plan = tmp / "none.json"
        write_json(none_plan, {"schemaVersion": 1})
        proc, report = run(none_plan, [src], plan_only=True)
        check(proc.returncode == 0 and report.get("status") == "not-declared",
              f"用例2：未声明 adaptiveLayout 应判 not-declared 且不违规，"
              f"得到 {report.get('status')} / {report.get('violations')}")
        check(any("adaptiveLayout" in w for w in report.get("warnings") or []),
              "用例2：未声明宽度轴必须留下告警 —— 那是「本页只交付手机档」的显式表态，"
              "不能静默")

        # ---- 用例 2b：工程声称支持 iPad 却没有宽度轴声明 → 只告警、不硬判，且按文件去重 ----
        # project.pbxproj 里 TARGETED_DEVICE_FAMILY 每个 build configuration 出现一次，
        # 逐条报会刷出六条一模一样的告警 —— 重复告警会训练出「看到告警就忽略」的习惯。
        family_src = tmp / "family-src"
        write(family_src / "FormView.swift", GOOD_SWIFT)
        write(family_src / "project.pbxproj",
              "TARGETED_DEVICE_FAMILY = \"1,2\";\n" * 6)
        proc, report = run(none_plan, [family_src])
        check(proc.returncode == 0 and report.get("status") == "not-declared",
              f"用例2b：声称支持 iPad 但没声明宽度轴应只告警不硬判，"
              f"得到 {report.get('status')} / {report.get('violations')}")
        family_warnings = [w for w in report.get("warnings") or []
                           if "TARGETED_DEVICE_FAMILY" in w]
        check(len(family_warnings) == 1,
              f"用例2b：设备族告警应每个文件只说一次，实得 {len(family_warnings)} 条")

        # ---- 用例 3：计划硬伤逐条拦下 ----
        bad = good_plan()
        layout = bad["adaptiveLayout"]
        layout["model"] = "two-breakpoints"
        layout["windowSamples"] = [{"id": "phone", "widthClass": "compact", "width": 393}]
        layout["forbiddenAdaptations"] = ["uniform-scale"]
        layout["regions"] = [
            {"region": "list", "widthPolicy": "stretch-full-width"},
            {"region": "form", "widthPolicy": "max-content-width"},
            {"region": "grid", "widthPolicy": "grid",
             "columnCount": {"compact": 2, "medium": 1, "expanded": 3}},
        ]
        bad_plan_path = tmp / "bad-plan.json"
        write_json(bad_plan_path, bad)
        proc, report = run(bad_plan_path, plan_only=True)
        found = kinds(report)
        for kind in ("adaptive-model-mismatch", "too-few-window-samples",
                     "window-class-uncovered", "forbidden-adaptations-incomplete",
                     "stretch-full-width-not-a-policy", "missing-max-content-width",
                     "column-count-not-monotonic"):
            check(kind in found,
                  f"用例3：计划硬伤 {kind} 未被报出，实得 {sorted(found)}")
        check(proc.returncode == 1,
              f"用例3：存在计划硬伤时应退出 1，得到 {proc.returncode}")

        # ---- 用例 4：源码四类禁止模式逐条拦下 ----
        bad_src = tmp / "bad-src"
        write(bad_src / "BadView.swift", """
import UIKit

final class BadView: UIView {
    override func layoutSubviews() {
        super.layoutSubviews()
        let screenWidth = UIScreen.main.bounds.width
        let scale = bounds.width / 393
        _ = (screenWidth, scale)
    }
}
""")
        write(bad_src / "MainActivity.kt", """
package demo

import android.util.DisplayMetrics

class MainActivity {
    fun width(dm: DisplayMetrics): Int = dm.widthPixels
}
""")
        write(bad_src / "AndroidManifest.xml",
              '<manifest><application><activity android:screenOrientation="portrait" />'
              "</application></manifest>\n")
        write(bad_src / "Info.plist", """<dict>
  <key>UISupportedInterfaceOrientations</key>
  <array>
    <string>UIInterfaceOrientationPortrait</string>
  </array>
</dict>
""")
        proc, report = run(plan, [bad_src])
        found = kinds(report)
        for kind in ("screen-as-layout-source", "display-metrics-as-layout-source",
                     "orientation-locked", "missing-max-content-width-idiom"):
            check(kind in found,
                  f"用例4：源码禁止模式 {kind} 未被报出，实得 {sorted(found)}")
        check(proc.returncode == 1,
              f"用例4：源码违规时应退出 1，得到 {proc.returncode}")

        # ---- 用例 5：UIRequiresFullScreen 单独一条（它会直接退出分屏支持）----
        full = tmp / "full-src"
        write(full / "Info.plist", """<dict>
  <key>UIRequiresFullScreen</key>
  <true/>
  <key>UISupportedInterfaceOrientations</key>
  <array>
    <string>UIInterfaceOrientationPortrait</string>
    <string>UIInterfaceOrientationLandscapeLeft</string>
  </array>
</dict>
""")
        write(full / "FormView.swift", GOOD_SWIFT)
        proc, report = run(plan, [full])
        found = kinds(report)
        check("requires-full-screen" in found,
              f"用例5：UIRequiresFullScreen 未被报出，实得 {sorted(found)}")
        check("orientation-locked" not in found,
              "用例5：方向集含 LandscapeLeft 时不应判 orientation-locked —— "
              "那不是锁死，是「两种方向都支持」")

        # ---- 用例 5b：iPhone 竖屏 + iPad 全方向是**合法组合**，不得误报 ----
        # 这是 iOS 上很常见的一种声明方式（手机保持竖屏，平板放开）。见到 Portrait
        # 就报会把它一起误报掉，而假告警会训练出「看到告警就忽略」的习惯。
        per_idiom = tmp / "per-idiom-src"
        write(per_idiom / "Info.plist", """<dict>
  <key>UISupportedInterfaceOrientations</key>
  <array>
    <string>UIInterfaceOrientationPortrait</string>
  </array>
  <key>UISupportedInterfaceOrientations~ipad</key>
  <array>
    <string>UIInterfaceOrientationPortrait</string>
    <string>UIInterfaceOrientationLandscapeLeft</string>
    <string>UIInterfaceOrientationLandscapeRight</string>
  </array>
</dict>
""")
        write(per_idiom / "FormView.swift", GOOD_SWIFT)
        proc, report = run(plan, [per_idiom])
        found = kinds(report)
        check("orientation-locked" not in found,
              f"用例5b：iPhone 竖屏 + iPad 全方向的合法组合被误报：{sorted(found)}")
        check(not any("~ipad" in w for w in report.get("warnings") or []),
              f"用例5b：已声明 ~ipad 方向集却仍告警缺它：{report.get('warnings')}")

        # ---- 用例 6：精度 —— 正确做法不得被误报 ----
        # view.bounds / values-sw600dp / maxContentWidth 都是正确答案，误报比漏报更伤。
        good_src = tmp / "good-src"
        write(good_src / "FormView.swift", GOOD_SWIFT)
        write(good_src / "res" / "values" / "dimens.xml",
              '<resources><dimen name="content_max_width">0dp</dimen></resources>\n')
        write(good_src / "res" / "values-sw600dp" / "dimens.xml",
              '<resources><dimen name="content_max_width">600dp</dimen></resources>\n')
        write(good_src / "layout" / "form.xml",
              '<androidx.constraintlayout.widget.ConstraintLayout '
              'android:layout_width="0dp" '
              'app:layout_constraintWidth_max="@dimen/content_max_width" />\n')
        proc, report = run(plan, [good_src])
        check(report.get("violations") == [],
              f"用例6：合规做法被误报：{report.get('violations')}")
        check(not any("values-sw600dp" in w for w in report.get("warnings") or []),
              f"用例6：values-sw600dp 已存在却仍告警缺资源目录：{report.get('warnings')}")

        # ---- 用例 7：声明 grid 却写死列数 ----
        grid_plan = good_plan()
        grid_plan["adaptiveLayout"]["regions"].append(
            {"region": "gallery", "widthPolicy": "grid",
             "columnCount": {"compact": 1, "medium": 2, "expanded": 3}})
        grid_path = tmp / "grid-plan.json"
        write_json(grid_path, grid_plan)
        grid_src = tmp / "grid-src"
        write(grid_src / "Gallery.kt",
              "val grid = LazyVerticalGrid(columns = GridCells.Fixed(2))\n")
        write(grid_src / "FormView.swift", GOOD_SWIFT)
        proc, report = run(grid_path, [grid_src])
        check("fixed-column-count" in kinds(report),
              f"用例7：GridCells.Fixed 未被报出，实得 {sorted(kinds(report))}")

        # ---- 用例 8：targets 缺采样 ----
        targets = tmp / "adaptive-targets.json"
        write_json(targets, {"schemaVersion": 1, "platform": "iOS Simulator",
                             "samples": [{"id": "phone-compact", "required": True,
                                          "geometry": "actual/geometry-phone-compact.json"}]})
        proc, report = run(plan, extra=["--targets", str(targets)])
        check("targets-missing-samples" in kinds(report),
              f"用例8：计划采样没有落成目标时未被报出，实得 {sorted(kinds(report))}")

        # ---- 用例 9：用法错误干净退出 ----
        proc = subprocess.run([sys.executable, str(SCRIPT)],
                              capture_output=True, text=True)
        check(proc.returncode == 2 and "Traceback" not in proc.stderr,
              f"用例9：缺 --plan 应退出 2，得到 {proc.returncode}：{proc.stderr[:200]}")

        # ---- 用例 10：计划文件不存在 → 退出 2，且不抛栈 ----
        proc, report = run(tmp / "nope.json")
        check(proc.returncode == 2 and "Traceback" not in proc.stderr,
              f"用例10：计划不存在应退出 2，得到 {proc.returncode}：{proc.stderr[:200]}")

    for problem in problems:
        print(problem)
    if problems:
        print("宽度轴静态核对未满足")
        return 1
    print("宽度轴静态核对：合规声明与源码通过、未声明时留告警不硬判、"
          "计划硬伤（断点口径/采样不足/档未覆盖/禁止清单不全/拉满/缺封顶值/列数非单调）"
          "逐条拦下、源码四类禁止模式与 UIRequiresFullScreen 拦下、"
          "iPhone 竖屏 + iPad 全方向的合法组合不误报、"
          "view.bounds 与 values-sw600dp 等正确做法不误报、固定列数与缺采样拦下、"
          "用法错误干净退出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
