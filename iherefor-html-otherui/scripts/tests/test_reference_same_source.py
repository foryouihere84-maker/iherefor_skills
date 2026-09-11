#!/usr/bin/env python3
"""回归：基准图必须与目标设备截图同源。

--viewport-from 应从 runtime-device.json 取点尺寸与 scale，使 reference.png 的像素
尺寸等于 screenshotPixels；默认只截视口，避免整页文档高度混进比对坐标系。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "scripts" / "tests" / "fixtures"


def main():
    problems = []
    device = json.loads((FIX / "runtime-device.json").read_text())
    expected = device["screenshotPixels"]

    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            ["node", str(ROOT / "scripts" / "render_reference.mjs"),
             "--input", str(FIX / "animated.html"),
             "--output", tmp,
             "--viewport-from", str(FIX / "runtime-device.json")],
            capture_output=True, text=True,
        )
        meta_path = Path(tmp) / "browser-meta.json"
        png_path = Path(tmp) / "reference.png"
        if proc.returncode != 0 or not meta_path.exists():
            print(f"render_reference.mjs 执行失败：{(proc.stderr or proc.stdout).strip()[:300]}")
            return 1

        meta = json.loads(meta_path.read_text())
        size = Image.open(png_path).size
        if size != (expected["width"], expected["height"]):
            problems.append(
                f"基准图像素尺寸 {size[0]}x{size[1]} 与设备截图 "
                f"{expected['width']}x{expected['height']} 不一致"
            )
        if meta.get("viewport") != {"width": device["screenBoundsPoints"]["width"],
                                    "height": device["screenBoundsPoints"]["height"]}:
            problems.append(f"viewport 未取自 runtime-device：{meta.get('viewport')}")
        if meta.get("scale") != device["screenshotScale"]:
            problems.append(f"scale 未取自 runtime-device：{meta.get('scale')}")
        if meta.get("fullPage") is not False:
            problems.append("默认必须只截视口（fullPage=false）")
        if not str(meta.get("viewportSource", "")).startswith("runtime-device:"):
            problems.append("browser-meta 未记录 viewport 来源")

    for p in problems:
        print(p)
    if problems:
        return 1
    print(f"基准图与设备截图同源（{expected['width']}x{expected['height']}），且默认只截视口")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
