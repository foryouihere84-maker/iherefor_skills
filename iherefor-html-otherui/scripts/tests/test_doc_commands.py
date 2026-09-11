#!/usr/bin/env python3
"""文档漂移检查：文档里出现的脚本命令，其参数必须是脚本真正支持的。

这个 skill 是文档驱动 Agent 的：Agent 照着 SKILL.md / references 里的命令执行。
文档里写错一个 flag（例如漏掉 --viewport-from、把不存在的参数写进示例），
Agent 会照着跑到失败，而脚本测试全绿——因为脚本本身没问题。

因此这里做一次交叉校验：把每个脚本接受的 --flag 抠出来，再扫描所有 md 文档里
出现 `scripts/<name>` 的那些行，检查该行上的 --flag 是否都在对应脚本的参数表里。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]

SCRIPT_PATTERN = re.compile(r"(?<![\w./-])scripts/([A-Za-z0-9_.-]+\.(?:py|mjs|sh))")
FLAG_PATTERN = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]+)")

PY_FLAG = re.compile(r"add_argument\(\s*[\"'](--[a-z0-9-]+)")
MJS_FLAG = re.compile(r"arg\(\s*['\"](--[a-z0-9-]+)|process\.argv\.includes\(\s*['\"](--[a-z0-9-]+)")
SH_FLAG = re.compile(r"^\s*(--[a-z][a-z0-9-]+)\)", re.MULTILINE)


def script_flags(script: Path) -> set[str]:
    text = script.read_text(encoding="utf-8")
    if script.suffix == ".py":
        return set(PY_FLAG.findall(text))
    if script.suffix == ".mjs":
        return {a or b for a, b in MJS_FLAG.findall(text)}
    if script.suffix == ".sh":
        return set(SH_FLAG.findall(text))
    return set()


def collect_scripts() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in sorted((SKILL_ROOT / "scripts").rglob("*")):
        if path.is_file() and path.suffix in {".py", ".mjs", ".sh"}:
            found[path.name] = script_flags(path)
    return found


def markdown_files() -> list[Path]:
    candidates = [SKILL_ROOT / "SKILL.md", SKILL_ROOT / "README.md"]
    candidates += sorted((SKILL_ROOT / "references").glob("*.md"))
    candidates += sorted((SKILL_ROOT / "evals").rglob("*.md"))
    candidates += sorted((SKILL_ROOT / "lanhu-mcp-server").glob("README.md"))
    candidates += sorted((SKILL_ROOT / "testUIProject").glob("README.md"))
    candidates += sorted((SKILL_ROOT / "scripts" / "tests" / "fixtures").glob("README.md"))
    return [p for p in candidates if p.is_file()]


def main() -> int:
    scripts = collect_scripts()
    problems: list[str] = []
    checked_lines = 0

    for doc in markdown_files():
        for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), start=1):
            names = SCRIPT_PATTERN.findall(line)
            if not names:
                continue
            known = [n for n in names if n in scripts]
            if not known:
                problems.append(f"{doc.relative_to(SKILL_ROOT)}:{number} 引用了不存在的脚本：{', '.join(names)}")
                continue
            # 同一行可能串了多个脚本，取并集判定。
            allowed = set().union(*(scripts[n] for n in known))
            for flag in FLAG_PATTERN.findall(line):
                checked_lines += 1
                if flag not in allowed:
                    problems.append(
                        f"{doc.relative_to(SKILL_ROOT)}:{number} {known[0]} 不接受 {flag}"
                    )

    if problems:
        print("文档与脚本参数不一致：")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    docs = len(markdown_files())
    print(f"文档漂移检查通过：{docs} 个文档，{len(scripts)} 个脚本，{checked_lines} 处参数引用全部有效")
    return 0


if __name__ == "__main__":
    sys.exit(main())
