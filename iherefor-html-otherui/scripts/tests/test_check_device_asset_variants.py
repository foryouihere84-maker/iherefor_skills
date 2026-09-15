#!/usr/bin/env python3
"""回归：双稿资源分档清单（``check_device_asset_variants.py``）。

把「逐字节比对两份设备稿同名资源」固化成机器门。测试盯：

1. **召回**：md5 不同的同名资源要进 variants，且 phone/tablet 的 md5+pixelSize+bytes 齐全；
2. **精度**：md5 逐字节相同的共享，不进 variants（same 计数正确）；
3. **单边文件**：仅手机 / 仅 iPad 出现的文件各自进 phoneOnly / tabletOnly，不误配；
4. **干净退出**：无差异时 variantCount=0、退出 0；
5. **用法错误退出 2**：缺 --phone-dir / --tablet-dir 时干净报错。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_device_asset_variants.py"


def _png(path, size, color):
    Image.new("RGBA", size, color).save(path)


def run(phone_dir, tablet_dir):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--phone-dir", str(phone_dir), "--tablet-dir", str(tablet_dir)],
        capture_output=True, text=True)
    if "Traceback" in proc.stderr:
        raise AssertionError(f"脚本抛栈：{proc.stderr.strip()[-600:]}")
    data = json.loads(proc.stdout) if proc.returncode == 0 else None
    return proc.returncode, data


def main():
    problems = []

    def check(condition, message):
        if not condition:
            problems.append(message)

    with tempfile.TemporaryDirectory() as scratch:
        tmp = Path(scratch)
        phone = tmp / "phone"; tablet = tmp / "tablet"
        phone.mkdir(); tablet.mkdir()

        # 用例 1：不同 → variant；相同 → same；单边 → phoneOnly/tabletOnly
        _png(phone / "img_4.png", (393, 365), (100, 100, 100, 255))   # hero 不同
        _png(tablet / "img_4.png", (810, 396), (100, 100, 100, 255))
        _png(phone / "img_0.png", (17, 11), (0, 0, 0, 255))           # 相同
        _png(tablet / "img_0.png", (17, 11), (0, 0, 0, 255))
        _png(tablet / "img_9.png", (44, 44), (1, 2, 3, 255))          # 仅 iPad

        code, data = run(phone, tablet)
        check(code == 0, f"用例1：应退出 0，实得 {code}")
        check(data["variantCount"] == 1, f"用例1：variantCount 应为 1，实得 {data['variantCount']}")
        check(data["sameCount"] == 1, f"用例1：sameCount 应为 1，实得 {data['sameCount']}")
        check(data["tabletOnly"] == ["img_9.png"], f"用例1：tabletOnly 应含 img_9.png，实得 {data['tabletOnly']}")
        v = data["variants"][0]
        check(v["sourceName"] == "img_4.png", f"用例1：variant 应 img_4.png，实得 {v['sourceName']}")
        check(v["phone"]["md5"] != v["tablet"]["md5"], "用例1：两稿 md5 应不同")
        check(v["phone"]["pixelSize"] == {"width": 393, "height": 365}, "用例1：phone 尺寸错")
        check(v["tablet"]["pixelSize"] == {"width": 810, "height": 396}, "用例1：tablet 尺寸错")

        # 用例 2：全部相同 → 0 variant
        phone2 = tmp / "phone2"; tablet2 = tmp / "tablet2"
        phone2.mkdir(); tablet2.mkdir()
        _png(phone2 / "img_0.png", (17, 11), (0, 0, 0, 255))
        _png(tablet2 / "img_0.png", (17, 11), (0, 0, 0, 255))
        code2, data2 = run(phone2, tablet2)
        check(code2 == 0 and data2["variantCount"] == 0,
              f"用例2：无差异应 0 variant，实得 {data2 and data2['variantCount']}")

        # 用例 3：用法错误 → 退出 2
        proc = subprocess.run([sys.executable, str(SCRIPT)],
                              capture_output=True, text=True)
        check(proc.returncode == 2, f"用例3：缺参应退出 2，实得 {proc.returncode}")

    if problems:
        print("资源分档清单未满足：\n  " + "\n  ".join(problems))
        return 1
    print("资源分档清单：不同→variant、相同→same、单边→phoneOnly/tabletOnly、无差异干净退出、用法错误退出 2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
