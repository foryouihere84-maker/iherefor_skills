#!/usr/bin/env python3
"""回归：对齐审计必须能从「已知真值」的合成图里还原出位移与比例。

为什么用合成图而不是事故现场图。事故图只能证明「审计说出了正确的话」，不能证明
「审计的数学是对的」—— 现场没有 ground truth，谁也不知道真实的 dy 到底是多少。所以
另造一批**参数已知**的图：先画基准图，再按已知的 ``(slope, intercept)`` 变形出实测图，
然后要求审计把这两个参数还原回来。还原不回来就是审计有 bug，不是数据有问题。

同时钉住一个恒真式陷阱。``domVsReference`` 若用模板匹配实现（模板取自 reference
自身再回 reference 里找），``(dx, dy)`` 恒为 ``(0, 0)``、``status`` 恒为 ``aligned``，
永远给出「DOM 与基准图一致」的假保证。用例 5/6 故意把 page-facts 的预测框整体平移/
缩放（等价于「基准图不是事实表采集时那个 viewport 下渲染的」），要求审计必须报出来。
没有这两个用例，恒真式实现也能让前四个用例全绿。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "tests"))

import alignment_fixture as fixture  # noqa: E402

SCRIPT = ROOT / "scripts" / "audit_alignment.py"


def run_audit(case_dir, out_path, extra=()):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--reference", str(case_dir / "reference.png"),
         "--actual", str(case_dir / "actual.png"),
         "--page-facts", str(case_dir / "page-facts.json"),
         "--transform", str(case_dir / "canvas-transform.json"),
         "--output", str(out_path), "--quiet", *extra],
        capture_output=True, text=True,
    )
    data = json.loads(out_path.read_text()) if out_path.exists() else None
    return proc, data


def mutate_page_facts(case_dir, dy_pt=0.0, scale=1.0):
    """把页面事实表的预测框整体平移/缩放，模拟「基准图与事实表采集条件不一致」。

    本夹具里画布 == 设备、CSS px == 设备点，所以 dy_pt 就是 CSS px 的平移量。
    """
    path = case_dir / "page-facts.json"
    facts = json.loads(path.read_text())
    dpr = facts["viewport"]["devicePixelRatio"]
    for element in facts["elements"]:
        rect = element["rectInReference"]
        rect["x"] = rect["x"] * scale
        rect["y"] = rect["y"] * scale + dy_pt * dpr
        rect["width"] *= scale
        rect["height"] *= scale
        for box in (element.get("textMetrics") or {}).get("rects") or []:
            box["x"] = box["x"] * scale
            box["y"] = box["y"] * scale + dy_pt
            box["width"] *= scale
            box["height"] *= scale
    path.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")


def check(problems, label, condition, message):
    if not condition:
        problems.append(f"{label}：{message}")


def main():
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # ---- 用例 1：完全对齐。真值 slope=0, intercept=0 ----
        case = tmp / "aligned"
        fixture.write_case(case, slope=0.0, intercept_pt=0.0)
        proc, data = run_audit(case, tmp / "aligned.json")
        if data is None:
            problems.append("用例1：未生成 alignment.json；stderr=" + proc.stderr[-400:])
        else:
            check(problems, "用例1", data.get("status") == "aligned",
                  f"完全对齐被判为 {data.get('status')!r} / {data.get('reason')!r}，必须为 'aligned'")
            check(problems, "用例1", proc.returncode == 0,
                  f"完全对齐的退出码为 {proc.returncode}，必须为 0")
            # 基准图与 DOM 一致时不能误报
            dom = data["comparisons"]["domVsReference"]
            check(problems, "用例1", dom.get("status") == "aligned",
                  f"基准图与 DOM 一致却被判为 {dom.get('status')!r} / {dom.get('reason')!r}")

        # ---- 用例 2：纯平移 +5pt。真值 slope=0, intercept=+5 ----
        case = tmp / "const-shift"
        fixture.write_case(case, slope=0.0, intercept_pt=5.0)
        proc, data = run_audit(case, tmp / "const-shift.json")
        if data is None:
            problems.append("用例2：未生成 alignment.json；stderr=" + proc.stderr[-400:])
        else:
            ref = data["comparisons"]["referenceVsActual"]
            check(problems, "用例2", ref.get("status") == "needs-review"
                  and ref.get("reason") == "constant-offset",
                  f"纯平移 5pt 被判为 {ref.get('status')!r} / {ref.get('reason')!r}，"
                  "必须为 needs-review/constant-offset")
            fit = ref.get("offsetFit") or {}
            got = fit.get("intercept")
            check(problems, "用例2", got is not None and abs(got - 5.0) <= 1.0,
                  f"平移量还原为 {got}pt，真值 5.0pt（容差 1pt）")
            slope = fit.get("slope")
            check(problems, "用例2", slope is not None and abs(slope) <= 0.002,
                  f"纯平移却报出斜率 {slope}")

        # ---- 用例 3：纯缩放 1.003。真值 slope=+0.003, intercept=0 ----
        case = tmp / "scale"
        fixture.write_case(case, slope=0.003, intercept_pt=0.0)
        proc, data = run_audit(case, tmp / "scale.json")
        if data is None:
            problems.append("用例3：未生成 alignment.json；stderr=" + proc.stderr[-400:])
        else:
            ref = data["comparisons"]["referenceVsActual"]
            check(problems, "用例3", ref.get("status") == "needs-review"
                  and ref.get("reason") == "scale-mismatch",
                  f"0.3% 比例差被判为 {ref.get('status')!r} / {ref.get('reason')!r}，"
                  "必须为 needs-review/scale-mismatch")
            # 带级拟合是斜率的主证据（元素级在小文本上易歧义）
            band = ((ref.get("bandRobust") or {}).get("offsetFit")) or {}
            got = band.get("impliedScale")
            check(problems, "用例3", got is not None and abs(got - 1.003) <= 0.0015,
                  f"带级隐含比例还原为 {got}，真值 1.003（容差 0.0015）")
            check(problems, "用例3", (band.get("t") or 0) >= 3.0,
                  f"带级斜率信噪比 t={band.get('t')}，应 >= 3")

        # ---- 用例 4：缩放 + 平移。真值 slope=+0.0025, intercept=+4pt ----
        case = tmp / "scale-shift"
        fixture.write_case(case, slope=0.0025, intercept_pt=4.0)
        proc, data = run_audit(case, tmp / "scale-shift.json")
        if data is None:
            problems.append("用例4：未生成 alignment.json；stderr=" + proc.stderr[-400:])
        else:
            ref = data["comparisons"]["referenceVsActual"]
            check(problems, "用例4", ref.get("reason") == "scale-mismatch",
                  f"缩放+平移被判为 {ref.get('reason')!r}，缩放应优先于平移被报出")
            fit = ref.get("offsetFit") or {}
            got = fit.get("intercept")
            check(problems, "用例4", got is not None and abs(got - 4.0) <= 1.5,
                  f"平移分量还原为 {got}pt，真值 4.0pt（容差 1.5pt）")

        # ---- 用例 5：基准图与 DOM 事实不符（整体平移）—— 反恒真式 ----
        case = tmp / "dom-shift"
        fixture.write_case(case, slope=0.0, intercept_pt=0.0)
        mutate_page_facts(case, dy_pt=20.0)
        proc, data = run_audit(case, tmp / "dom-shift.json")
        if data is None:
            problems.append("用例5：未生成 alignment.json；stderr=" + proc.stderr[-400:])
        else:
            dom = data["comparisons"]["domVsReference"]
            check(problems, "用例5", dom.get("status") != "aligned",
                  "事实表预测框整体偏 20pt，基准图与 DOM 的不一致却没被报出来"
                  "（这是恒真式实现的典型症状）")
            check(problems, "用例5", data.get("reason") == "baseline-disagrees-with-dom",
                  f"总体判词为 {data.get('reason')!r}，必须为 'baseline-disagrees-with-dom'")
            check(problems, "用例5", data.get("status") == "needs-review",
                  f"总体状态为 {data.get('status')!r}，必须为 'needs-review'")
            trust = data.get("trust") or ""
            check(problems, "用例5", "DOM" in trust,
                  f"应指认该信 DOM，实际 trust={trust!r}")

        # ---- 用例 6：基准图与 DOM 事实不符（整体缩放）—— 反恒真式 ----
        case = tmp / "dom-scale"
        fixture.write_case(case, slope=0.0, intercept_pt=0.0)
        mutate_page_facts(case, scale=1.06)
        proc, data = run_audit(case, tmp / "dom-scale.json")
        if data is None:
            problems.append("用例6：未生成 alignment.json；stderr=" + proc.stderr[-400:])
        else:
            dom = data["comparisons"]["domVsReference"]
            check(problems, "用例6", dom.get("status") != "aligned",
                  "事实表预测框整体放大 6%，基准图与 DOM 的不一致却没被报出来")
            check(problems, "用例6", data.get("reason") == "baseline-disagrees-with-dom",
                  f"总体判词为 {data.get('reason')!r}，必须为 'baseline-disagrees-with-dom'")

        # ---- 用例 7：基准图不在设备画布上时必须出警告，而不是默默通过 ----
        case = tmp / "aligned"
        proc, data = run_audit(case, tmp / "canvas.json", extra=(
            "--runtime-device", str(ROOT / "scripts" / "tests" / "fixtures" / "runtime-device.json"),))
        if data is None:
            problems.append("用例7：未生成 alignment.json；stderr=" + proc.stderr[-400:])
        else:
            check(problems, "用例7", data.get("referenceOnDeviceCanvas") is False,
                  "基准图 400x800 不在设备画布 1206x2622 上，却未标记 referenceOnDeviceCanvas=false")
            check(problems, "用例7", any("不在设备画布上" in w for w in data.get("warnings") or []),
                  "缺少「基准图不在设备画布上」的警告")

        # ---- 用例 8：纯横向错位时，结论必须报「横向」而不是报一个不存在的纵向位移 ----
        # 真值 slope=0, intercept=0, 横向 +10pt。
        # 这里钉的是一个**文案**缺陷（但代价很实在）：触发条件是三个数的最大值
        # max(|intercept|, maxAbsDy, maxAbsDx)，而消息原来只报纵向的 intercept 与
        # maxAbsDy。于是纯横向错位会输出成「常数位移 +0.00pt（最大 0.01pt），超容差
        # 2.0pt」—— 自相矛盾，看的人会先怀疑工具坏了，从而放过一个真实的横向错位。
        # 事故页就正好踩在这个形态上：页脚 Terms 横向差 12pt。
        case = tmp / "shift-x"
        fixture.write_case(case, slope=0.0, intercept_pt=0.0, shift_x_pt=10.0)
        proc, data = run_audit(case, tmp / "shift-x.json")
        if data is None:
            problems.append("用例8：未生成 alignment.json；stderr=" + proc.stderr[-400:])
        else:
            ref = data["comparisons"]["referenceVsActual"]
            check(problems, "用例8", ref.get("status") == "needs-review"
                  and ref.get("reason") == "constant-offset",
                  f"纯横向错位被判为 {ref.get('status')!r} / {ref.get('reason')!r}，"
                  "必须为 needs-review/constant-offset")
            extremes = ref.get("extremes") or {}
            got_dx = extremes.get("maxAbsDx")
            check(problems, "用例8", got_dx is not None and abs(got_dx - 10.0) <= 1.5,
                  f"横向位移还原为 {got_dx}pt，真值 10.0pt（容差 1.5pt）")
            got_dy = extremes.get("maxAbsDy")
            check(problems, "用例8", got_dy is not None and got_dy <= 2.0,
                  f"纯横向用例却报出纵向位移 {got_dy}pt")
            # 归因元素必须一并给出，否则运维还要自己去 elements 里翻
            check(problems, "用例8", bool((extremes.get("mostDx") or {}).get("index") is not None),
                  "extremes.mostDx 未记录横向错位最严重的元素")
            detail = ref.get("detail") or ""
            check(problems, "用例8", "横向" in detail,
                  f"横向超容差却未在 detail 里说明横向：{detail!r}")
            check(problems, "用例8", "纵向" not in detail,
                  f"纵向并未超容差，detail 不应提纵向：{detail!r}")
            verdict = data.get("verdict") or ""
            check(problems, "用例8", "横向" in verdict,
                  f"总体结论未说明横向：{verdict!r}")
            check(problems, "用例8", "纵向最大" not in verdict,
                  f"纵向并未超容差，总体结论不应报「纵向最大」：{verdict!r}")
            # 同一处错位在两处必须归到同一个元素（曾经一处取自可信行、一处取自全量行）
            check(problems, "用例8",
                  (ref.get("extremes") or {}).get("mostDx") is not None and "mostDx" in (ref.get("extremes") or {}),
                  "extremes 缺少 mostDx，conclude 将无法复用同一归因")

    for problem in problems:
        print("FAIL " + problem)
    if problems:
        print(f"\n{len(problems)} 项不通过")
        return 1
    print("对齐审计回归：8 个用例全部通过（含 2 个反恒真式用例、1 个横向错位结论文案用例）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
