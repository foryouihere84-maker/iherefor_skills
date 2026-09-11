#!/usr/bin/env python3
"""回归：高差异必须判 fail，尺寸不一致必须判 fail，完全一致必须判 pass。

事故样本见 fixtures/README.md：run 011 在 changedRatio=0.375 时被判 pass。
第三个用例（同一张图自比）用于防止「一律判 fail」的退化修复。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "scripts" / "tests" / "fixtures"
SCRIPT = ROOT / "scripts" / "compare_reference.py"


def compare(reference, actual, out_path, extra=()):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--reference", str(reference), "--actual", str(actual),
         "--output", str(out_path), *extra],
        capture_output=True, text=True,
    )
    data = json.loads(out_path.read_text()) if out_path.exists() else None
    return proc.returncode, data


def main():
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # 用例 1：同尺寸、约 37.5% 差异 —— 事故现场，必须 fail
        code, data = compare(FIX / "reference.png", FIX / "actual-device-downscaled.png", tmp / "a.json")
        if data is None:
            problems.append("用例1：未生成 summary.json")
        else:
            if data.get("status") != "fail":
                problems.append(f"用例1：37.5% 差异被判为 {data.get('status')!r}，必须为 'fail'")
            if code == 0:
                problems.append("用例1：高差异场景退出码为 0，必须非 0")
            ratio = data.get("changedRatio")
            if not isinstance(ratio, (int, float)) or ratio < 0.3:
                problems.append("用例1：changedRatio 缺失或与事故样本不符")
            for field in ("maxChangedRatio", "warnChangedRatio", "referenceSize", "actualSize"):
                if field not in data:
                    problems.append(f"用例1：summary 缺少字段 {field}")

        # 用例 2：尺寸不一致 —— 必须 fail，且原因为 size-mismatch
        code2, data2 = compare(FIX / "reference.png", FIX / "actual-device.png", tmp / "b.json")
        if data2 is None:
            problems.append("用例2：未生成 summary.json")
        else:
            if data2.get("status") != "fail":
                problems.append("用例2：尺寸不一致未被判 fail")
            if data2.get("reason") != "size-mismatch":
                problems.append(f"用例2：reason 为 {data2.get('reason')!r}，应为 'size-mismatch'")
            if code2 == 0:
                problems.append("用例2：尺寸不一致时退出码为 0，必须非 0")

        # 用例 3：同一张图自比 —— 必须 pass（防止退化修复）
        code3, data3 = compare(FIX / "reference.png", FIX / "reference.png", tmp / "c.json")
        if data3 is None:
            problems.append("用例3：未生成 summary.json")
        else:
            if data3.get("status") != "pass":
                problems.append(f"用例3：零差异被判为 {data3.get('status')!r}，必须为 'pass'")
            if code3 != 0:
                problems.append("用例3：零差异时退出码非 0，必须为 0")

    for p in problems:
        print(p)
    if problems:
        print("比较器未满足契约：高差异与尺寸不一致都必须阻塞交付")
        return 1
    print("高差异判 fail、尺寸不一致判 fail、零差异判 pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
