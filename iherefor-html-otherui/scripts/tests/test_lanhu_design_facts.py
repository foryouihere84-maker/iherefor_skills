#!/usr/bin/env python3
"""回归：设计事实解析必须还原真实 API 的字段嵌套结构，不得按理想化 schema 猜字段。

真实 `lanhu_get_design_document` 返回体有几个容易写错的坑，本用例专门盯住：

1. ``type`` 对文本/形状/组**全是 ``artboard``** —— 解析器不得用 ``type`` 判断文本层；
2. 文本在 ``style.typography``（不在 ``style.text``），且 ``color`` 是 ``{r,g,b,a,value}``；
3. ``metadata.parentId`` **实测全 null、不可靠** —— 父视图归属必须由 ``children`` 树推导；
4. ``typography.fontSize`` 是**除过 ``canvas.scale`` 的**（scale=2 稿里 fontSize=7 = 真实 14/2），
   解析器必须按 scale 还原，并保留 ``fontSizeRaw`` 供追溯；
5. 字体族名 ``AvenirLT-*``（带 LT 后缀，系统里不存在）要 normalize 成 ``Avenir-*``。

本用例用内联构造的最小返回体做对照，确保解析器在字段名、嵌套层级、scale 语义上都不偏离实际。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lanhu_design_facts.py"


def run_facts(document, output):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(document, fh, ensure_ascii=False)
        doc_path = fh.name
    argv = [sys.executable, str(SCRIPT), "--document", doc_path, "--output", str(output)]
    proc = subprocess.run(argv, capture_output=True, text=True)
    if not output.exists():
        raise SystemExit("解析器未产出：%s" % (proc.stderr or proc.stdout).strip()[:400])
    return json.loads(output.read_text())


def minimal_document():
    """构造一个能暴露「scale 语义 + parentId 空 + 字体族名」三个坑的最小返回体。

    canvas.scale=2、fontSize=7（真实应 14）、metadata.parentId 全 null、
    fontFamily=AvenirLT-Black（应 normalize 成 Avenir-Black）。
    """
    return {
        "name": "测试稿",
        "imageId": "img-1",
        "projectId": "proj-1",
        "canvas": {"width": 810, "height": 1080, "scale": 2, "device": "iOS @1x"},
        "layers": [
            {
                "id": "ROOT",
                "name": "root",
                "type": "artboard",
                "rect": {"x": 0, "y": 0, "width": 810, "height": 1080},
                "style": {
                    "fills": [], "borders": [], "shadows": [],
                    "opacity": 100, "blendMode": "normal",
                    "visible": True, "locked": False, "rotation": 0,
                },
                "children": [
                    {
                        "id": "TITLE",
                        "name": "title",
                        "type": "artboard",
                        "rect": {"x": 10, "y": 10, "width": 100, "height": 40},
                        "style": {
                            "fills": [],
                            "borders": [
                                {"color": {"r": 0, "g": 0, "b": 0, "a": 1, "value": "rgba(0,0,0,1)"},
                                 "width": 0.5, "style": "solid", "radius": 0},
                            ],
                            "shadows": [],
                            "opacity": 100, "blendMode": "normal",
                            "visible": True, "locked": False, "rotation": 0,
                            "typography": {
                                "fontFamily": "AvenirLT-Black", "fontSize": 7,
                                "fontWeight": 400, "lineHeight": 12,
                                "letterSpacing": 0, "textAlign": "left",
                                "color": {"r": 26, "g": 26, "b": 26, "a": 1, "value": "#1A1A1A"},
                                "text": "Hello",
                            },
                        },
                        "children": [],
                        "metadata": {"depth": 1, "parentId": None,
                                     "hasExportImage": False, "exportFormats": []},
                    },
                ],
                "metadata": {"depth": 0, "parentId": None,
                             "hasExportImage": False, "exportFormats": []},
            },
        ],
    }


def test_typography_is_not_type():
    """type 是 artboard，但文本仍须从 style.typography 取出。"""
    out = Path(tempfile.mkdtemp()) / "facts.json"
    facts = run_facts(minimal_document(), out)
    assert facts["summary"]["typographyCount"] == 1, facts["summary"]
    row = facts["typography"][0]
    assert row["text"] == "Hello"
    assert row["color"] == "#1A1A1A"
    # 含 typography 的那个节点，其 type 也必须是 artboard（契约里可断言）
    assert facts["hierarchy"][1]["id"] == "TITLE"


def test_font_size_restored_by_scale():
    """坑 4：fontSize 是除过 canvas.scale 的，必须还原，并保留 fontSizeRaw。"""
    out = Path(tempfile.mkdtemp()) / "facts.json"
    facts = run_facts(minimal_document(), out)
    row = facts["typography"][0]
    assert row["fontSizeRaw"] == 7          # document 原文
    assert row["fontSize"] == 14.0          # 7 * scale(2)
    assert facts["scale"]["canvasScale"] == 2.0
    assert facts["scale"]["fontSizeScaled"] is True


def test_font_family_normalized():
    """坑 5：AvenirLT-Black 应 normalize 成 Avenir-Black（保留 fontFamilyRaw 追溯）。"""
    out = Path(tempfile.mkdtemp()) / "facts.json"
    facts = run_facts(minimal_document(), out)
    row = facts["typography"][0]
    assert row["fontFamily"] == "Avenir-Black"
    assert row["fontFamilyRaw"] == "AvenirLT-Black"


def test_parent_derived_from_children_not_metadata():
    """坑 3：metadata.parentId 全 null 时，父视图归属仍须由 children 树推导出来。"""
    out = Path(tempfile.mkdtemp()) / "facts.json"
    facts = run_facts(minimal_document(), out)
    by_id = {h["id"]: h for h in facts["hierarchy"]}
    assert by_id["ROOT"]["depth"] == 0
    assert by_id["ROOT"]["parentId"] is None      # 根层无父
    assert by_id["TITLE"]["depth"] == 1
    assert by_id["TITLE"]["parentId"] == "ROOT"   # 由 children 推导，而非 metadata


def test_scale_absent_no_restore():
    """canvas.scale 缺失或无效时，fontSize 原样返回、不做还原。"""
    doc = minimal_document()
    doc["canvas"].pop("scale")
    out = Path(tempfile.mkdtemp()) / "facts.json"
    facts = run_facts(doc, out)
    row = facts["typography"][0]
    assert row["fontSize"] == row["fontSizeRaw"] == 7
    assert facts["scale"]["fontSizeScaled"] is False


def test_borders_extracted():
    """描边层进入 borders，且宽度可读。"""
    out = Path(tempfile.mkdtemp()) / "facts.json"
    facts = run_facts(minimal_document(), out)
    assert facts["summary"]["borderCount"] == 1
    assert facts["borders"][0]["name"] == "title"
    assert facts["borders"][0]["borders"][0]["width"] == 0.5


def test_summary_counts():
    """summary 的统计与结构一致：图层数、根层数、不可见层、导出图。"""
    out = Path(tempfile.mkdtemp()) / "facts.json"
    facts = run_facts(minimal_document(), out)
    s = facts["summary"]
    assert s["layerCount"] == 2
    assert s["rootCount"] == 1
    assert s["visibleFalseCount"] == 0
    assert facts["roots"][0]["id"] == "ROOT"


def test_rgba_fallback_hexless_color():
    """color 缺 value 时，应能由 r/g/b/a 拼出 rgba 字符串。"""
    doc = minimal_document()
    c = doc["layers"][0]["children"][0]["style"]["typography"]["color"]
    c.pop("value")
    c["r"], c["g"], c["b"], c["a"] = 255, 0, 128, 0.5
    out = Path(tempfile.mkdtemp()) / "facts.json"
    facts = run_facts(doc, out)
    assert facts["typography"][0]["color"] == "rgba(255,0,128,0.5)"


def test_font_size_degraded_signal():
    """多个文本都由同一字号、且各不相同时，必须标 fontSizeDegraded=true（字号层级丢失）。"""
    doc = minimal_document()
    # 在 ROOT 下再加一个子文本，与 TITLE 字号不同，模拟「字号层级被坍缩」
    second = dict(doc["layers"][0]["children"][0])
    second["id"] = "TITLE2"
    second["name"] = "title2"
    second["style"] = dict(second["style"])
    second["style"]["typography"] = dict(second["style"]["typography"])
    second["style"]["typography"]["text"] = "World"
    second["style"]["typography"]["fontSize"] = 7  # 与第一个相同 → 坍缩
    second["metadata"] = {"depth": 1, "parentId": None, "hasExportImage": False, "exportFormats": []}
    doc["layers"][0]["children"].append(second)
    out = Path(tempfile.mkdtemp()) / "facts.json"
    facts = run_facts(doc, out)
    # 两个文本、字号相同 → 坍缩信号为 True
    assert facts["summary"]["typographyCount"] == 2
    assert facts["degraded"]["fontSizeDegraded"] is True
    # 改了字号后（两个字号不同）→ 信号为 False
    doc["layers"][0]["children"][1]["style"]["typography"]["fontSize"] = 9
    out2 = Path(tempfile.mkdtemp()) / "facts.json"
    facts2 = run_facts(doc, out2)
    assert facts2["degraded"]["fontSizeDegraded"] is False


def test_gradient_degraded_signal():
    """gradient fill 的 stops 为空时，必须标 gradientDegraded=true（渐变信息丢失）。"""
    doc = minimal_document()
    fill = {"type": "gradient", "gradient": {"type": "linear", "stops": []}}
    doc["layers"][0]["children"][0]["style"]["fills"] = [fill]
    out = Path(tempfile.mkdtemp()) / "facts.json"
    facts = run_facts(doc, out)
    assert facts["degraded"]["gradientDegraded"] is True
    # stops 有内容 → 不判失真
    fill["gradient"]["stops"] = [{"color": "#000"}]
    out2 = Path(tempfile.mkdtemp()) / "facts.json"
    facts2 = run_facts(doc, out2)
    assert facts2["degraded"]["gradientDegraded"] is False


if __name__ == "__main__":
    test_typography_is_not_type()
    test_font_size_restored_by_scale()
    test_font_family_normalized()
    test_parent_derived_from_children_not_metadata()
    test_scale_absent_no_restore()
    test_borders_extracted()
    test_summary_counts()
    test_rgba_fallback_hexless_color()
    test_font_size_degraded_signal()
    test_gradient_degraded_signal()
    print("lanhu_design_facts 解析还原：全部通过")
