#!/usr/bin/env python3
"""回归：渲染前的动画/过渡禁用注入必须真正落在页面上。

render_reference.mjs 若在 page.goto() 之前调用 addStyleTag，样式会随 about:blank
文档一起被丢弃。本测试断言的是「注入后回读 DOM」的页面事实
（browser-meta.json 的 styleInjection.presentInDom），而不是脚本的自我声明。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "scripts" / "tests" / "fixtures"


def main():
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            ["node", str(ROOT / "scripts" / "render_reference.mjs"),
             "--input", str(FIX / "animated.html"),
             "--output", tmp,
             "--viewport", "200x200", "--scale", "1"],
            capture_output=True, text=True,
        )
        meta_path = Path(tmp) / "browser-meta.json"
        if proc.returncode != 0 or not meta_path.exists():
            print(f"render_reference.mjs 执行失败：{(proc.stderr or proc.stdout).strip()[:400]}")
            return 1

        meta = json.loads(meta_path.read_text())
        injection = meta.get("styleInjection")
        if not injection:
            print("browser-meta.json 缺少 styleInjection：无法证明禁用动画的样式真正生效")
            return 1
        if not injection.get("presentInDom"):
            print("注入的样式未出现在最终 DOM 中（addStyleTag 在 goto 之前被执行后丢失）")
            return 1
        if not injection.get("css"):
            print("styleInjection 未记录注入内容")
            return 1

    print("动画/过渡禁用样式已注入且存在于最终 DOM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
