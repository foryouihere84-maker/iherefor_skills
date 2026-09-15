#!/usr/bin/env python3
"""扫描 Xcode project.pbxproj 里重复的 Object ID。

背景（血的教训）：手动往 pbxproj 加资源时，若新资源的 Object ID 与既有对象撞了，
Xcode 解析时后一个定义覆盖前一个，被覆盖的资源就**静默不拷贝进 bundle**，`imageNamed:`
返回 nil、UI 渲染成 0×0 —— 编译照样 SUCCEEDED，只有像素 diff 能暴露，肉眼极易漏判。
实测「目的」页 4 个资源（purpose_cta_background / purpose_ipad_*）的 ID 与 brush_option
系列冲突，导致全部 purpose 资源未进 bundle。

所以「Object ID 全局唯一」必须有一个机器门：扫描 pbxproj 里所有对象定义行，report
同一个 24 位 ID 出现多个定义的情况。

用法：
    python3 scripts/check_pbxproj_ids.py <project.pbxproj>

退出码：0 = 无重复 ID；1 = 有重复 ID（列出冲突的 ID 与对应注释）；2 = 读取/用法错误。
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

# pbxproj 对象**定义**行：`ID /* 注释 */ = { isa = ...; ... };`
# 关键是紧跟的 `isa =`——Xcode 用 `ID = {` 的"外键引用"（TargetAttributes / PBXContainerItemProxy
# 里的跨 target proto ID）没有 isa、也不是对象定义，必须排除，否则会把合法的 target 引用误判成重复。
DEF_LINE = re.compile(r"^\s*([A-Fa-f0-9]{24})\s*(?:/\*\s*(.*?)\s*\*/)?\s*=\s*\{\s*isa\s*=?")


def scan(pbxproj_text):
    definitions = defaultdict(list)  # id -> [(注释, 行号)]
    for lineno, line in enumerate(pbxproj_text.splitlines(), 1):
        m = DEF_LINE.match(line)
        if not m:
            continue
        oid = m.group(1).upper()
        comment = (m.group(2) or "").strip()
        definitions[oid].append((comment, lineno))

    duplicates = {
        oid: entries for oid, entries in definitions.items() if len(entries) > 1
    }
    return duplicates, definitions


def main(argv=None):
    if len(argv) != 1:
        print("用法：check_pbxproj_ids.py <project.pbxproj>", file=sys.stderr)
        return 2

    path = Path(argv[0])
    if not path.is_file():
        print(f"pbxproj 不存在：{path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8", errors="replace")
    duplicates, _definitions = scan(text)

    if not duplicates:
        print(f"{path.name}: 无重复 Object ID，通过")
        return 0

    print(f"{path.name}: 发现 {len(duplicates)} 个重复 Object ID（会导致对象被覆盖、"
          f"资源静默丢失）：")
    for oid, entries in sorted(duplicates.items()):
        print(f"  {oid}:")
        for comment, lineno in entries:
            print(f"    行 {lineno}: {comment or '<无注释>'}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
