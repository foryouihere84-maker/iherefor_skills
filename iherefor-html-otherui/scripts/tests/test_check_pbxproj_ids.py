#!/usr/bin/env python3
"""回归：pbxproj Object ID 唯一性门（``check_pbxproj_ids.py``）。

手动加资源时 ID 冲突会导致对象被覆盖、资源静默丢失。测试盯：

1. **召回**：同一个 24 位 ID 有多个对象定义（含 isa）→ 判重复、退出 1、列出冲突行；
2. **精度**：合法的「外键引用」（TargetAttributes / PBXContainerItemProxy 里跨 target 的
   ``ID = {`` 无 isa）不算重复 —— 三个 target 的 proto ID 在 dependency 里被引用是正常的；
3. **干净通过**：无重复时退出 0；
4. **读错误退出 2**：文件不存在或用法错。
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_pbxproj_ids.py"

DUP_ID = "A10000000000000000000094"
OTHER_ID = "A20000000000000000000094"


def run(text):
    with tempfile.TemporaryDirectory() as scratch:
        p = Path(scratch) / "project.pbxproj"
        p.write_text(text, encoding="utf-8")
        proc = subprocess.run([sys.executable, str(SCRIPT), str(p)],
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout


def main():
    problems = []

    def check(condition, message):
        if not condition:
            problems.append(message)

    # 用例 1：真重复 —— 同 ID 两个定义（都含 isa）→ 判重、退出 1
    dup = (
        f"\t\t{DUP_ID} /* my_asset.png in Resources */ = {{isa = PBXBuildFile; fileRef = {OTHER_ID}; }};\n"
        f"\t\t{DUP_ID} /* other_asset.png in Resources */ = {{isa = PBXBuildFile; fileRef = {OTHER_ID}; }};\n"
    )
    code, out = run(dup)
    check(code == 1, f"用例1：重复 ID 应退出 1，实得 {code}")
    check("my_asset.png" in out and "other_asset.png" in out,
          f"用例1：应列出两个冲突注释，实得 {out.strip()[:200]}")

    # 用例 2：合法外键引用不算重复 —— 同一 ID 一个定义 + 一个无 isa 的 { } 引用
    legit = (
        f"\t\t{DUP_ID} /* testTarget */ = {{isa = PBXNativeTarget; }};\n"
        f"\t\t\t{DUP_ID} = {{\n\t\t\t\tDevelopmentTeam = \"\";\n\t\t\t}};\n"
    )
    code2, _ = run(legit)
    check(code2 == 0, f"用例2：合法的外键引用不应判重，实得 {code2}")

    # 用例 3：无重复 → 退出 0
    clean = "\t\tA20000000000000000000095 /* a.png */ = {isa = PBXFileReference; };\n"
    code3, _ = run(clean)
    check(code3 == 0, f"用例3：无重复应退出 0，实得 {code3}")

    # 用例 4：用法错（无参数）→ 退出 2
    proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    check(proc.returncode == 2, f"用例4：缺参应退出 2，实得 {proc.returncode}")

    if problems:
        print("pbxproj ID 门未满足：\n  " + "\n  ".join(problems))
        return 1
    print("pbxproj ID 门：重复定义召回、外键引用不误判、无重复通过、用法错退出 2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
