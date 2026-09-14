#!/usr/bin/env python3
"""比较器回归：三分法必须把结构/纹理/填充分到正确的桶，且只对真缺陷设阈值。

**这一组用例在防什么。** 早期实现的规则是「差异像素落在任一方的边缘带上即结构
差异」。它看起来没问题，实际有个致命缺陷：**抗锯齿差异本身就长在边缘上**，所以
「HTML 用 Web 字体、App 用系统字体」这种纯栅格化差异会被全部算成结构差异，页面
永远撞上限、无法交付 —— 正是要避免的双输。而真正要抓的两类缺陷（几何错位、颜色
写错）反而可能因为分类错误而混进「纹理差异」被放过。

所以合成样本是必需的：真实事故样本只告诉你「这一张该 fail」，不告诉你「一张只有
纹理差异的图不该 fail」。四类样本的构造与期望见 ``diff_fixture.py``。

**阈值是标定出来的，不是拍的。** 下表是用 ``diff_fixture`` 扫 ``--edge-tolerance``
得到的（content dilate = 0）：

    tolerance  sample          changed  struct   texture  fill
        1      geometry(3px)   0.22468  0.12793  0.01422  0.08253
        1      fill           0.34988  0.00567  0.02328  0.32093
        1      ink            0.03751  0.00003  0.01014  0.02733
        1      texture(0.5px) 0.02191  0.01637  0.00407  0.00147   ← 结构被误判
        2      geometry(3px)   0.22468  0.15355  0.00973  0.06139
        2      geometry(6px)   0.31922  0.14019  0.02714  0.15188
        2      fill           0.34988  0.00841  0.02331  0.31817
        2      ink            0.03751  0.00000  0.01016  0.02734
        2      texture(0.5px) 0.02191  0.00000  0.01467  0.00724   ← 干净分离
        3      texture(0.5px) 0.02191  0.00000  0.01467  0.00724

``tolerance = 1`` 时次像素相位差仍被判成结构差异（0.01637 > 告警线 0.005）；``2`` 时
归零。取 2：在 scale 3 的截图上等于 0.67pt，远小于契约要求的 2pt 位置容差，所以不会
放过真实的错位。

另有一处容易踩的坑：内容图（判断「是不是纯色块」的图）**不能**按 tolerance 膨胀。
一膨胀，几像素高的文字笔画就整条被划进「有内容」，于是「文字颜色写错」这种纯颜色
缺陷会被算成纹理差异而放过。``ink`` 用例就是这条的守卫。抗锯齿斜坡已经由低阈值
覆盖，不需要膨胀。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "scripts" / "tests" / "fixtures"
SCRIPT = ROOT / "scripts" / "compare_reference.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diff_fixture  # noqa: E402


def compare(reference, actual, out_path, extra=()):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--reference", str(reference), "--actual", str(actual),
         "--output", str(out_path), *extra],
        capture_output=True, text=True,
    )
    data = json.loads(out_path.read_text()) if out_path.exists() else None
    return proc.returncode, data


def dominant(data):
    """返回差异占比最大的桶名（structural / texture / fill）。"""
    buckets = {name: data[f"{name}Ratio"] for name in ("structural", "texture", "fill")}
    return max(buckets, key=buckets.get)


def check_exhaustive(problems, label, data):
    """结构 + 纹理 + 填充必须互斥且穷尽，加起来等于全部差异像素。"""
    parts = [data.get("structuralChangedPixels"), data.get("textureChangedPixels"),
             data.get("fillChangedPixels")]
    if any(not isinstance(p, int) for p in parts):
        problems.append(f"{label}：结构/纹理/填充像素数缺失：{parts}")
    elif sum(parts) != data.get("changedPixels"):
        problems.append(
            f"{label}：三分之和 {sum(parts)} != changedPixels {data.get('changedPixels')}，"
            "三类必须互斥且穷尽")


def main():
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # ---------- 合成真值：四类差异必须落对桶，且只有真缺陷判 fail ----------
        cases = diff_fixture.cases()   # {名字: (reference, actual, 期望判定, 期望桶)}
        for name, (reference, actual, expected, bucket) in cases.items():
            ref_png, act_png = tmp / f"{name}-ref.png", tmp / f"{name}-act.png"
            reference.save(ref_png)
            actual.save(act_png)
            code, data = compare(ref_png, act_png, tmp / f"{name}.json")
            if data is None:
                problems.append(f"合成/{name}：未生成 summary.json")
                continue
            check_exhaustive(problems, f"合成/{name}", data)
            if data.get("status") != expected:
                problems.append(
                    f"合成/{name}：判定为 {data.get('status')!r}（{data.get('reason')}），"
                    f"期望 {expected!r}；"
                    f"struct={data.get('structuralRatio')} texture={data.get('textureRatio')} "
                    f"fill={data.get('fillRatio')}")
            found = dominant(data)
            if found != bucket:
                problems.append(
                    f"合成/{name}：差异落在 {found} 桶，期望 {bucket} 桶；"
                    f"struct={data.get('structuralRatio')} texture={data.get('textureRatio')} "
                    f"fill={data.get('fillRatio')}")
            if (code == 0) != (expected == "pass"):
                problems.append(f"合成/{name}：退出码 {code} 与判定 {expected} 不一致")

        # 逐条把「这一类的判据」写死，避免将来有人放宽阈值时静默退化。
        expected_checks = {
            # 几何错位：结构差异必须显著，且必须是最大桶
            "geometry": lambda d: d["structuralRatio"] > 0.02,
            # 填充写错：平坦区差异必须超过上限并单独触发 fail
            "fill": lambda d: d["fillRatio"] > 0.02 and d["reason"] == "fill-diff-exceeded",
            # 文字颜色写错：纯颜色缺陷，结构差异必须为零 —— 否则就是又把它误判成几何问题
            "ink": lambda d: d["structuralRatio"] < 0.005 and d["reason"] == "fill-diff-exceeded",
            # 栅格化相位差：结构差异与填充差异都必须干净，否则 Web 字体的页面永远过不了
            "texture": lambda d: d["structuralRatio"] <= 0.005 and d["fillRatio"] <= 0.02,
        }
        for name, predicate in expected_checks.items():
            path = tmp / f"{name}.json"
            if not path.exists():
                continue
            data = json.loads(path.read_text())
            if not predicate(data):
                problems.append(
                    f"合成/{name}：判据未满足 —— struct={data['structuralRatio']} "
                    f"texture={data['textureRatio']} fill={data['fillRatio']} "
                    f"reason={data.get('reason')}")

        # ---------- 事故现场：同尺寸约 40% 差异，必须 fail ----------
        code, data = compare(FIX / "reference.png", FIX / "actual-device-downscaled.png",
                             tmp / "acc.json")
        if data is None:
            problems.append("事故现场：未生成 summary.json")
        else:
            if data.get("status") != "fail":
                problems.append(f"事故现场：被判为 {data.get('status')!r}，必须为 'fail'")
            if code == 0:
                problems.append("事故现场：退出码为 0，必须非 0")
            ratio = data.get("changedRatio")
            if not isinstance(ratio, (int, float)) or ratio < 0.3:
                problems.append("事故现场：changedRatio 缺失或与样本不符")
            for field in ("maxStructuralRatio", "warnStructuralRatio", "maxFillRatio",
                          "referenceSize", "actualSize", "edgeTolerance"):
                if field not in data:
                    problems.append(f"事故现场：summary 缺少字段 {field}")
            check_exhaustive(problems, "事故现场", data)
            if not isinstance(data.get("structuralRatio"), (int, float)):
                problems.append("事故现场：缺少 structuralRatio")
            elif data["structuralRatio"] <= 0.02:
                problems.append(
                    f"事故现场：结构差异只有 {data['structuralRatio']:.4f}，"
                    "预期内容错位会表现为显著的结构差异")
            if dominant(data) == "texture":
                problems.append(
                    "事故现场：整体错位被归为纹理差异，阈值就不会拦住它了")
            if not isinstance(data.get("regions"), list) or not data["regions"]:
                problems.append("事故现场：缺少区域级差异明细 regions")
            elif not data.get("worstRegions"):
                problems.append("事故现场：最差区域为空，无法定位问题在哪一带")

        # ---------- 尺寸不一致：必须 fail 且原因为 size-mismatch ----------
        code2, data2 = compare(FIX / "reference.png", FIX / "actual-device.png", tmp / "b.json")
        if data2 is None:
            problems.append("尺寸不一致：未生成 summary.json")
        else:
            if data2.get("status") != "fail":
                problems.append("尺寸不一致：未被判 fail")
            if data2.get("reason") != "size-mismatch":
                problems.append(f"尺寸不一致：reason 为 {data2.get('reason')!r}，应为 'size-mismatch'")
            if code2 == 0:
                problems.append("尺寸不一致：退出码为 0，必须非 0")

        # ---------- 自比：必须 pass（防止「一律判 fail」的退化修复）----------
        code3, data3 = compare(FIX / "reference.png", FIX / "reference.png", tmp / "c.json")
        if data3 is None:
            problems.append("自比：未生成 summary.json")
        else:
            if data3.get("status") != "pass":
                problems.append(f"自比：零差异被判为 {data3.get('status')!r}，必须为 'pass'")
            if code3 != 0:
                problems.append("自比：零差异时退出码非 0，必须为 0")

        # 自比 + 结构阈值压到 0：纹理差异再大也不能触发 fail（阈值只作用于结构/填充）
        code4, data4 = compare(FIX / "reference.png", FIX / "reference.png",
                               tmp / "d.json",
                               extra=("--max-structural-ratio", "0.0",
                                      "--warn-structural-ratio", "0.0"))
        if data4 is None:
            problems.append("自比(阈值0)：未生成 summary.json")
        elif data4.get("status") != "pass":
            problems.append(
                f"自比(阈值0)：被判为 {data4.get('status')!r}，阈值应只作用于结构/填充差异")

        # ---------- 参数校验：告警线不能大于上限 ----------
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--reference", str(FIX / "reference.png"),
             "--actual", str(FIX / "reference.png"), "--output", str(tmp / "e.json"),
             "--warn-structural-ratio", "0.5", "--max-structural-ratio", "0.1"],
            capture_output=True, text=True)
        if proc.returncode == 0:
            problems.append("参数校验：warn > max 时应报错退出")

    for p in problems:
        print(p)
    if problems:
        print("比较器未满足契约：三分法必须分对桶，且只对结构/填充差异设阈值")
        return 1
    print("结构/纹理/填充三分正确：几何与颜色缺陷必 fail，栅格化差异必 pass，"
          "尺寸不一致必 fail，自比必 pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
