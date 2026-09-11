#!/usr/bin/env python3
"""零凭据判分器：对一个工作区执行用例的 expect 与 judge，全部是确定性断言。

这是评测套件的「判分器自检」层——不需要任何 Agent Engine 凭据，CI 每次都能跑。
它**不能**替代 `skill-up run`：真实执行需要一个真实 Agent。但「判分逻辑对不对」
不应该等到花了额度才知道，也不应该因为没额度就一直没人验证。

用法：
  run_case.py --case evals/cases/x.yaml --workspace <dir> [--message answer.md]
              [--skill <skill root>] [--exit-code 0] [--quiet]

退出码：0 = PASS，1 = FAIL，2 = 用法/配置错误。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("需要 PyYAML：pip install -r requirements.txt")

# expect 里按「追加去重」合并的切片字段；标量字段由用例覆盖默认值。
LIST_FIELDS = ("must_contain", "must_not_contain", "files_exist", "files_not_exist", "file_contains")
SCALAR_FIELDS = ("exit_code", "golden_file")


class Report:
    def __init__(self, quiet: bool = False) -> None:
        self.problems: list[str] = []
        self.lines: list[str] = []
        self.quiet = quiet

    def ok(self, text: str) -> None:
        self.lines.append(f"  ok   {text}")

    def bad(self, text: str) -> None:
        self.lines.append(f"  FAIL {text}")
        self.problems.append(text)

    def flush(self) -> None:
        if not self.quiet:
            print("\n".join(self.lines))


def merged_expect(skill: Path, case: dict) -> dict:
    """把 eval.yaml 的 cases.defaults.expect 与用例自己的 expect 合并。"""
    expect: dict = {}
    eval_path = skill / "evals" / "eval.yaml"
    if eval_path.is_file():
        config = yaml.safe_load(eval_path.read_text(encoding="utf-8")) or {}
        defaults = ((config.get("cases") or {}).get("defaults") or {}).get("expect") or {}
        expect.update(defaults)
    case_expect = case.get("expect") or {}
    for key in LIST_FIELDS:
        combined = list(expect.get(key) or []) + list(case_expect.get(key) or [])
        if combined:
            # dict 元素（file_contains）不能直接去重，按 JSON 串去重。
            seen, unique = set(), []
            for item in combined:
                marker = json.dumps(item, sort_keys=True, ensure_ascii=False)
                if marker not in seen:
                    seen.add(marker)
                    unique.append(item)
            expect[key] = unique
    for key in SCALAR_FIELDS:
        if key in case_expect:
            expect[key] = case_expect[key]
    return expect


def check_files(rep: Report, workspace: Path, expect: dict) -> None:
    for rel in expect.get("files_exist") or []:
        if (workspace / rel).exists():
            rep.ok(f"存在 {rel}")
        else:
            rep.bad(f"缺少 {rel}")
    for rel in expect.get("files_not_exist") or []:
        if (workspace / rel).exists():
            rep.bad(f"不应存在却出现了 {rel}")
        else:
            rep.ok(f"未出现 {rel}")
    for entry in expect.get("file_contains") or []:
        path = workspace / entry.get("path", "")
        needle = entry.get("content", "")
        if not path.is_file():
            rep.bad(f"file_contains 目标不存在：{entry.get('path')}")
        elif needle in path.read_text(encoding="utf-8", errors="replace"):
            rep.ok(f"{entry.get('path')} 含 {needle!r}")
        else:
            rep.bad(f"{entry.get('path')} 不含 {needle!r}")


def text_matchers(rep: Report, label: str, matchers: dict, message: str) -> None:
    for value in matchers.get("all") or []:
        rep.ok(f"{label} all: {value!r}") if value in message else rep.bad(f"{label} all 未命中: {value!r}")
    any_list = matchers.get("any") or []
    if any_list:
        hit = next((v for v in any_list if v in message), None)
        rep.ok(f"{label} any: 命中 {hit!r}") if hit else rep.bad(f"{label} any 全部未命中: {any_list}")
    for value in matchers.get("not") or []:
        rep.bad(f"{label} not 命中（不应出现）: {value!r}") if value in message else rep.ok(f"{label} not: 未出现 {value!r}")


def regex_matchers(rep: Report, label: str, matchers: dict, message: str) -> None:
    def search(pattern: str) -> bool:
        try:
            return re.search(pattern, message, re.MULTILINE) is not None
        except re.error as exc:
            rep.bad(f"{label} 正则非法 {pattern!r}: {exc}")
            return False

    for pattern in matchers.get("all") or []:
        rep.ok(f"{label} all: /{pattern}/") if search(pattern) else rep.bad(f"{label} all 未命中: /{pattern}/")
    any_list = matchers.get("any") or []
    if any_list:
        hit = next((p for p in any_list if search(p)), None)
        rep.ok(f"{label} any: /{hit}/") if hit else rep.bad(f"{label} any 全部未命中: {any_list}")
    for pattern in matchers.get("not") or []:
        rep.bad(f"{label} not 命中（不应出现）: /{pattern}/") if search(pattern) else rep.ok(f"{label} not: 未命中 /{pattern}/")


def run_judge(rep: Report, skill: Path, workspace: Path, judge: dict, message: str, exit_code: int) -> None:
    kind = judge.get("type")
    if kind == "script":
        script = (skill / judge["script_path"]).resolve()
        if not script.is_file():
            rep.bad(f"判分脚本不存在：{judge['script_path']}")
            return
        proc = subprocess.run(["bash", str(script)], cwd=workspace, capture_output=True, text=True)
        rep.lines.append(f"  ---- script judge {judge['script_path']} → exit={proc.returncode}")
        for stream in (proc.stdout, proc.stderr):
            for line in (stream or "").strip().splitlines():
                rep.lines.append(f"       {line}")
        if proc.returncode == 0:
            rep.ok("script judge 通过")
        else:
            rep.bad(f"script judge 失败（exit={proc.returncode}）")
    elif kind == "rule_based":
        for assertion in judge.get("success") or []:
            for key, value in assertion.items():
                if key == "output_contains":
                    text_matchers(rep, "output_contains", value, message)
                elif key == "output_matches":
                    regex_matchers(rep, "output_matches", value, message)
                elif key in ("files_exist", "files_not_exist", "file_contains"):
                    check_files(rep, workspace, {key: value})
                elif key == "exit_code":
                    if exit_code == value:
                        rep.ok(f"exit_code == {value}")
                    else:
                        rep.bad(f"exit_code={exit_code}，期望 {value}")
                else:
                    rep.bad(f"判分器尚未支持 matcher: {key}")
        for assertion in judge.get("failure") or []:
            for key, value in assertion.items():
                if key == "output_contains":
                    hits = [v for v in (value.get("any") or []) if v in message]
                    if hits:
                        rep.bad(f"failure 命中：{hits}")
    elif kind == "agent_judge":
        rep.bad("agent_judge 需要 Agent Engine 凭据，零凭据自检不支持；请用 skill-up run")
    else:
        rep.bad(f"未知 judge 类型：{kind}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--message", type=Path)
    parser.add_argument("--skill", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    skill = args.skill.resolve()
    if not args.case.is_file():
        print(f"用例不存在：{args.case}", file=sys.stderr)
        return 2
    case = yaml.safe_load(args.case.read_text(encoding="utf-8")) or {}
    workspace = args.workspace.resolve()
    message = ""
    if args.message and args.message.is_file():
        message = args.message.read_text(encoding="utf-8", errors="replace")

    rep = Report(quiet=args.quiet)
    if not args.quiet:
        print(f"用例 {case.get('id') or args.case.stem} | 工作区 {workspace}")

    expect = merged_expect(skill, case)
    check_files(rep, workspace, expect)
    for value in expect.get("must_contain") or []:
        rep.ok(f"must_contain: {value!r}") if value in message else rep.bad(f"must_contain 未命中: {value!r}")
    for value in expect.get("must_not_contain") or []:
        rep.bad(f"must_not_contain 命中: {value!r}") if value in message else rep.ok(f"must_not_contain: 未出现 {value!r}")
    if "exit_code" in expect and expect["exit_code"] != args.exit_code:
        rep.bad(f"expect.exit_code={expect['exit_code']}，实际 {args.exit_code}")

    run_judge(rep, skill, workspace, case.get("judge") or {}, message, args.exit_code)

    rep.flush()
    if not args.quiet:
        print(f"→ {'PASS' if not rep.problems else 'FAIL'}（{len(rep.problems)} 项问题）")
    return 0 if not rep.problems else 1


if __name__ == "__main__":
    sys.exit(main())
