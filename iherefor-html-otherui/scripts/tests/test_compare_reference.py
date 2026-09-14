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

from PIL import Image

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


def attribution_fixture():
    """造一对图 + 事实表 + 计划，专测具名区域归因。

    布局（120x120）：

    * ``card``（index 0）覆盖整张图，上半 60 行在 actual 里变灰 ⇒ 填充差异；
    * ``badge``（index 1）是 10,70 处 40x30 的小框，框内黑块在 actual 里右移 6px
      ⇒ 框内 180 个像素是结构差异，其中 x=50..55 那 6 列落在框**外**。

    这样一次就能测到三件事：最小包含元素优先（badge 先认领，card 拿不到那 180）、
    互斥且穷尽（区域之和 + unattributed == 整页）、以及计划里的 region 名优先于 DOM 身份。
    """
    width = height = 120
    reference = Image.new("RGB", (width, height), (255, 255, 255))
    actual = reference.copy()
    for y in range(0, 60):
        for x in range(width):
            actual.putpixel((x, y), (200, 200, 200))
    for y in range(70, 100):
        for x in range(10, 50):
            reference.putpixel((x, y), (0, 0, 0))
            actual.putpixel((x, y), (255, 255, 255))
    for y in range(70, 100):
        for x in range(16, 56):
            actual.putpixel((x, y), (0, 0, 0))

    facts = {"schemaVersion": 3, "elements": [
        {"index": 0, "id": "card",
         "rectInReference": {"x": 0, "y": 0, "width": 120, "height": 120}},
        {"index": 1, "className": "badge",
         "rectInReference": {"x": 10, "y": 70, "width": 40, "height": 30}},
    ]}
    plan = {
        "layoutProportions": {"regions": [{"index": 1, "region": "badge.art"}]},
        "unsupported": {"items": [
            {"category": "system-bars", "box": {"x": 0, "y": 0, "width": 120, "height": 20}},
            {"category": "typography"},
        ]},
    }
    return reference, actual, facts, plan


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

        # ---------- 归因：具名区域必须互斥且穷尽，并给出扣除已声明差异后的剩余值 ----------
        #
        # 网格 regions 只说「差在哪一带」，说不出「差在哪个控件」。归因要能定位到控件，
        # 又必须保证「区域之和 + unattributed == 整页」—— 漏算会低估缺陷，重复计算会
        # 把一处错位报成两处。同时钉住两条反向断言：不给 --page-facts 必须记 not-run
        # （不能编一份看起来完整的归因），旧版事实表没有 rectInReference 必须记
        # insufficient-evidence（不能拿 DOM 坐标空间当参考图像素空间用）。
        region_ref, region_act, facts, plan = attribution_fixture()
        rp, ap = tmp / "region-ref.png", tmp / "region-act.png"
        region_ref.save(rp)
        region_act.save(ap)
        (tmp / "page-facts.json").write_text(json.dumps(facts))
        (tmp / "plan.json").write_text(json.dumps(plan))

        _, plain = compare(rp, ap, tmp / "plain.json")
        if plain is None:
            problems.append("归因：未生成 summary.json")
        else:
            attribution = plain.get("attribution") or {}
            if attribution.get("status") != "not-run":
                problems.append(
                    f"归因：未给 --page-facts 时 status={attribution.get('status')!r}，"
                    "应为 'not-run'")
            if attribution.get("reason") is None:
                problems.append("归因：status=not-run 却没有 reason，读的人无从知道缺什么")

        # 旧版事实表（只有 rect、没有 rectInReference）必须判 insufficient-evidence，
        # 不能拿 DOM 的 CSS px 坐标空间当参考图像素空间用。
        (tmp / "legacy-facts.json").write_text(json.dumps(
            {"schemaVersion": 2, "elements": [
                {"index": 0, "id": "card",
                 "rect": {"x": 0, "y": 0, "width": 120, "height": 120}}]}))
        _, legacy = compare(rp, ap, tmp / "legacy.json",
                            extra=("--page-facts", str(tmp / "legacy-facts.json")))
        if legacy is None:
            problems.append("归因：旧版事实表用例未生成 summary.json")
        else:
            attribution = legacy.get("attribution") or {}
            if attribution.get("status") != "insufficient-evidence":
                problems.append(
                    f"归因：旧版事实表（无 rectInReference）被判 {attribution.get('status')!r}，"
                    "应为 'insufficient-evidence'")

        _, data = compare(rp, ap, tmp / "attribution.json",
                          extra=("--page-facts", str(tmp / "page-facts.json"),
                                 "--plan", str(tmp / "plan.json")))
        if data is None:
            problems.append("归因：未生成 summary.json")
        else:
            attribution = data.get("attribution") or {}
            if attribution.get("status") != "ok":
                problems.append(
                    f"归因：status={attribution.get('status')!r}"
                    f"（{attribution.get('reason')}），应为 'ok'")
            else:
                rows = attribution.get("regions") or []
                names = {row.get("region") for row in rows}
                # 计划里的 region 名（badge.art）必须优先于从 DOM 身份猜出来的（badge）
                if "badge.art" not in names:
                    problems.append(
                        f"归因：区域名为 {sorted(names)}，计划里确认过的 'badge.art' 未被采用")
                by_name = {row["region"]: row for row in rows}
                badge = by_name.get("badge.art")
                if badge is None:
                    problems.append("归因：缺少 badge.art 区域")
                else:
                    # 最小包含元素优先：badge 先认领框内那 6 列错位（6*30=180），
                    # 且它们是结构差异、不是填充差异
                    if badge.get("changedPixels") != 180:
                        problems.append(
                            f"归因：badge.art 认领 {badge.get('changedPixels')} 个差异像素，"
                            "应为 180（框内 6 列 x 30 行的错位带）")
                    if badge.get("fillPixels") != 0:
                        problems.append(
                            f"归因：badge.art 的填充差异为 {badge.get('fillPixels')}，应为 0"
                            "（该区域只有几何错位）")
                    if badge.get("structuralRatio") is None:
                        problems.append("归因：区域缺少区域内 structuralRatio")

                unattributed = attribution.get("unattributed") or {}
                attributed_sum = sum(row.get("changedPixels") or 0 for row in rows)
                missing = (unattributed.get("changed") or {}).get("pixels")
                if missing is None:
                    problems.append("归因：缺少 unattributed.changed.pixels")
                elif attributed_sum + missing != data.get("changedPixels"):
                    problems.append(
                        f"归因：区域之和 {attributed_sum} + 未归属 {missing} != "
                        f"整页 {data.get('changedPixels')}，归属必须互斥且穷尽")
                for bucket in ("structural", "texture", "fill"):
                    bucket_sum = sum(row.get(f"{bucket}Pixels") or 0 for row in rows)
                    bucket_missing = (unattributed.get(bucket) or {}).get("pixels")
                    if bucket_missing is None:
                        problems.append(f"归因：缺少 unattributed.{bucket}.pixels")
                    elif bucket_sum + bucket_missing != data.get(f"{bucket}ChangedPixels"):
                        problems.append(
                            f"归因：{bucket} 区域之和 {bucket_sum} + 未归属 {bucket_missing} != "
                            f"整页 {data.get(f'{bucket}ChangedPixels')}")
                shares = attribution.get("attributedShare") or {}
                if set(shares) != {"changed", "structural", "texture", "fill"}:
                    problems.append(f"归因：attributedShare 字段不全：{sorted(shares)}")

                declared = attribution.get("declaredUnsupported") or {}
                if len(declared.get("located") or []) != 1:
                    problems.append(
                        f"归因：declaredUnsupported.located 为 {declared.get('located')}，"
                        "应记录 1 个有坐标的声明项")
                if declared.get("unlocated") != ["typography"]:
                    problems.append(
                        f"归因：declaredUnsupported.unlocated 为 {declared.get('unlocated')}，"
                        "应如实列出没有坐标、扣不掉的声明项 ['typography']")
                residual = attribution.get("residual") or {}
                got = (residual.get("changed") or {}).get("pixels")
                expected_residual = data.get("changedPixels") - 120 * 20
                if got != expected_residual:
                    problems.append(
                        f"归因：residual.changed.pixels={got}，应为 {expected_residual}"
                        f"（整页 {data.get('changedPixels')} 减去已声明区 120x20）")
                for bucket in ("structural", "texture", "fill"):
                    if (residual.get(bucket) or {}).get("pixels") is None:
                        problems.append(f"归因：residual 缺少 {bucket}")

        # ---------- 声明的结构差异下界：只降级、不放宽，且不传时行为不变 ----------
        #
        # 文字密集页的结构差异存在物理下界（基准 scale(1.0229) vs 契约禁止缩放字号），
        # 不可能降到 0。所以计划要显式声明它，而不是让 Agent 反复逼近不存在的 0。
        # 这组用例钉住四条边界：① 只把 fail 降为 pass-with-review，不升为 pass；
        # ② 只对结构差异生效，fillRatio 超标不受豁免；③ 实际值超过下界仍 fail；
        # ④ 不传下界时判定与旧版逐字一致。
        #
        # 用 geometry 合成图（structural 0.1536 > 上限 0.02），并把 --max-fill-ratio 抬高，
        # 让 fill 不参与干扰 —— 本组测的是结构下界，不是颜色阈值。
        geo_ref, geo_act, _, _ = diff_fixture.cases()["geometry"]
        gp, ga = tmp / "floor-ref.png", tmp / "floor-act.png"
        geo_ref.save(gp)
        geo_act.save(ga)
        loose_fill = ("--max-fill-ratio", "0.2")

        _, no_floor = compare(gp, ga, tmp / "no-floor.json", extra=loose_fill)
        if no_floor is None:
            problems.append("下界：未生成 summary.json")
        else:
            if no_floor.get("status") != "fail":
                problems.append(
                    f"下界：未声明下界时 geometry 被判 {no_floor.get('status')!r}，应为 'fail'")
            declared = no_floor.get("declaredStructuralFloor") or {}
            if declared.get("value") is not None or declared.get("source") != "none":
                problems.append(
                    f"下界：未声明时 declaredStructuralFloor 为 {declared}，"
                    "应记 value=None / source='none'")

        _, lifted = compare(gp, ga, tmp / "floor-lifted.json",
                            extra=loose_fill + ("--expected-structural-floor", "0.2"))
        if lifted is None:
            problems.append("下界：声明下界用例未生成 summary.json")
        else:
            if lifted.get("status") != "pass-with-review":
                problems.append(
                    f"下界：0.1536 在声明下界 0.2 内，却判 {lifted.get('status')!r}"
                    f"/{lifted.get('reason')!r}，应为 pass-with-review")
            if lifted.get("reason") != "structural-within-declared-floor":
                problems.append(f"下界：reason 为 {lifted.get('reason')!r}，"
                                "应为 'structural-within-declared-floor'")
            declared = lifted.get("declaredStructuralFloor") or {}
            if declared.get("source") != "cli":
                problems.append(f"下界：来源记作 {declared.get('source')!r}，应为 'cli'")
            if declared.get("withinFloor") is not True:
                problems.append("下界：withinFloor 未记 True，无法事后核对是否真的在下界内")
            headroom = declared.get("headroom")
            if not isinstance(headroom, (int, float)) or headroom <= 0:
                problems.append(f"下界：headroom={headroom!r}，应给出正的结构差异余量")
            if lifted.get("exitCode") != 2:
                problems.append(f"下界：退出码 {lifted.get('exitCode')!r}，应为 2")

        # ③ 超过声明下界仍 fail
        _, exceeded = compare(gp, ga, tmp / "floor-exceeded.json",
                              extra=loose_fill + ("--expected-structural-floor", "0.05"))
        if exceeded is None:
            problems.append("下界：超下界用例未生成 summary.json")
        else:
            if exceeded.get("status") != "fail":
                problems.append(
                    f"下界：0.1536 超过声明下界 0.05，却判 {exceeded.get('status')!r}；"
                    "下界是「不可消除的下界」，不是「豁免额度」")
            declared = exceeded.get("declaredStructuralFloor") or {}
            if declared.get("withinFloor") is not False:
                problems.append("下界：超下界时 withinFloor 未记 False")

        # ② fillRatio 超标不受下界豁免（颜色写错与字号无关）
        _, fill_over = compare(gp, ga, tmp / "floor-fill-over.json",
                               extra=("--max-fill-ratio", "0.02",
                                      "--expected-structural-floor", "0.2"))
        if fill_over is None:
            problems.append("下界：fill 超标用例未生成 summary.json")
        else:
            if fill_over.get("status") != "fail":
                problems.append(
                    f"下界：structural 在下界内但 fillRatio 超标，却判 {fill_over.get('status')!r}；"
                    "下界只对结构差异生效")

        # ① 只降级不放宽：texture 合成图（structural ≈ 0）不能因为声明了下界而变成 pwr
        tex_ref, tex_act, _, _ = diff_fixture.cases()["texture"]
        tp, ta = tmp / "floor-tex-ref.png", tmp / "floor-tex-act.png"
        tex_ref.save(tp)
        tex_act.save(ta)
        _, not_upgraded = compare(tp, ta, tmp / "floor-no-upgrade.json",
                                  extra=("--expected-structural-floor", "0.5"))
        if not_upgraded is None:
            problems.append("下界：不升格用例未生成 summary.json")
        elif not_upgraded.get("status") != "pass":
            problems.append(
                f"下界：structural 在告警线以下却因声明下界被判 {not_upgraded.get('status')!r}；"
                "下界只能把 fail 降为 pass-with-review，不能升格")

        # 计划里的 gateReachability 能自动提供下界（source 记 'plan'）
        (tmp / "floor-plan.json").write_text(json.dumps(
            {"gateReachability": {"expectedStructuralFloor": 0.2,
                                  "unavoidable": [{"category": "typography",
                                                   "cause": "baseline-scale-vs-fixed-font-size",
                                                   "measuredShare": 0.01563}]}}))
        _, from_plan = compare(gp, ga, tmp / "floor-from-plan.json",
                               extra=loose_fill + ("--plan", str(tmp / "floor-plan.json")))
        if from_plan is None:
            problems.append("下界：计划提供下界用例未生成 summary.json")
        else:
            declared = from_plan.get("declaredStructuralFloor") or {}
            if declared.get("source") != "plan" or declared.get("value") != 0.2:
                problems.append(
                    f"下界：计划里的 0.2 未被采用（{declared}），来源应记 'plan'")
            if from_plan.get("status") != "pass-with-review":
                problems.append(
                    f"下界：计划提供下界后仍判 {from_plan.get('status')!r}，应为 pass-with-review")

        # 下界低于上限是无意义的，必须报错而不是静默接受
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--reference", str(gp), "--actual", str(ga),
             "--output", str(tmp / "floor-bad.json"),
             "--expected-structural-floor", "0.01"],
            capture_output=True, text=True)
        if proc.returncode == 0:
            problems.append("下界：--expected-structural-floor 小于 --max-structural-ratio 时应报错退出")

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
          "尺寸不一致必 fail，自比必 pass；具名区域归因互斥且穷尽，并给出扣除后的剩余值；"
          "声明的结构差异下界只把 fail 降为 pass-with-review（不升格、不豁免 fill、超下界仍 fail）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
