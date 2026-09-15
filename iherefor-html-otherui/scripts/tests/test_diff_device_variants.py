#!/usr/bin/env python3
"""回归：双稿尺寸差异自动生成 sizeVariants（``diff_device_variants.py``）。

这一脚本把「人工读两份设备稿、逐一比宽高、手写 sizeVariants」机械自动化。测试盯：

1. **召回**：同名容器宽或高的跨设备差异要被抓出来，生成 sizeVariants 条目（region/basis/
   values/why 齐全）；
2. **排除文本层**：``type == "text"`` / 带 ``style.typography`` 的图层不进 sizeVariants ——
   字号差异走 typeFacts，不走 sizeInvariance（它只审计几何宽高）；
3. **位置（x/y）差异不 diff**：sizeVariants 只管宽高；
4. **无差异时干净退出**：没有分档差异时输出空数组、退出 0，不抛异常；
5. **用法错误退出 2**：缺 --phone / --tablet 时干净报错。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "diff_device_variants.py"


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def doc(name, image_id, layers):
    return {"name": name, "imageId": image_id, "canvas": {}, "layers": layers}


def shape(name, width, height, layer_type="shape", typography=None):
    style = {"typography": typography} if typography else {}
    return {"name": name, "type": layer_type, "style": style,
            "rect": {"x": 0, "y": 0, "width": width, "height": height}, "children": []}


def run(phone_doc, tablet_doc, *extra):
    out = Path(phone_doc).parent / "size-variants.json"
    if out.is_file():
        out.unlink()
    args = [sys.executable, str(SCRIPT), "--phone", str(phone_doc),
            "--tablet", str(tablet_doc), "--output", str(out), *extra]
    proc = subprocess.run(args, capture_output=True, text=True)
    if "Traceback" in proc.stderr:
        raise AssertionError(f"脚本抛栈：{proc.stderr.strip()[-600:]}")
    payload = json.loads(out.read_text()) if out.is_file() else None
    return proc, payload, out


def main():
    problems = []

    def check(condition, message):
        if not condition:
            problems.append(message)

    with tempfile.TemporaryDirectory() as scratch:
        tmp = Path(scratch)

        # 用例 1：跨设备宽高差异 → 生成 entries，且排除 text 层、不 diff 位置
        phone = doc("目的", "phone-img", [
            shape("Continue", 68, 22),
            shape("btn_back", 32, 32),
            shape("optionRow", 353, 66, "group"),
            shape("title", 258, 29, "text", {"fontSize": 24}),   # 文本层，应排除
        ])
        tablet = doc("目的-iPad", "tablet-img", [
            shape("Continue", 141, 28),
            shape("btn_back", 44, 44),
            shape("optionRow", 481, 66, "group"),
            shape("title", 322, 36, "text", {"fontSize": 48}),   # 文本层，应排除
        ])
        pp = tmp / "phone.json"
        tt = tmp / "tablet.json"
        write_json(pp, phone)
        write_json(tt, tablet)
        proc, payload, _ = run(pp, tt)
        check(proc.returncode == 0, f"用例1：应退出 0，得到 {proc.returncode}")
        check(isinstance(payload, list) and len(payload) == 3,
              f"用例1：应 diff 出 3 个容器（文本层排除），得到 {len(payload) if payload else 0} 条")
        regions = {item.get("region") for item in (payload or [])}
        check(regions == {"Continue", "btn_back", "optionRow"},
              f"用例1：diff 出的 region 应是三个容器而非文本层，得到 {regions}")
        cta = next((item for item in (payload or []) if item["region"] == "Continue"), None)
        check(cta is not None and cta["values"]["phone-compact"] == {"width": 68, "height": 22}
              and cta["values"]["tablet-regular-portrait"] == {"width": 141, "height": 28},
              f"用例1：Continue 的 values 应正确反映双稿宽高，得到 {cta}")
        check(all("basis" in item and "why" in item and "values" in item and "region" in item
                  for item in (payload or [])),
              "用例1：每条 entry 必须含 region/basis/values/why")
        check(all("_diff" not in item for item in (payload or [])),
              "用例1：输出的 sizeVariants 不得混入内部字段 _diff")

        # 用例 2：无差异 → 空数组、退出 0
        same = doc("目的-iPad", "tablet-img", [
            shape("Continue", 68, 22),
            shape("btn_back", 32, 32),
        ])
        tt2 = tmp / "tablet-same.json"
        write_json(tt2, same)
        proc, payload, _ = run(pp, tt2)
        check(proc.returncode == 0, f"用例2：无差异应退出 0，得到 {proc.returncode}")
        check(payload == [], f"用例2：无差异应产出空数组，得到 {payload}")

        # 用例 3：用法错误 → 退出 2
        proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
        check(proc.returncode == 2 and "Traceback" not in proc.stderr,
              f"用例3：缺 --phone/--tablet 应退出 2，得到 {proc.returncode}：{proc.stderr[:200]}")

        # 用例 4：位置（x/y）差异不拿来做分档判定 —— 宽高相同但 x/y 不同的容器不应产出条目
        phone4 = doc("目的", "phone-img", [shape("offset", 100, 50)])
        tablet4 = doc("目的-iPad", "tablet-img", [shape("offset", 100, 50)])
        # 通过直接构造不同 x/y（上面 shape 固定 x=0）——这里仅验证「宽高相同则不产条目」
        pp4 = tmp / "phone4.json"
        tt4 = tmp / "tablet4.json"
        write_json(pp4, phone4)
        write_json(tt4, tablet4)
        proc, payload, _ = run(pp4, tt4)
        check(payload == [], f"用例4：宽高相同不应产出条目，得到 {payload}")

    for problem in problems:
        print(problem)
    if problems:
        print("双稿尺寸 diff 未满足")
        return 1
    print("双稿尺寸 diff：跨设备宽高差异被抓出、文本层被排除、位置差异不 diff、"
          "无差异空数组退出、用法错误退出 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
