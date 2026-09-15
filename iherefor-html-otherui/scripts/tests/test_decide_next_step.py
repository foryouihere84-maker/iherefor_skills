#!/usr/bin/env python3
"""回归：decide_next_step.py 的停止判定 —— 顺序、分支、纯函数。

核心断言（这脚本价值所在）：
  1. 「基准不可信」优先于「物理下界」「y 单调」—— 基准错了，后面结论全不可信；
  2. 各硬停止条件正确命中对应的落盘产物状态；
  3. regions_monotonic_in_y 对「随 y 递增」与「无规律」的判别正确；
  4. parent_no_improvement 沿 parentRunId 链比较，无 parent 时返回 None。

用临时目录造合成的 comparison.json / alignment.json / review.json，不端到端跑 audit。
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import decide_next_step as dns  # noqa: E402


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False))


def make_run(tmp, comparison=None, alignment=None, review=None):
    run = Path(tmp) / "pages" / "p" / "runs" / "r1"
    run.mkdir(parents=True)
    for name, obj in (("comparison.json", comparison), ("alignment.json", alignment), ("review.json", review)):
        if obj is not None:
            write(run / "diff" / name, obj) if name.endswith(".json") and name != "review.json" else write(run / name, obj)
    return run


CMP_PASS = {"status": "pass", "structuralRatio": 0.005, "fillRatio": 0.002, "textureRatio": 0.02,
            "warnStructuralRatio": 0.02, "maxStructuralRatio": 0.08, "maxFillRatio": 0.1, "regions": []}
ALIGN_ALIGNED = {"status": "aligned", "reason": "ok"}


def main():
    problems = []

    # 1. regions_monotonic_in_y 纯函数
    def reg(rows):
        return [{"row": r, "structuralRatio": v} for r, v in rows]
    assert dns.regions_monotonic_in_y([]) is False
    assert dns.regions_monotonic_in_y(reg([(0, 0.01), (1, 0.02), (2, 0.04)])) is True   # 单调×2
    assert dns.regions_monotonic_in_y(reg([(0, 0.01), (1, 0.009), (2, 0.04)])) is False  # 非单调
    assert dns.regions_monotonic_in_y(reg([(0, 0.01), (1, 0.015)])) is False            # 少于3行
    assert dns.regions_monotonic_in_y(reg([(0, 0.01), (1, 0.011), (2, 0.012)])) is False  # 增幅不够显著（末行仅 1.2 倍）

    # 2. decide：干净 pass → continue
    with tempfile.TemporaryDirectory() as tmp:
        run = make_run(tmp, comparison=CMP_PASS, alignment=ALIGN_ALIGNED)
        decision, reason, action, checks = dns.decide(run, with_parent=False)
        if decision != 'continue':
            problems.append(f"干净 align+pass 应 continue，得 {decision} / {reason}")

    # 3. 缺 comparison → stop
    with tempfile.TemporaryDirectory() as tmp:
        run = make_run(tmp, comparison=None, alignment=ALIGN_ALIGNED)
        decision, reason, _, _ = dns.decide(run, with_parent=False)
        if decision != 'stop' or 'comparison' not in reason:
            problems.append(f"缺 comparison 应 stop，得 {decision} / {reason}")

    # 4. 基准不可信 → stop（优先级最高，即使 comparison 是物理下界）
    with tempfile.TemporaryDirectory() as tmp:
        cmp_floor = dict(CMP_PASS, status="pass-with-review", reason="structural-within-declared-floor")
        align_bad = {"status": "needs-review", "reason": "baseline-disagrees-with-dom", "crossCheckRequired": True}
        run = make_run(tmp, comparison=cmp_floor, alignment=align_bad)
        decision, reason, _, _ = dns.decide(run, with_parent=False)
        if decision != 'stop' or 'baseline-disagrees' not in reason:
            problems.append(f"基准不可信应优先 stop（即使物理下界），得 {decision} / {reason}")

    # 5. 只有纹理噪点 —— 软提示（不 stop，但 checks 带 texture-only-noise 告警）
    with tempfile.TemporaryDirectory() as tmp:
        cmp_tex = {"status": "pass", "structuralRatio": 0.001, "fillRatio": 0.001, "textureRatio": 0.05,
                   "warnStructuralRatio": 0.02, "maxFillRatio": 0.1, "regions": []}
        run = make_run(tmp, comparison=cmp_tex, alignment=ALIGN_ALIGNED)
        decision, reason, _, checks = dns.decide(run, with_parent=False)
        if decision != 'continue':
            problems.append(f"只有纹理噪点不应硬停，得 {decision} / {reason}")
        if not any(c.get('check') == 'texture-only-noise' for c in checks):
            problems.append("纹理噪点应作为软提示出现在 checks 里")

    # 6. y 单调 → stop
    with tempfile.TemporaryDirectory() as tmp:
        cmp_ymono = dict(CMP_PASS, structuralRatio=0.03, regions=[
            {"row": 0, "structuralRatio": 0.01}, {"row": 1, "structuralRatio": 0.02}, {"row": 2, "structuralRatio": 0.04}])
        run = make_run(tmp, comparison=cmp_ymono, alignment=ALIGN_ALIGNED)
        decision, reason, _, _ = dns.decide(run, with_parent=False)
        if decision != 'stop' or '单调' not in reason:
            problems.append(f"y 单调递增应 stop，得 {decision} / {reason}")

    # 7. 物理下界（无基准问题）→ stop，且 reason 命中下界（而非噪点）
    with tempfile.TemporaryDirectory() as tmp:
        cmp_floor = dict(CMP_PASS, status="pass-with-review", reason="structural-within-declared-floor")
        run = make_run(tmp, comparison=cmp_floor, alignment=ALIGN_ALIGNED)
        decision, reason, _, _ = dns.decide(run, with_parent=False)
        if decision != 'stop':
            problems.append(f"物理下界应 stop，得 {decision}")

    # 8. parent_no_improvement 纯函数：无 parent → None；有改善 → False；无改善 → True
    with tempfile.TemporaryDirectory() as tmp:
        run = make_run(tmp, comparison={"structuralRatio": 0.05, "fillRatio": 0.03}, review={"parentRunId": "r0"})
        # 无 parent 目录里的 comparison → None
        if dns.parent_no_improvement(run) is not None:
            problems.append("无 parent 可读时应返回 None")
        # 造 parent，本轮无改善
        write(run.parent / "r0" / "diff" / "comparison.json", {"structuralRatio": 0.02, "fillRatio": 0.01})
        if dns.parent_no_improvement(run) is not True:
            problems.append("本轮 0.05≥0.02 且 0.03≥0.01 应判 True（无改善）")
        # 造 parent，本轮有改善
        write(run / "diff" / "comparison.json", {"structuralRatio": 0.01, "fillRatio": 0.005})
        if dns.parent_no_improvement(run) is not False:
            problems.append("本轮 0.01<0.02 应判 False（有改善）")

    for p in problems:
        print(p)
    if problems:
        return 1
    print("decide_next_step 停止判定：顺序、分支、纯函数均正确")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
