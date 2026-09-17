#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan-artifacts.py — iherefor-smart-development 闭环校验器

扫描目标工程的 docs/<feature>/ 目录，依据 task-breakdown.md 的「阶段 → 任务 → 产出物
路径 + 必填章节」做结构核验（cur 式：存在性 + 章节完整性），输出 HTML 可视化报告。

用法:
    python3 scan-artifacts.py <目标工程根目录> [--feature <feature名>] [--tier <full|lite>] [--out <html路径>]

说明:
    - 不传 --feature 时，自动探测 docs/ 下第一个子目录作为 feature 名。
    - 不传 --tier 时按 full 档；--tier lite 时按 config/tier.json 跳过 lite 档可省略产物。
    - 每个任务产物对应一个模板；必填章节关键词标注在 DEF 常量里。
    - 产出物落在各工程目录（测试代码/源码）的任务标「不判定」，由阶段 5.1 编译门兜底。
    - 本脚本只做「机器可判定」校验，不替代人工闸门（a/b/c/d/交付门）。
"""

import os
import sys
import json
import datetime

# ---------------------------------------------------------------------------
# 校验基准：与 references/task-breakdown.md + templates/*.md 一一对应
# 每个任务：(任务号, 任务名, 产出物相对路径 或 None=不判定, [必填章节关键词])
# 产出物路径相对于 docs/<feature>/ 目录。
#
# 语义显式约定（修复早期 None/空列表混用导致的意图不清）：
#   - NOT_APPLICABLE = 产物落在各工程目录（测试/源码），校验器不判定，由编译门兜底。
#   - EXISTENCE_ONLY = 产物无常驻章节，仅做存在性核验。
# 二者区分开，避免维护时误改。
# ---------------------------------------------------------------------------
NOT_APPLICABLE = None   # 不判定（产物在工程目录）
EXISTENCE_ONLY = []     # 仅存在性核验（无章节锚点）
DEF = {
    1: {
        "name": "需求理清（Spec）", "gate": "🔒 闸门 a",
        "tasks": [
            ("1.1", "定功能短名", "00-入口/文档导航.md", ["使用规则", "主线产物读取顺序"]),
            ("1.2", "厘清需求边界", "01-需求/requirements.md", ["业务目标", "边界", "非目标"]),
            ("1.3", "固化领域模型", "01-需求/domain-model.md", ["术语表", "实体", "不变量"]),
            ("1.4", "出用户故事", "01-需求/user-stories.md", ["用户故事", "验收场景"]),
            ("1.5", "定共享需求", "01-需求/shared-requirements.md", ["共享范围"]),
        ],
    },
    2: {
        "name": "架构设计（Plan）", "gate": "🔒 闸门 b（最重）",
        "tasks": [
            ("2.1", "定事实边界", "02-架构/search-questions.md", ["问题清单"]),
            ("2.2", "搜索事实", "02-架构/facts.md", ["结论", "来源"]),
            ("2.3", "抽设计约束", "02-架构/constraints.md", ["硬约束"]),
            ("2.4", "并行出多案", "02-架构/design-options.md", ["方案"]),
            ("2.5", "方案对比", "02-架构/comparison.md", ["对比维度", "推荐"]),
            ("2.6", "定共享层", "02-架构/shared-layer.md", ["领域模型", "数据契约", "不变量清单"]),
            ("2.7", "出方案草案", "02-架构/proposal-draft.md", ["变更概述"]),
        ],
    },
    3: {
        "name": "工程落地计划（Plan 变更清单 → Tasks）", "gate": "🔒 闸门 c1（变更清单）+ c2（tickets）",
        "tasks": [
            ("3.1", "审现有架构", "03-落地计划/architecture-audit.md", ["摩擦点", "风险"]),
            ("3.2", "定变更清单", "03-落地计划/change-list.md", ["文件变更", "依赖"]),
            ("3.3", "定回滚方式", "03-落地计划/rollback.md", ["回滚路径"]),
            ("3.4", "拆任务 tickets", "03-落地计划/tickets.md", ["Tickets"]),
        ],
    },
    4: {
        "name": "TDD 落地（Implementation）", "gate": "🔒 闸门 d",
        "tasks": [
            ("4.1", "选测试栈+seam", "04-实现与测试/test-plan.md", ["测试栈", "seam", "should"]),
            ("4.2", "red 写失败测试", NOT_APPLICABLE, EXISTENCE_ONLY),   # 产物在工程 test/ 目录
            ("4.3", "green 最小实现", NOT_APPLICABLE, EXISTENCE_ONLY),   # 产物在工程 src/ 目录
            ("4.4", "落地层分叉", NOT_APPLICABLE, EXISTENCE_ONLY),      # 产物在工程 src/ 目录
        ],
    },
    5: {
        "name": "编译·测试·审查·交付（Implementation）", "gate": "🔒 交付门",
        "tasks": [
            ("5.1", "双端编译", "05-交付/build-report.md", ["iOS 编译", "Android 编译"]),
            ("5.2", "双轴审查", "05-交付/review-report.md", ["审查结论", "降级说明"]),
            ("5.3", "代码↔文档对账", "05-交付/一致性对账.md", ["同步点", "漂移项"]),
            ("5.4", "出交付报告", "05-交付/delivery-report.md", ["交付清单", "回滚状态"]),
        ],
    },
    6: {
        "name": "反馈闭环", "gate": "（回跳，log 增量）",
        # 阶段 6 是过程动作，只核验 run-log.jsonl 存在性
        "tasks": [
            ("6.1", "定位失败归属", "99-来源与日志/run-log.jsonl", EXISTENCE_ONLY),
            ("6.2", "回跳重跑", "99-来源与日志/run-log.jsonl", EXISTENCE_ONLY),
        ],
    },
}

STATUS_LABEL = {"ok": "已产出", "weak": "缺字段", "missing": "缺失", "skipped": "不判定/已跳过"}
STATUS_COLOR = {"ok": "#1a7f37", "weak": "#b08800", "missing": "#cf222e", "skipped": "#6e7781"}


def find_feature(root):
    docs = os.path.join(root, "docs")
    if not os.path.isdir(docs):
        return None
    subs = sorted(d for d in os.listdir(docs)
                  if os.path.isdir(os.path.join(docs, d)) and not d.startswith("."))
    return subs[0] if subs else None


def load_tier(tier):
    """读取 tier.json，返回该档位可跳过产物集合。失败或未知档位 → 空集合（等价 full）。"""
    if not tier or tier == "full":
        return set()
    here = os.path.dirname(os.path.abspath(__file__))
    tier_path = os.path.join(here, "..", "config", "tier.json")
    try:
        with open(tier_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("tiers", {}).get(tier, {}).get("skip_artifacts", []))
    except (OSError, ValueError):
        return set()


def check_artifact(base_dir, artifact_path, keywords):
    """返回 (status, detail)。artifact_path 为 NOT_APPLICABLE → skipped(不判定)。"""
    if artifact_path is NOT_APPLICABLE:
        return "skipped", "产物在工程目录，由阶段 5.1 编译门兜底"


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:  # noqa: BLE001
        return None


def check_artifact(base_dir, artifact_path, keywords):
    """返回 (status, detail)。artifact_path 为 NOT_APPLICABLE → skipped(不判定)。"""
    if artifact_path is NOT_APPLICABLE:
        return "skipped", "产物在工程目录，由阶段 5.1 编译门兜底"
    full = os.path.join(base_dir, artifact_path)
    if not os.path.exists(full):
        return "missing", "缺失"
    if not os.path.isfile(full):
        return "missing", "路径存在但非文件"
    if os.path.getsize(full) == 0:
        return "weak", "文件为空"
    text = read_text(full)
    if text is None:
        return "weak", "读取失败"
    if keywords is EXISTENCE_ONLY:
        return "ok", "存在（无章节核验锚点）"
    missing = [k for k in keywords if k not in text]
    if not missing:
        return "ok", f"章节齐全（{len(keywords)}/{len(keywords)}）"
    return "weak", f"缺章节：{'、'.join(missing)}"


def scan(root, feature, skip_artifacts=None):
    base = os.path.join(root, "docs", feature) if feature else None
    skip = skip_artifacts or set()
    results = []
    totals = {"ok": 0, "weak": 0, "missing": 0, "skipped": 0}
    for stage_no in sorted(DEF):
        st = DEF[stage_no]
        entries = []
        for task_id, task_name, artifact, keywords in st["tasks"]:
            if artifact is not NOT_APPLICABLE and artifact in skip:
                # lite 档明确跳过：不判缺失，标 skipped（已按档位省略）
                status, detail = "skipped", "lite 档可跳过"
                totals[status] += 1
            elif base is None and artifact is not NOT_APPLICABLE:
                status, detail = "missing", "feature 目录不存在"
                totals[status] += 1
            else:
                status, detail = check_artifact(base, artifact, keywords)
                totals[status] += 1
            entries.append({
                "task_id": task_id, "task_name": task_name,
                "artifact": artifact or "(工程目录)", "status": status, "detail": detail,
            })
        results.append({
            "stage": stage_no, "name": st["name"], "gate": st["gate"], "entries": entries,
        })
    return results, totals, base


def render_html(results, totals, feature, root, base, tier="full"):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cards = []
    for r in results:
        rows = []
        for e in r["entries"]:
            rows.append(
                "<tr>"
                f"<td class='tid'>{e['task_id']}</td>"
                f"<td>{e['task_name']}</td>"
                f"<td class='mono'>{e['artifact']}</td>"
                f"<td><span class='pill' style='background:{STATUS_COLOR[e['status']]}'>"
                f"{STATUS_LABEL[e['status']]}</span></td>"
                f"<td class='dim'>{e['detail']}</td>"
                "</tr>"
            )
        cards.append(
            "<div class='stage'>"
            f"<div class='stage-head'><span class='stage-title'>阶段 {r['stage']} · {r['name']}</span>"
            f"<span class='gate'>{r['gate']}</span></div>"
            "<table><thead><tr><th>任务</th><th>做什么</th><th>产出物</th><th>状态</th><th>说明</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        )
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>闭环校验报告 · {feature}</title>
<style>
:root{{--bg:#f6f8fa;--card:#fff;--line:#d0d7de;--text:#1f2328;--dim:#59636e;}}
*{{box-sizing:border-box}}body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;background:var(--bg);color:var(--text);line-height:1.55}}
.wrap{{max-width:1080px;margin:0 auto;padding:24px}}h1{{font-size:22px;margin:0 0 4px}}
.sub{{color:var(--dim);font-size:13px;margin-bottom:20px}}
.summary{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}}
.chip{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 18px}}
.chip b{{display:block;font-size:24px}}.chip span{{color:var(--dim);font-size:12px}}
.stage{{background:var(--card);border:1px solid var(--line);border-radius:10px;margin-bottom:18px;overflow:hidden}}
.stage-head{{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid var(--line);background:#fafbfc}}
.stage-title{{font-weight:600;font-size:15px}}.gate{{font-size:12px;color:var(--dim);background:#eaeef2;padding:2px 8px;border-radius:20px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line)}}
th{{background:#f3f5f7;color:var(--dim);font-weight:600;white-space:nowrap}}tr:last-child td{{border-bottom:none}}
.tid{{color:var(--dim);font-family:ui-monospace,monospace;white-space:nowrap}}.mono{{font-family:ui-monospace,monospace;font-size:12px}}
.pill{{display:inline-block;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px}}.dim{{color:var(--dim)}}
.foot{{color:var(--dim);font-size:12px;margin-top:24px;border-top:1px solid var(--line);padding-top:12px}}
</style></head><body><div class="wrap">
<h1>闭环校验报告</h1>
<div class="sub">feature：<b>{feature}</b> · 档位：{tier} · 扫描根：{root} · 生成时间：{now}</div>
<div class="summary">
<div class="chip"><b style="color:{ok_color}">{ok}</b><span>已产出</span></div>
<div class="chip"><b style="color:{weak_color}">{weak}</b><span>缺字段</span></div>
<div class="chip"><b style="color:{missing_color}">{missing}</b><span>缺失</span></div>
<div class="chip"><b style="color:{skip_color}">{skipped}</b><span>不判定</span></div>
</div>
{cards}
<div class="foot">本报告由 scan-artifacts.py 生成，按 templates/ 必填章节做结构核验，不替代人工闸门（a/b/c/d/交付门）。基准见 skill/references/task-breakdown.md。</div>
</div></body></html>
""".format(
        feature=feature or "(未识别)", root=root, now=now, tier=tier,
        ok=totals["ok"], weak=totals["weak"], missing=totals["missing"], skipped=totals["skipped"],
        ok_color=STATUS_COLOR["ok"], weak_color=STATUS_COLOR["weak"],
        missing_color=STATUS_COLOR["missing"], skip_color=STATUS_COLOR["skipped"],
        cards="".join(cards),
    )


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        sys.exit(1)
    root = os.path.abspath(argv[0])
    if not os.path.isdir(root):
        print(f"错误：目标工程根目录不存在：{root}")
        sys.exit(2)
    feature = None
    out_path = None
    tier = "full"
    i = 1
    while i < len(argv):
        if argv[i] == "--feature" and i + 1 < len(argv):
            feature = argv[i + 1]; i += 2
        elif argv[i] == "--tier" and i + 1 < len(argv):
            tier = argv[i + 1]; i += 2
        elif argv[i] == "--out" and i + 1 < len(argv):
            out_path = argv[i + 1]; i += 2
        else:
            i += 1
    feature = feature or find_feature(root)
    skip_artifacts = load_tier(tier)
    if feature is None:
        print("警告：未识别 feature（docs/ 下无子目录），仅能报告「全部缺失」。")
        print("提示：先用 --feature 指定，或让任务 1.1 初始化 docs/<feature>/。")
    results, totals, base = scan(root, feature, skip_artifacts)
    out = out_path or os.path.join(root, "artifact-scan-report.html")
    html = render_html(results, totals, feature, root, base, tier)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"feature: {feature or '(未识别)'} · tier: {tier}")
    print(f"结果: 已产出 {totals['ok']} · 缺字段 {totals['weak']} · 缺失 {totals['missing']} · 不判定/已跳过 {totals['skipped']}")
    print(f"报告已生成: {out}")


if __name__ == "__main__":
    main()
