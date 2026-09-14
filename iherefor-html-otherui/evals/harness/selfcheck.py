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

import os
import re
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
FIXTURES = SKILL_ROOT / "evals" / "fixtures"

# 样本里可能出现的文本文件（图片素材不在其中）。
TEXT_SUFFIXES = (".json", ".md", ".yaml", ".yml", ".txt", ".sh")
HOME_PATH = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+")


def case_files() -> list:
    """以 eval.yaml 的 cases.files 为准，避免漏跑或跑进未登记的用例。"""
    config = yaml.safe_load((SKILL_ROOT / "evals" / "eval.yaml").read_text(encoding="utf-8")) or {}
    return ((config.get("cases") or {}).get("files")) or []


def case_ids() -> list[str]:
    """以 eval.yaml 的 cases.files 为准，避免漏跑或跑进未登记的用例。"""
    return [Path(name).stem for name in case_files()]


def case_document(name):
    """读一份用例定义；名字可以是带路径的，也可以只是文件名。"""
    candidate = SKILL_ROOT / name
    if not candidate.is_file():
        candidate = SKILL_ROOT / "evals" / "cases" / Path(name).name
    if not candidate.is_file():
        return None
    return yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}


def check_fixture_layout() -> list:
    """每个 repo_fixture 指向的目录都不得自带文档文件。

    这是「两层 fixture」约定的可执行版本。``repo_fixture`` 的语义是**把目录内容拷进
    被测 Agent 的工作区**，所以指到哪一层，那一层的所有文件都会进工作区。fixture 根目录
    的 ``README.md`` 记着用例的正确结论（判分侧文档），一旦与素材平级，它就会被一起拷进去 ——
    等于泄题。这类问题的形态很隐蔽：文件本身全都正常，错的是「拷什么」的边界，
    评审时很难看出来（`fixtures/repo` 就曾经是这种扁平结构）。

    所以这里直接判「被指向的目录里不许有文档文件」，而不是去猜某个文件是不是答案。
    """
    problems = []
    for name in case_files():
        case_id = Path(name).stem
        case = case_document(name)
        if case is None:
            problems.append(f"{case_id}: 找不到用例定义 {name}")
            continue
        fixture = (case.get("context") or {}).get("repo_fixture")
        if not fixture:
            continue
        target = SKILL_ROOT / fixture
        if not target.is_dir():
            problems.append(f"{case_id}: repo_fixture 不存在：{fixture}")
            continue
        leaked = sorted(
            item.name for item in target.iterdir()
            if item.is_file() and item.suffix.lower() in (".md", ".txt", ".rst", ".html"))
        if leaked:
            problems.append(
                f"{case_id}: repo_fixture 目录 {fixture} 里有文档文件 {leaked} —— "
                "fixture 没有分两层，判分侧文档会被一起拷进被测 Agent 的工作区。"
                "把素材移进 workspace/，文档留在 fixture 根目录")
        if not any(target.iterdir()):
            problems.append(f"{case_id}: repo_fixture 目录是空的：{fixture}")
    return problems


def check_fixture_portability() -> list:
    """fixture 里不得出现钉死在某台机器上的绝对路径。

    样本记录的是「一次正确执行长什么样」，其中不少字段是工具**原样产出的**。而工具写路径
    用的是 ``Path(...).resolve()``，于是绝对路径会被一起存进样本：换台机器、或仓库换个位置，
    这些字段就指向不存在的地方。它们不参与断言，所以不会让任何测试变红 —— 只能主动扫。

    危害也不是「报错」，而是**样本失真**：下次有人拿样本跟真跑结果对照，会看到一个纯属环境
    差异的「不一致」，甚至顺手把样本改回绝对路径。同一用例的 ``pass`` / ``fail`` 两份样本
    也会因此写法不一致（`same-size-needs-region-evidence` 就曾经如此：``fail`` 是工作区相对
    写法、``pass`` 是绝对路径）。

    规则：fixture 下的文本文件里不许出现 home 绝对路径，也不许出现仓库根的绝对路径。
    记录工具输出时要把这类字段改写成工作区相对形式（如 ``images/reference.png``）。
    """
    problems = []
    root = str(SKILL_ROOT)
    for path in sorted(FIXTURES.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(lines, start=1):
            hits = []
            for match in HOME_PATH.finditer(line):
                hits.append(match.group(0))
            if root in line:
                hits.append(root)
            if hits:
                rel = path.relative_to(SKILL_ROOT)
                problems.append(
                    f"{rel}:{number} 钉死了机器绝对路径 {hits[0]} —— "
                    "记录工具输出时要把路径字段改写成工作区相对形式")
    return problems


def check_judge_scripts() -> list:
    """判分脚本必须存在、且带可执行位。

    可执行位这条约定写在 `evals/README.md` 里，但**判分器是用 ``bash <path>`` 调用的**，
    所以少一个 ``+x`` 在测试里永远看不出来 —— 又一个静默缺陷。它只会在人手动
    ``./check-xxx.sh`` 时报 permission denied，而那时人正在排查别的问题。

    （``check-region-evidence.sh`` 就曾经漏了可执行位，同目录另外四个都有。）
    """
    problems = []
    seen = set()
    for name in case_files():
        case = case_document(name)
        if case is None:
            continue
        script = ((case.get("judge") or {}).get("script_path"))
        if not script or script in seen:
            continue
        seen.add(script)
        path = SKILL_ROOT / script
        if not path.is_file():
            problems.append(f"{Path(name).stem}: judge.script_path 不存在：{script}")
        elif not os.access(path, os.X_OK):
            problems.append(
                f"{script} 没有可执行位 —— 判分器用 bash 调它所以测试不会红，"
                "但人手动跑会 permission denied；chmod +x 补上")
    return problems


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

    # 先查 fixture 布局与可移植性：两项都零成本，而且不查的话这两件事都只会在花额度真跑时
    # 以「Agent 表现异常好」（泄题）或「样本对不上真跑结果」（路径失效）的形式出现，
    # 从现象看不出根因。
    fixture_checks = (
        ("repo_fixture 分层与存在性", check_fixture_layout()),
        ("fixture 不含机器绝对路径", check_fixture_portability()),
        ("判分脚本存在且可执行", check_judge_scripts()),
    )
    print(f"{'用例':<34} {'fixture':<12}")
    print("-" * 62)
    for label, problems in fixture_checks:
        for problem in problems:
            failures += 1
            print(f"  {problem}")
        if not problems:
            print(f"{label:<34} {'✅ 如预期':<12}")
    print()

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
    print(f"判分器自检通过：{len(ids)} 个用例 × pass/fail 双向共 {len(ids) * 2} 项全部如预期，"
          "且每个 repo_fixture 都按两层结构摆放、fixture 里没有钉死机器绝对路径、"
          "每个判分脚本都存在且可执行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
