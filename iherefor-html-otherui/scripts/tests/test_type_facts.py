#!/usr/bin/env python3
"""回归：样式恒量（typeFacts）必须带 page-facts 元素溯源。

这是「权威来自 DOM」的可执行判据。以前的漏洞是：布局门只盯几何关系
（``kind`` / ``of`` / ``basis``），字号/字体/颜色/描边这些值落在 Agent 写码的
字面量上，四道门全放行 —— 于是「不读 DOM、拍脑袋编个 fontSize=14」也能交差。

``check_layout_proportions.py`` 的 ``--plan-only`` 现在会把顶层 ``typeFacts``
与 ``page-facts.json`` 交叉核对。这个测试用**变异探针**：先把合规计划判为通过，
再逐项改坏（删 typeFacts / kindSource 写成 agent-decided / elementIndex 越界 /
拿空容器顶文本），要求每一项都被判违规。没有这些「必须挂」的断言，测试只是
「脚本跑得动」，不是「脚本认得偷懒」。

纪律（见项目 memory）：
1. 只要读落盘产物，run 前先删旧输出，断言 stderr 无 ``Traceback``。
2. fixture 不造物理上不存在的几何。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = ROOT / "scripts" / "check_layout_proportions.py"


def _run(tmp, plan_path, facts_path=None, output_name="check.json"):
    out = tmp / output_name
    if out.exists():
        out.unlink()  # 纪律 1：先删旧输出，防读到上一轮残留结论
    args = [str(CHECK_SCRIPT), "--plan", str(plan_path), "--plan-only"]
    if facts_path is not None:
        args += ["--page-facts", str(facts_path)]
    args += ["--output", str(out), "--quiet"]
    proc = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if "Traceback" in proc.stderr:
        raise AssertionError(f"脚本崩栈：\n{proc.stderr}")
    data = json.loads(out.read_text()) if out.is_file() else None
    return proc, data


def _write(tmp, name, payload):
    path = tmp / name
    path.write_text(json.dumps(payload, ensure_ascii=False))
    return path


def _kinds(data):
    return {v.get("kind") for v in (data or {}).get("violations", [])}


def _facts_payload():
    # 元素 3 是文本元素、元素 5 是带描边元素 —— 与 typeFacts 的声明对齐。
    return {
        "elements": [
            {"index": 0, "tag": "div", "ownsText": False,
             "border": {"widthPx": 0}, "style": {}},
            {"index": 3, "tag": "span", "ownsText": True,
             "border": {"widthPx": 0}, "style": {"fontSize": "24px"}},
            {"index": 5, "tag": "div", "ownsText": False,
             "border": {"widthPx": 0.5}, "style": {"borderRadius": "22px"}},
        ]
    }


def _plan_payload(type_facts):
    plan = {
        "layoutProportions": {
            "regions": [
                {"region": "主标题",
                 "relations": [{"id": "t.x", "kind": "pinned", "edge": "leading", "inset": 16},
                                {"id": "t.y", "kind": "pinned", "edge": "top", "inset": 24}]},
            ]
        }
    }
    if type_facts is not None:
        plan["typeFacts"] = type_facts
    return plan


def _ok_type_facts():
    return [
        {"region": "主标题", "elementIndex": 3, "fontSize": 24,
         "fontFamily": "Avenir Black", "color": "#1A1A1A",
         "borderWidth": 0, "borderColor": None, "borderRadius": 0,
         "kindSource": "page-facts"},
    ]


def main():
    n_fail = 0
    checks = []

    def check(name, cond):
        nonlocal n_fail
        checks.append((name, cond))
        if not cond:
            n_fail += 1
            print(f"FAIL  {name}")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        facts = _write(tmp, "facts.json", _facts_payload())

        # 1. 合规：文字区域 + 合法 typeFacts，必须 pass。
        plan = _write(tmp, "plan_ok.json", _plan_payload(_ok_type_facts()))
        _, data = _run(tmp, plan, facts)
        check("合规 typeFacts 判通过", data and data.get("status") == "pass" and not data.get("violations"))

        # 2. 违规：文字区域但 typeFacts 整体缺失 → fact-source-missing。
        plan = _write(tmp, "plan_missing.json", _plan_payload(None))
        _, data = _run(tmp, plan, facts)
        check("缺 typeFacts 判 fact-source-missing",
              "fact-source-missing" in _kinds(data))

        # 3. 违规：kindSource 写成 agent-decided → fact-not-from-authority。
        bad = _ok_type_facts()
        bad[0]["kindSource"] = "agent-decided"
        plan = _write(tmp, "plan_kindsrc.json", _plan_payload(bad))
        _, data = _run(tmp, plan, facts)
        check("kindSource 非法判 fact-not-from-authority",
              "fact-not-from-authority" in _kinds(data))

        # 4. 违规：elementIndex 越界 → fact-element-index-out-of-range。
        bad = _ok_type_facts()
        bad[0]["elementIndex"] = 99
        plan = _write(tmp, "plan_range.json", _plan_payload(bad))
        _, data = _run(tmp, plan, facts)
        check("elementIndex 越界判 out-of-range",
              "fact-element-index-out-of-range" in _kinds(data))

        # 5. 违规：声明 fontSize 但 elementIndex 指向非文本元素 → fact-text-on-non-text-element。
        bad = _ok_type_facts()
        bad[0]["elementIndex"] = 0  # 元素 0 无 ownText
        plan = _write(tmp, "plan_textonbox.json", _plan_payload(bad))
        _, data = _run(tmp, plan, facts)
        check("文字声明落在非文本元素判 fact-text-on-non-text-element",
              "fact-text-on-non-text-element" in _kinds(data))

    print(f"\ntypeFacts 溯源校验：{'全部通过' if n_fail == 0 else f'{n_fail} 项失败'}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
