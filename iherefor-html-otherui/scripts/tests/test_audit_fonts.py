#!/usr/bin/env python3
"""回归：字体链审计必须能区分「声明的族没落地」与「只是族名格式不同」。

这条链是 run 011 事故里最隐蔽的一层：CSS 声明 `AvenirLT-Black`、`@font-face` 规则数为 0、
无 generic fallback，Chromium 静默回落到 Times，于是 DOM 与基准图「一致地一起错」。
本测试固定三件事：

1. **召回**：真替换必须被查出来，并落到具体元素上。
2. **精度**：族名格式差异（`Avenir-Medium` vs `Avenir Medium`）**不能**报成替换 ——
   实测真实事故页 18 个文本元素里 14 个是这种格式差异，误报就等于把闸门焊死。
3. **拒绝猜测**：没有做字体测量的事实表（旧 schema）必须判「证据不足」，而不是判 clean。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit_fonts.py"
FALLBACK = ROOT / "evals" / "fixtures" / "font-fallback" / "workspace" / "reference"


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def run(tmp, page_facts, browser_meta=None, name="out.json"):
    """跑一次审计，返回 (退出码, 结果文档)。"""
    facts_path = tmp / f"{name}.page-facts.json"
    write_json(facts_path, page_facts)
    out = tmp / name
    args = [sys.executable, str(SCRIPT), "--page-facts", str(facts_path),
            "--output", str(out), "--quiet"]
    if browser_meta is not None:
        meta_path = tmp / f"{name}.browser-meta.json"
        write_json(meta_path, browser_meta)
        args += ["--browser-meta", str(meta_path)]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode not in (0, 1, 2):
        return None, {"stderr": proc.stderr, "stdout": proc.stdout}
    return proc.returncode, json.loads(out.read_text())


def text_element(index, declared, resolved, **extra):
    """一个文本元素：CSS 声明的族 + 运行时实际用上的族。"""
    element = {
        "index": index, "tag": "span", "ownsText": True,
        "ownText": extra.pop("ownText", f"text{index}"),
        "fontFamily": declared,
        "primaryFont": {"family": resolved, "glyphCount": 10, "isCustomFont": False},
    }
    element.update(extra)
    return element


def meta(font_face_rules=None, declared_families=None, ok=True, join_ok=True):
    return {
        "schemaVersion": 2,
        "fontProbe": {"declaredFamilies": declared_families or [],
                      "fontFaceRules": font_face_rules if font_face_rules is not None else []},
        "fontMeasurement": {"ok": ok, "method": "cdp:CSS.getPlatformFontsForNode"},
        "fontJoin": {"ok": join_ok, "textMarkMismatchCount": 0, "unjoinedIndexes": []},
    }


def main():
    problems = []

    def expect(condition, message):
        if not condition:
            problems.append(message)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # ---- 用例 1：真替换必须被查出来，且落到具体元素上 ----
        code, result = run(tmp, {
            "elements": [
                text_element(3, "AvenirLT-Black", "Times", ownText="Choose Your Plan"),
                text_element(7, "AvenirLT-Medium", "Times", ownText="$59.99"),
                text_element(9, "PingFang SC", "PingFang SC", ownText="Try For Free"),
            ]}, meta(declared_families=["AvenirLT-Black", "AvenirLT-Medium", "PingFang SC"]),
            "substituted.json")
        expect(code == 1, f"用例1：真替换未判 exit 1，得到 {code}")
        expect(result.get("substituted") is True, "用例1：substituted 不是 true")
        expect(result.get("status") == "substituted", "用例1：status 不是 substituted")
        expect(result.get("fixSide") == "baseline",
               f"用例1：fixSide 不是 baseline，得到 {result.get('fixSide')!r}")
        affected = result.get("affectedElements") or []
        expect(len(affected) == 2, f"用例1：受影响元素数不是 2，得到 {len(affected)}")
        expect([a["index"] for a in affected] == [3, 7], "用例1：受影响元素不是 index 3/7")
        expect("AvenirLT-Black" in (result.get("missingFamilies") or []),
               "用例1：missingFamilies 未点名声明却没落地的族")
        expect("Times" in (result.get("landedFamilies") or []),
               "用例1：landedFamilies 未点名实际回落到的族")
        expect(result.get("fontFaceRuleCount") == 0,
               "用例1：未记录 @font-face 规则数")
        evidence = " ".join(result.get("evidence") or [])
        expect("AvenirLT-Black" in evidence and "Times" in evidence,
               "用例1：evidence 没有给出具体的族名对照")
        # 对照组必须被识别出来，否则「不匹配是不是测量噪声」无从排除
        expect("对照组" in evidence, "用例1：没有指出同一页的对照组（解析正确的元素）")
        expect(all(a.get("mechanism") == "silent-default-fallback" for a in affected),
               "用例1：无 generic 兜底的替换未被判为 silent-default-fallback")

        # ---- 用例 2【变异探针】族名格式差异不能被报成替换 ----
        # 这是真实事故页的形态：CSS 写 Avenir-Medium，CDP 的 familyName 报 Avenir Medium。
        # 没有归一化的话，18 个元素里 14 个都会被报成替换。
        code, result = run(tmp, {
            "elements": [
                text_element(1, "Avenir-Medium", "Avenir Medium"),
                text_element(2, "Avenir-Heavy", "Avenir Heavy"),
                text_element(3, "Times", "Times-Roman"),
                text_element(4, "PingFang SC", "PingFang SC"),
            ]}, meta(declared_families=["Avenir-Medium"]), "formatting.json")
        expect(code == 0, f"用例2：族名格式差异被误报成替换（exit {code}）")
        expect(result.get("substituted") is False, "用例2：substituted 不是 false")
        expect(result.get("status") == "clean", "用例2：status 不是 clean")
        expect(not (result.get("affectedElements") or []), "用例2：clean 却列出了受影响元素")

        # ---- 用例 3：把一条比例换成真替换，必须立刻变红（证明用例 2 不是空的）----
        code, result = run(tmp, {
            "elements": [
                text_element(1, "Avenir-Medium", "Avenir Medium"),
                text_element(2, "Avenir-Heavy", "Avenir Black"),   # 声明 Heavy，来了 Black
                text_element(3, "Times", "Times-Roman"),
            ]}, meta(), "probe.json")
        expect(code == 1, f"用例3：同一份素材里换掉一个族的字重后未被查出（exit {code}）")
        expect([a["index"] for a in (result.get("affectedElements") or [])] == [2],
               "用例3：受影响元素定位不对")

        # ---- 用例 4：没做字体测量的旧事实表必须判证据不足，不能判 clean ----
        code, result = run(tmp, {
            "elements": [{"index": 0, "tag": "div", "text": "no runtime font here",
                          "style": {"fontFamily": "AvenirLT-Black"}}]}, None, "unmeasured.json")
        expect(code == 2, f"用例4：未做字体测量却未判证据不足，得到 {code}")
        expect(result.get("status") == "insufficient-evidence", "用例4：status 不对")
        expect(result.get("substituted") is None,
               "用例4：证据不足时 substituted 必须为 null（不得猜成 false）")
        expect(result.get("fixSide") == "none", "用例4：证据不足时不该指向任何一侧")
        expect(any("字体测量" in w for w in (result.get("warnings") or [])),
               "用例4：没有告警说明「这份事实表没做过字体测量」")

        # ---- 用例 5：没有文本元素 → 证据不足 ----
        code, result = run(tmp, {"elements": [{"index": 0, "tag": "img", "src": "a.png"}]},
                           None, "notext.json")
        expect(code == 2, f"用例5：没有文本元素却未判证据不足，得到 {code}")

        # ---- 用例 6：测量链路自身失败（fontMeasurement.ok=false）→ 证据不足 ----
        code, result = run(tmp, {
            "elements": [text_element(1, "AvenirLT-Black", "Times")]},
            meta(ok=False), "measurement-failed.json")
        expect(code == 2, f"用例6：测量失败却下了结论，得到 {code}")
        expect(any("fontMeasurement" in w for w in (result.get("warnings") or [])),
               "用例6：没有告警点明测量链路失败")

        # ---- 用例 7：index 空间漂移（fontJoin.ok=false）→ 归属不可信，判证据不足 ----
        code, result = run(tmp, {
            "elements": [text_element(1, "AvenirLT-Black", "Times")]},
            {"fontJoin": {"ok": False, "textMarkMismatchCount": 2},
             "fontMeasurement": {"ok": True}}, "join-broken.json")
        expect(code == 2, f"用例7：字体归属不可信却下了结论，得到 {code}")
        expect(any("归属" in w for w in (result.get("warnings") or [])),
               "用例7：没有告警点明 primaryFont 归属不可信")

        # ---- 用例 8：generic 兜底的替换是 medium 级，不是 silent ----
        code, result = run(tmp, {
            "elements": [text_element(1, "AvenirLT-Black, sans-serif", "Helvetica")]},
            meta(), "generic.json")
        expect(code == 1, f"用例8：generic 兜底的替换未被判为替换，得到 {code}")
        expect(result.get("severity") == "medium",
               f"用例8：generic 兜底应判 medium，得到 {result.get('severity')!r}")
        expect((result.get("affectedElements") or [{}])[0].get("mechanism") == "generic-fallback",
               "用例8：机制不是 generic-fallback")

        # ---- 用例 9：系统关键字（-apple-system / system-ui / ui-monospace）不构成替换证据 ----
        # 三个都要覆盖，且必须包含**带连字符**的那些：归一化会把 `system-ui` 变成
        # `system ui`，关键字表若不按归一化形式存放就匹配不上（只测 `BlinkMacSystemFont`
        # 是测不出来的 —— 它归一化后与自己完全一致，那条断言等于空写）。
        code, result = run(tmp, {
            "elements": [
                text_element(1, "-apple-system, BlinkMacSystemFont", "Helvetica Neue"),
                text_element(2, "system-ui", "Helvetica Neue"),
                text_element(3, "ui-monospace", "Menlo"),
            ]}, meta(), "system-keyword.json")
        expect(code == 0, f"用例9：系统关键字被误判成替换（exit {code}）")
        expect(len(result.get("ambiguousElements") or []) == 3,
               f"用例9：应有 3 个元素判为系统关键字待判，得到 "
               f"{[a['index'] for a in (result.get('ambiguousElements') or [])]}")
        expect(not (result.get("affectedElements") or []),
               "用例9：系统关键字元素不该进 affectedElements")
        expect(any("系统关键字" in w for w in (result.get("warnings") or [])),
               "用例9：没有告警说明系统关键字无法比对")

        # ---- 用例 10：真实 render 输出形状（style.fontFamily + primaryFont.familyName）----
        code, result = run(tmp, {
            "elements": [
                {"index": 6, "tag": "span", "ownsText": True, "ownText": "Choose Your Plan",
                 "style": {"fontFamily": "AvenirLT-Black"},
                 "primaryFont": {"familyName": "Times", "postScriptName": "Times-Roman",
                                "isCustomFont": False, "glyphCount": 16},
                 "fontsResolved": [{"familyName": "Times", "postScriptName": "Times-Roman",
                                    "glyphCount": 16}],
                 "textMetrics": {"advanceWidth": 173.609}},
                {"index": 3, "tag": "span", "ownsText": True, "ownText": "Alpha",
                 "style": {"fontFamily": "Avenir-Medium"},
                 "primaryFont": {"familyName": "Avenir Medium", "postScriptName": "Avenir-Medium",
                                 "isCustomFont": False, "glyphCount": 7},
                 "textMetrics": {"advanceWidth": 48.766}},
            ]}, meta(), "render-shape.json")
        expect(code == 1, f"用例10：真实 render 形状的替换未被查出，得到 {code}")
        expect([a["index"] for a in (result.get("affectedElements") or [])] == [6],
               "用例10：真实形状下受影响元素定位不对（Avenir-Medium 不该被报）")
        expect((result.get("affectedElements") or [{}])[0].get("advanceWidth") == 173.609,
               "用例10：affectedElements 未带上排版宽度这一证据")

        # ---- 用例 11：部分覆盖时要如实说明只覆盖了已测量的部分 ----
        code, result = run(tmp, {
            "elements": [
                text_element(1, "AvenirLT-Black", "Times"),
                {"index": 2, "tag": "span", "ownsText": True, "ownText": "x",
                 "fontFamily": "AvenirLT-Black"},                      # 没有运行时字体
            ]}, meta(), "partial.json")
        expect(code == 1, f"用例11：部分覆盖下的替换未被查出，得到 {code}")
        expect(result.get("coverage") == 0.5,
               f"用例11：coverage 不是 0.5，得到 {result.get('coverage')!r}")
        expect(any("只拿到声明" in w for w in (result.get("warnings") or [])),
               "用例11：没有告警说明结论只覆盖已测量的元素")

        # ---- 用例 12：评测素材本身就是一份真替换（工具层与评测层对同一份事实的判断一致）----
        if (FALLBACK / "page-facts.json").is_file():
            out = tmp / "fixture.json"
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--page-facts", str(FALLBACK / "page-facts.json"),
                 "--browser-meta", str(FALLBACK / "browser-meta.json"),
                 "--output", str(out), "--quiet"],
                capture_output=True, text=True)
            expect(proc.returncode == 1,
                   f"用例12：评测素材（真替换）未判 exit 1，得到 {proc.returncode}")
            fixture_result = json.loads(out.read_text())
            indexes = sorted(a["index"] for a in (fixture_result.get("affectedElements") or []))
            expect(indexes == [3, 7, 15],
                   f"用例12：受影响元素不是素材里那三个 [3,7,15]，得到 {indexes}")
            # 素材里的对照组（PingFang SC）不能被算成受影响
            expect(22 not in indexes, "用例12：对照组元素 22 被误报成受影响")
            expect(fixture_result.get("fixSide") == "baseline",
                   "用例12：fixSide 不是 baseline")
            for key in ("declaredFontFamily", "resolvedFontFamily", "substituted",
                        "affectedElements", "evidence", "fixSide"):
                expect(key in fixture_result,
                       f"用例12：产物缺少评测判分器要求的字段 {key}")
        else:
            problems.append("用例12：找不到 evals/fixtures/font-fallback 素材")

    for problem in problems:
        print(problem)
    if problems:
        print("字体链审计未满足契约")
        return 1
    print("字体链审计：真替换查出并落到元素、族名格式差异不误报、generic 与系统关键字分级正确、"
          "未测量/测量失败/归属漂移三类均判证据不足")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
