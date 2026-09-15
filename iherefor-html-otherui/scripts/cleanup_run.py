#!/usr/bin/env python3
"""回收 run 目录里契约外的 Xcode DerivedData，阻止体积无界累积。

`xcodebuild -derivedDataPath <run>/DerivedData` 会把一份完整编译缓存塞进每个 run，
run 目录因此不可控地膨胀（实测单个 run 50~100MB）。但 DerivedData **不在 run 产物
契约里**（见 references/artifact-contract.md 与 project-management.md 的 run 目录结构），
删掉它不影响任何证据：`actual/` 截图与日志、`diff/`、`review.json`、`delivery-gate.json`
等都保留，下次编译会按需重建缓存。

本脚本**只删** run 目录下名为 ``DerivedData`` 的目录，绝不碰契约内产物。默认 dry-run
只列清单，``--yes`` 才真删。

用法：
    # 列出一个 run 会回收什么（默认 dry-run）
    python3 scripts/cleanup_run.py --run <run-dir>

    # 真删一个 run 的 DerivedData
    python3 scripts/cleanup_run.py --run <run-dir> --yes

    # 递归回收整个页面或整个项目下的所有 run
    python3 scripts/cleanup_run.py --page <pages/<page-id>> --yes
    python3 scripts/cleanup_run.py --project <project-root> --yes

退出码：0 = 成功（含「没有可回收项」）；1 = 出错；2 = 用法错误。
"""
import argparse
import shutil
import sys
from pathlib import Path

# 只回收这个名字的目录。契约外、可重建、删除安全。
# 不放其它模式：run 里的 actual/diff/*.json 都是证据，绝不误删。
DERIVED_DIR_NAME = "DerivedData"


def find_derived_dirs(base: Path):
    """返回 base 下所有名为 DerivedData 的目录（含 base 自身若是）。"""
    hits = []
    if base.name == DERIVED_DIR_NAME and base.is_dir():
        hits.append(base)
        return hits
    if base.is_dir():
        for p in base.rglob(DERIVED_DIR_NAME):
            if p.is_dir():
                hits.append(p)
    return sorted(hits, key=lambda p: str(p))


def dir_size(path: Path):
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
    except OSError:
        pass
    return total


def human(nbytes):
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024 or unit == "GB":
            return f"{nbytes:.1f} {unit}" if unit != "B" else f"{nbytes} B"
        nbytes /= 1024
    return f"{nbytes:.1f} GB"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", help="单个 run 目录（runs/<run-id>）")
    group.add_argument("--page", help="页面目录（pages/<page-id>），递归回收其下所有 run")
    group.add_argument("--project", help="项目根（含 .ihereforUI），递归回收所有 run")
    ap.add_argument("--yes", action="store_true", help="真删；缺省 dry-run 只列清单")
    args = ap.parse_args()

    base = Path(args.run or args.page or args.project).resolve()
    if not base.is_dir():
        print(f"error: not a directory: {base}", file=sys.stderr)
        return 2

    hits = find_derived_dirs(base)
    if not hits:
        print("没有可回收的 DerivedData（契约外编译缓存）。")
        return 0

    total = sum(dir_size(p) for p in hits)
    print(f"发现 {len(hits)} 个 DerivedData，合计约 {human(total)}：")
    for p in hits:
        print(f"  {human(dir_size(p)):>10}  {p}")

    if not args.yes:
        print("\n[dry-run] 未删除。加 --yes 真删。这些目录属契约外编译缓存，删除安全。")
        return 0

    removed_bytes = 0
    for p in hits:
        sz = dir_size(p)
        try:
            shutil.rmtree(p)
            removed_bytes += sz
            print(f"  已删  {human(sz):>10}  {p}")
        except OSError as exc:
            print(f"  失败  {p}: {exc}", file=sys.stderr)
    print(f"回收完成，释放约 {human(removed_bytes)}。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
