#!/usr/bin/env python3
"""对 layout 用例的判分器做逐条变异，证明它的断言不是空的。

用法（需要 PyYAML，所以用 skill 自带的解释器）：

    .runtime/venv/bin/python3 evals/harness/probe_layout_judge.py

为什么单独有这么一个探针：``selfcheck.py`` 只证明「pass 判过、fail 判挂」，它管不到
「断言本身有没有在断言」。判分器里一条写坏的 `if` 会让某个断言静默短路，而两份样本
恰好都走到旁边那条路径上 —— 于是两边都「如预期」。

**这个探针比一般的变异探针多一类断言：反向断言。** 只验「改坏了一定变红」会漏掉
更危险的一种缺陷 —— 旧检查在新口径下**反过来惩罚正确答案**。本用例就踩过：
判分器曾要求 `relationKindCounts.fixed > 0`，用来证明「计划不是旧的一轴产物」；
而闭合契约下 `fixed` 只是候选，一个复核得对的 Agent 会把 `offers.height` / `cta.height`
改判成 `intrinsic` / `bounded`，于是 `fixed = 0` —— 正确实现被判挂。
所以下面的用例 2 专门断言「复核后 fixed=0 仍必须通过」。

退出码：0 = 全部如预期，1 = 有断言形同虚设（或反向断言被误伤）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
SKILL_ROOT = HARNESS.parents[1]
CASE = SKILL_ROOT / "evals" / "cases" / "layout-no-device-derived-coordinates.yaml"
SAMPLE = SKILL_ROOT / "evals" / "fixtures" / "golden" / "layout-no-device-derived-coordinates" / "pass"


def judge(workspace: Path) -> tuple[int, str]:
    """用零凭据判分器判一个工作区，返回 (退出码, 输出)。"""
    proc = subprocess.run(
        [sys.executable, str(HARNESS / "run_case.py"),
         "--case", str(CASE), "--workspace", str(workspace),
         "--message", str(workspace / "answer.md")],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout or proc.stderr or ""


def patch_json(rel: str, mutate):
    """把样本里某个 JSON 的某处改坏。"""
    def apply(workspace: Path) -> None:
        path = workspace / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return apply


def edit_text(rel: str, old: str, new: str):
    def apply(workspace: Path) -> None:
        path = workspace / rel
        text = path.read_text(encoding="utf-8")
        if old not in text:
            raise AssertionError(f"{rel} 里找不到 {old!r} —— 变异没落进样本")
        path.write_text(text.replace(old, new), encoding="utf-8")
    return apply


def delete(rel: str):
    def apply(workspace: Path) -> None:
        (workspace / rel).unlink()
    return apply


def baseline(workspace: Path) -> None:
    pass


EVIDENCE = "diff/layout-proportions.json"
VERDICT = "diff/layout-verdict.json"

# (说明, 变异, 期望判分器退出码)。0 = 判过，1 = 判挂。
PROBES = [
    # 反向断言：基线本身必须过，否则后面「变红」说明不了任何事。
    ("基线：pass 样本必须过", baseline, 0),
    # 反向断言：复核过 fixed 候选、改判 intrinsic 的正确实现不得被误伤。
    ("复核后 fixed=0（改判 intrinsic）仍必须过",
     patch_json(EVIDENCE, lambda d: d["relationKindCounts"].update(fixed=0, intrinsic=4)), 0),
    # 出处：必须来自闭合契约版的校验器。
    ("schemaVersion 退回 3 必须判红",
     patch_json(EVIDENCE, lambda d: d.update(schemaVersion=3)), 1),
    # 位置轴：贴父边的约束闭合与成比例关系都必须在场。
    ("relationKindCounts 缺 pinned 必须判红",
     patch_json(EVIDENCE, lambda d: d["relationKindCounts"].pop("pinned")), 1),
    ("relationKindCounts 缺 proportional 必须判红",
     patch_json(EVIDENCE, lambda d: d["relationKindCounts"].pop("proportional")), 1),
    # 召回：设备推导坐标必须被点名。
    ("violations 只留 2 条设备推导值必须判红",
     patch_json(VERDICT, lambda d: d.update(violations=d["violations"][:2])), 1),
    ("violations 里没有 file 字段必须判红",
     patch_json(VERDICT, lambda d: [v.pop("file") for v in d["violations"]]), 1),
    # 精度：不该进 violations 的三类值。
    ("把 68（fixed 候选）塞进 violations 必须判红",
     patch_json(VERDICT, lambda d: d["violations"].append({"literal": 68, "file": "src/SpecialOfferViewController.m"})), 1),
    ("把 23（≤48pt 待判值）塞进 violations 必须判红",
     patch_json(VERDICT, lambda d: d["violations"].append({"literal": 23, "file": "src/SpecialOfferViewController.m"})), 1),
    # 候选接没接住。
    ("删掉 reviewPending 必须判红",
     patch_json(VERDICT, lambda d: d.pop("reviewPending")), 1),
    ("reviewPending 空数组必须判红",
     patch_json(VERDICT, lambda d: d.update(reviewPending=[])), 1),
    ("reviewPending 没点到候选关系必须判红",
     patch_json(VERDICT, lambda d: d.update(reviewPending=[{"relation": "legal.height", "verdict": "无需复核"}])), 1),
    # 结论要件。
    ("status 记成 pass 必须判红",
     patch_json(VERDICT, lambda d: d.update(status="pass")), 1),
    ("deliveryReady 记成 true 必须判红",
     patch_json(VERDICT, lambda d: d.update(deliveryReady=True)), 1),
    ("删掉 reason 必须判红",
     patch_json(VERDICT, lambda d: d.update(reason="")), 1),
    # 产物必须是脚本跑出来的，且源码不得被改写。
    ("缺校验器原始产出必须判红", delete(EVIDENCE), 1),
    ("源码被改写必须判红", edit_text("src/SpecialOfferViewController.m", "393, 321", "393, 999"), 1),
]


def main() -> int:
    if not SAMPLE.is_dir():
        print(f"找不到样本目录：{SAMPLE}", file=sys.stderr)
        return 2

    failures = 0
    for label, mutate, expected in PROBES:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw) / "pass"
            shutil.copytree(SAMPLE, workspace)
            try:
                mutate(workspace)
            except AssertionError as exc:
                failures += 1
                print(f"  探针本身失效：{label} —— {exc}")
                continue
            code, output = judge(workspace)
            # 判分器用法错误（2）不能算「如预期」：那说明探针跑不起来，
            # 而不是被测断言生效了。
            if code == 2:
                failures += 1
                print(f"  判分器用法错误：{label}\n{output.strip()[-400:]}")
                continue
            ok = code == expected
            if not ok:
                failures += 1
            wanted = "判过" if expected == 0 else "判挂"
            got = "判过" if code == 0 else "判挂"
            print(f"  [{'ok ' if ok else '!! '}] {label:<44} 期望{wanted}，实际{got}")
            if not ok:
                print("\n".join(f"        {line}" for line in output.strip().splitlines()[-6:]))

    print()
    if failures:
        print(f"变异探针发现 {failures} 项不符预期：有断言形同虚设，或有正确实现被误伤")
        return 1
    print(f"变异探针通过：{len(PROBES)} 项全部如预期"
          "（含两条反向断言：基线必须过、复核后 fixed=0 必须过）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
