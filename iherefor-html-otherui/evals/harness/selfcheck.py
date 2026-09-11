#!/usr/bin/env python3
"""评测套件自检：每个用例都必须带一对样本——「必须过」和「必须挂」。

零凭据、零 LLM，CI 每次都能跑。它保证的是**判分器本身有效**：
一个永远返回 PASS 的判分器，或者一条谁都满足不了的断言，在这里会立刻暴露。
没有这层，判分器的错误只能等到花额度真跑时才发现，而那时看到的「用例失败」
分不清是 Agent 做错了还是判分写错了。

样本约定（目录名固定为 pass / fail）：
  evals/fixtures/golden/<case-id>/pass/answer.md   （可另放该场景需要的工作区文件）
  evals/fixtures/golden/<case-id>/fail/answer.md

退出码：0 = 全部符合预期，1 = 有不符合，2 = 用法错误。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("需要 PyYAML：pip install -r requirements.txt")

HARNESS = Path(__file__).resolve().parent
SKILL_ROOT = HARNESS.parents[1]
GOLDEN = SKILL_ROOT / "evals" / "fixtures" / "golden"


def case_ids() -> list[str]:
    """以 eval.yaml 的 cases.files 为准，避免漏跑或跑进未登记的用例。"""
    config = yaml.safe_load((SKILL_ROOT / "evals" / "eval.yaml").read_text(encoding="utf-8")) or {}
    files = ((config.get("cases") or {}).get("files")) or []
    return [Path(name).stem for name in files]


def evaluate(case_id: str, kind: str) -> tuple[bool, str]:
    """返回 (是否符合预期, 说明)。"""
    sample = GOLDEN / case_id / kind
    if not sample.is_dir():
        return False, f"缺少样本目录 {sample.relative_to(SKILL_ROOT)}"
    proc = subprocess.run(
        [sys.executable, str(HARNESS / "run_case.py"),
         "--case", str(SKILL_ROOT / "evals" / "cases" / f"{case_id}.yaml"),
         "--workspace", str(sample),
         "--message", str(sample / "answer.md")],
        capture_output=True, text=True,
    )
    if proc.returncode == 2:
        return False, f"判分器用法错误：{proc.stderr.strip()[:200]}"
    passed = proc.returncode == 0
    expect_pass = kind == "pass"
    if passed == expect_pass:
        return True, ""
    # 不符预期时把完整判分过程带出来，否则「pass 样本挂了」这句话本身没法排查。
    lines = (proc.stdout or proc.stderr or "(判分器无输出)").strip().splitlines()
    return False, "\n".join(f"      {line}" for line in lines)


def main() -> int:
    ids = case_ids()
    if not ids:
        print("eval.yaml 未登记任何用例", file=sys.stderr)
        return 2

    failures = 0
    print(f"{'用例':<34} {'pass 样本':<12} {'fail 样本':<12}")
    print("-" * 62)
    for case_id in ids:
        marks = []
        for kind in ("pass", "fail"):
            ok, detail = evaluate(case_id, kind)
            marks.append("✅ 如预期" if ok else "❌ 不符预期")
            if not ok:
                failures += 1
                if detail:
                    print(f"  {case_id} [{kind}] {detail}")
        print(f"{case_id:<34} {marks[0]:<12} {marks[1]:<12}")

    print("-" * 62)
    if failures:
        print(f"判分器自检失败：{failures} 项不符预期")
        return 1
    print(f"判分器自检通过：{len(ids)} 个用例 × pass/fail 双向共 {len(ids) * 2} 项全部如预期")
    return 0


if __name__ == "__main__":
    sys.exit(main())
