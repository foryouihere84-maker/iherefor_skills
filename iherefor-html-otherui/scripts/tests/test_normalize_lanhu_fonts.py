#!/usr/bin/env python3
"""回归：字体族名 normalize 必须只替换确定的坏族名，不碰表外的族名。

真实坑：Lanhu 导出的 ``AvenirLT-Medium``/``AvenirLT-Black`` 带 LT 后缀、系统不存在，
Chromium 静默回落到 Times；``Avenir-*`` 才是系统真实族名。脚本只替换表里明确列出的
映射，表外的族名（如 ``PingFangSC-Semibold``）原样保留，留给 audit_fonts.py 审计。
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "normalize_lanhu_fonts.py"

SAMPLE_CSS = """\
body { font-family: "PingFang SC", sans-serif; }
.text_3 { font-family: AvenirLT-Medium; font-size: 14px; }
.text_4 { font-family: AvenirLT-Black; font-size: 24px; }
.text_5 { font-family: PingFangSC-Semibold; font-size: 18px; }
"""


def run_normalize(source_dir):
    argv = [sys.executable, str(SCRIPT), "--source", str(source_dir)]
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit("normalize 失败：%s" % (proc.stderr or proc.stdout).strip()[:400])


def test_replaces_known_bad_families():
    """AvenirLT-* 必须替换成 Avenir-*（去掉 LT 后缀）。"""
    d = Path(tempfile.mkdtemp())
    (d / "index.css").write_text(SAMPLE_CSS, encoding="utf-8")
    (d / "common.css").write_text("dummy", encoding="utf-8")
    run_normalize(d)
    css = (d / "index.css").read_text(encoding="utf-8")
    assert "AvenirLT-Medium" not in css
    assert "AvenirLT-Black" not in css
    assert "Avenir-Medium" in css
    assert "Avenir-Black" in css
    # 表外的族名原样保留
    assert "PingFangSC-Semibold" in css
    assert '"PingFang SC"' in css


def test_unknown_families_untouched():
    """表外族名不得被误替换。"""
    d = Path(tempfile.mkdtemp())
    css = "a { font-family: SomeUnrelatedFont; }"
    (d / "index.css").write_text(css, encoding="utf-8")
    (d / "common.css").write_text("x", encoding="utf-8")
    run_normalize(d)
    assert (d / "index.css").read_text(encoding="utf-8") == css


def test_idempotent():
    """已替换过的文件再跑一次不应再产生替换。"""
    d = Path(tempfile.mkdtemp())
    css = "a { font-family: Avenir-Medium; }"  # 已经是好族名
    (d / "index.css").write_text(css, encoding="utf-8")
    (d / "common.css").write_text("x", encoding="utf-8")
    run_normalize(d)
    assert (d / "index.css").read_text(encoding="utf-8") == css


if __name__ == "__main__":
    test_replaces_known_bad_families()
    test_unknown_families_untouched()
    test_idempotent()
    print("normalize_lanhu_fonts 字体族名替换：全部通过")
