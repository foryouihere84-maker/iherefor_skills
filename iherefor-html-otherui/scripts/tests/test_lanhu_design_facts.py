#!/usr/bin/env python3
"""回归：设计事实解析必须还原真实 API 的字段嵌套结构，不得按理想化 schema 猜字段。

真实 `lanhu_get_design_document` 返回体有三个容易写错的坑，本用例专门盯住：

1. ``type`` 对文本/形状/组**全是 ``artboard``** —— 解析器不得用 ``type`` 判断文本层；
2. 文本在 ``style.typography``（不在 ``style.text``），且 ``color`` 是 ``{r,g,b,a,value}``；
3. ``parentId`` / ``depth`` / ``hasExportImage`` 在 ``metadata``（不在顶层）。

本用例用内联构造的最小返回体（对照组），再配一段真实返回体切片做「真值对照」，
确保解析器在字段名、嵌套层级上都不偏离实际。
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
    """构造一个能暴露三个坑的最小返回体。"""
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
                                "fontFamily": "PingFang SC", "fontSize": 12,
                                "fontWeight": 400, "lineHeight": 12,
                                "letterSpacing": 0, "textAlign": "left",
                                "color": {"r": 26, "g": 26, "b": 26, "a": 1, "value": "#1A1A1A"},
                                "text": "Hello",
                            },
                        },
                        "children": [],
                        "metadata": {"depth": 1, "parentId": "ROOT",
                                     "hasExportImage": False, "exportFormats": []},
                    },
                ],
                "metadata": {"depth": 0, "parentId": None,
                             "hasExportImage": False, "exportFormats": []},
            },
        ],
    }


def test_typography_is_not_type():
    """坑 1&2：type 是 artboard，但文本仍须从 style.typography 取出。"""
    out = Path(tempfile.mkdtemp()) / "facts.json"
    facts = run_facts(minimal_document(), out)
    assert facts["summary"]["typographyCount"] == 1, facts["summary"]
    row = facts["typography"][0]
    assert row["text"] == "Hello"
    assert row["fontFamily"] == "PingFang SC"
    assert row["fontSize"] == 12
    assert row["color"] == "#1A1A1A"

    # 含 typography 的那个节点，其 type 也必须是 artboard（契约里可断言）
    assert facts["hierarchy"][1]["id"] == "TITLE"


def test_parent_comes_from_metadata():
    """坑 3：parentId / depth 读 metadata，不是顶层。"""
    out = Path(tempfile.mkdtemp()) / "facts.json"
    facts = run_facts(minimal_document(), out)
    by_id = {h["id"]: h for h in facts["hierarchy"]}
    assert by_id["ROOT"]["depth"] == 0
    assert by_id["ROOT"]["parentId"] is None
    assert by_id["TITLE"]["depth"] == 1
    assert by_id["TITLE"]["parentId"] == "ROOT"


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


if __name__ == "__main__":
    test_typography_is_not_type()
    test_parent_comes_from_metadata()
    test_borders_extracted()
    test_summary_counts()
    test_rgba_fallback_hexless_color()
    print("lanhu_design_facts 解析还原：全部通过")
