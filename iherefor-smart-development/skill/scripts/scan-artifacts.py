#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan-artifacts.py — iherefor-smart-development 闭环校验器（批次感知）

扫描目标工程的 docs/<feature>/ 目录，依据 references/任务拆解.md 的「阶段 → 任务 → 产出物
路径 + 必填章节」做结构核验（存在性 + 章节完整性），输出 HTML 可视化报告。

用法:
    python3 scan-artifacts.py <目标工程根目录> [--feature <feature名>] [--tier <full|lite>]
                              [--batch <批次名>] [--out <html路径>]

说明:
    - 不传 --feature 时，自动探测 docs/ 下第一个子目录作为 feature 名。
    - 不传 --batch 时核验**全部批次**；传了则只核验指定批次。
    - 不传 --tier 时按 full 档；--tier lite 时按 config/tier.json 跳过 lite 档可省略产物。

两级结构:
    文档按「批次层 + 产物层」两级组织（见 templates/模板说明.md 第 1 节）：
      · 批次层  = 目录 `<NN-需求名>`（如 `01-阅读进度续读`），一次需求迭代一个批次。
                  出现在 01-需求 / 02-原型 / 04-落地计划 / 05-实现与测试 / 06-交付 五个阶段下，
                  **必须同名对齐**。DEF 里用 `<批次>` 占位符表示这一层。
      · 产物层  = 批次内的文件，分追加型（多实例，路径含 `*`）与收敛型（单实例，无 `*`）。
      · 全局单例 = `00-入口/`、`03-架构/`、`99-来源与日志/`，不带批次层，只核验一次。

核验规则:
    第 0 层 批次结构 —— 批次发现 + 各阶段批次名对齐 + 批次序号连续。
    第 1 层 收敛型   —— 存在性 + 必填章节命中。
    第 2 层 追加型   —— 至少匹配一个文件 + 每个都过章节核验 + 批次内序号从 00 连续。
    产物落在各工程目录（测试代码/源码）的任务标「不判定」，由阶段 6.1 编译门兜底。
    本脚本只做「机器可判定」校验，不替代人工闸门（a/p/b/c1/c2/d/交付门）。
"""

import os
import re
import sys
import glob
import json
import fnmatch
import datetime

# ---------------------------------------------------------------------------
# 校验基准：与 references/任务拆解.md + templates/*.md 一一对应
# 每个任务：(任务号, 任务名, 产出物相对路径 或 None=不判定, [必填章节关键词])
# 产出物路径相对于 docs/<feature>/ 目录；含 `<批次>` 表示批次内产物，含 `*` 表示追加型多实例。
#
# 语义显式约定（区分「不判定」与「仅存在性」，避免维护时误改）：
#   - 不判定（NOT_APPLICABLE）：产物落在各工程目录（测试/源码），校验器不判定，由编译门兜底。
#   - 仅存在性（EXISTENCE_ONLY）：产物无常驻章节，仅做存在性核验。
# ---------------------------------------------------------------------------
NOT_APPLICABLE = None   # 不判定（产物在工程目录）
EXISTENCE_ONLY = []     # 仅存在性核验（无章节锚点）

BATCH_TOKEN = "<批次>"

# `03-架构/` 全部 7 份产物共有的锚点：架构层＝项目总体架构约束层，
# 别处改动须同步增量更新并留台账（文件夹级纪律，故用常量而非逐处硬写）
ARCH_LEDGER = "增量更新记录"                    # 批次层占位符
BATCH_STAGES = ["01-需求", "02-原型", "04-落地计划",
                "05-实现与测试", "06-交付"]   # 带批次层的阶段目录

DEF = {
    1: {
        "name": "需求理清（Spec）", "gate": "🔒 闸门 a",
        "tasks": [
            ("1.1", "定功能短名与批次", "00-入口/文档导航.md", ["使用规则", "批次清单", "主线读取顺序"]),
            ("1.2", "厘清需求边界", "01-需求/" + BATCH_TOKEN + "/需求-*.md", ["业务目标", "边界", "非目标"]),
            ("1.3", "固化领域模型", "01-需求/" + BATCH_TOKEN + "/领域模型.md",
             ["术语表", "实体", "不变量", "枚举与取值域"]),
            ("1.4", "出用户故事", "01-需求/" + BATCH_TOKEN + "/用户故事-*.md", ["用户故事", "验收场景"]),
            ("1.5", "定共享需求", "01-需求/" + BATCH_TOKEN + "/跨端共享需求.md",
             ["共享范围", "命名规范", "共享接口规范", "共享数据契约",
              "枚举与取值域", "跨端一致性铁律", "分叉点"]),
        ],
    },
    2: {
        "name": "原型设计（Prototype）", "gate": "🔒 闸门 p（原型门）",
        "tasks": [
            ("2.1", "定页面清单", "02-原型/" + BATCH_TOKEN + "/原型说明.md", ["页面清单", "关键交互", "状态覆盖"]),
            ("2.2", "出原型图", "02-原型/" + BATCH_TOKEN + "/原型图.html", ["data-prototype", "data-screen"]),
            ("2.3", "走查并补状态", "02-原型/" + BATCH_TOKEN + "/原型说明.md", ["视觉稿规格", "设计取舍", "走查记录"]),
        ],
    },
    3: {
        "name": "架构设计（Plan，全局共享）", "gate": "🔒 闸门 b（最重）",
        "tasks": [
            # 架构层是「项目总体架构约束层」：全局单例（不属任何批次）、所有批次共享、单一真相；
            # 别处改动须全项目同步，且每份都须在文末「增量更新记录」留台账（锚点为文件夹级纪律）
            ("3.1", "定事实边界", "03-架构/待查证问题.md", ["问题清单", ARCH_LEDGER]),
            ("3.2", "搜索事实", "03-架构/事实纪要.md", ["结论", "来源", ARCH_LEDGER]),
            ("3.3", "抽设计约束", "03-架构/设计约束.md", ["硬约束", "软约束", ARCH_LEDGER]),
            ("3.4", "并行出多案", "03-架构/候选方案.md", ["方案 1", "方案 2", "方案 3", ARCH_LEDGER]),
            ("3.5", "方案对比", "03-架构/方案对比.md", ["对比维度", "推荐", ARCH_LEDGER]),
            ("3.6", "定共享层", "03-架构/跨端共享层.md",
             ["共享层边界与组成", "依赖方向", "契约落点", "序列化与持久化实现", "变更同步机制",
              ARCH_LEDGER]),
            ("3.7", "出方案草案", "03-架构/方案草案.md", ["变更概述", "落地分叉", ARCH_LEDGER]),
        ],
    },
    4: {
        "name": "工程落地计划（Plan 变更清单 → Tasks）", "gate": "🔒 闸门 c1（变更清单）+ c2（任务拆分）",
        "tasks": [
            ("4.1", "审现有架构", "04-落地计划/" + BATCH_TOKEN + "/架构审计.md", ["摩擦点", "风险"]),
            ("4.2", "定变更清单", "04-落地计划/" + BATCH_TOKEN + "/变更清单-*.md", ["文件变更", "依赖", "签名/导航/资源变更"]),
            ("4.3", "定回滚方式", "04-落地计划/" + BATCH_TOKEN + "/回滚方案.md", ["回滚路径"]),
            ("4.4", "拆任务", "04-落地计划/" + BATCH_TOKEN + "/任务拆分.md", ["Tickets"]),
        ],
    },
    5: {
        "name": "TDD 落地（Implementation）", "gate": "🔒 闸门 d",
        "tasks": [
            ("5.1", "选测试栈+seam", "05-实现与测试/" + BATCH_TOKEN + "/测试计划.md", ["测试栈", "seam 位置", "should 用例"]),
            ("5.2", "red 写失败测试", NOT_APPLICABLE, EXISTENCE_ONLY),   # 产物在工程 test/ 目录
            ("5.3", "green 最小实现", NOT_APPLICABLE, EXISTENCE_ONLY),   # 产物在工程 src/ 目录
            ("5.4", "落地层分叉", NOT_APPLICABLE, EXISTENCE_ONLY),      # 产物在工程 src/ 目录
        ],
    },
    6: {
        "name": "编译·测试·审查·交付（Implementation）", "gate": "🔒 交付门",
        "tasks": [
            ("6.1", "双端编译", "06-交付/" + BATCH_TOKEN + "/编译报告-*.md", ["iOS 编译", "Android 编译"]),
            ("6.2", "双轴审查", "06-交付/" + BATCH_TOKEN + "/审查报告-*.md", ["审查结论", "降级说明"]),
            ("6.3", "代码↔文档对账", "06-交付/" + BATCH_TOKEN + "/一致性对账-*.md", ["同步点", "漂移项"]),
            ("6.4", "出交付报告", "06-交付/" + BATCH_TOKEN + "/交付报告-*.md", ["交付清单", "回滚状态"]),
        ],
    },
    7: {
        "name": "反馈闭环", "gate": "（回跳，log 增量）",
        # 阶段 7 是过程动作，只核验 运行日志.jsonl 存在性
        "tasks": [
            ("7.1", "定位失败归属", "99-来源与日志/运行日志.jsonl", EXISTENCE_ONLY),
            ("7.2", "回跳重跑", "99-来源与日志/运行日志.jsonl", EXISTENCE_ONLY),
        ],
    },
}

STATUS_LABEL = {"ok": "已产出", "weak": "缺字段", "missing": "缺失", "skipped": "不判定/已跳过"}
STATUS_COLOR = {"ok": "#1a7f37", "weak": "#b08800", "missing": "#cf222e", "skipped": "#6e7781"}


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

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


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:  # noqa: BLE001
        return None


def is_batch_artifact(artifact):
    return bool(artifact) and BATCH_TOKEN in artifact


# ---------------------------------------------------------------------------
# 第 0 层：批次结构
# ---------------------------------------------------------------------------

def discover_batches(base):
    """批次发现。返回 (批次数列表, {阶段目录: set(批次名) 或 None=阶段目录不存在})。

    批次列表取各阶段目录名的**并集**——某批次可能只在部分阶段落了目录（迭代尚在进行中）。
    """
    per_stage = {}
    for d in BATCH_STAGES:
        p = os.path.join(base, d)
        if not os.path.isdir(p):
            per_stage[d] = None          # 该阶段目录整体不存在
            continue
        per_stage[d] = {n for n in os.listdir(p)
                        if os.path.isdir(os.path.join(p, n)) and not n.startswith(".")}
    names = set()
    for s in per_stage.values():
        if s:
            names |= s
    return sorted(names), per_stage


def check_batch_sequence(batches):
    """批次序号连续性检查，返回提示串（连续则空串）。"""
    nums = []
    for n in batches:
        m = re.match(r"^(\d+)-", n)
        if m:
            nums.append(int(m.group(1)))
    if not nums:
        return ""
    nums.sort()
    if nums != list(range(1, len(nums) + 1)):
        return (f"批次序号不连续（现有 {', '.join('%02d' % x for x in nums)}，"
                f"应为 01~{len(nums):02d}）")
    return ""


def batch_alignment(batch, per_stage):
    """返回该批次在各阶段的存在情况：[(阶段目录, 'ok'|'missing'|'no_stage')]。"""
    out = []
    for d in BATCH_STAGES:
        s = per_stage.get(d)
        if s is None:
            out.append((d, "no_stage"))      # 阶段目录整体未建
        elif batch in s:
            out.append((d, "ok"))
        else:
            out.append((d, "missing"))       # 阶段目录在，但缺该批次
    return out


def check_sequence(names):
    """批次内追加型产物的序号连续性检查，返回提示串（连续则空串）。"""
    nums = []
    for n in names:
        m = re.match(r"^[^\d]*(\d+)-", n)
        if m:
            nums.append(int(m.group(1)))
    if not nums:
        return ""
    nums.sort()
    if nums != list(range(len(nums))):
        return f"序号不连续（现有 {', '.join('%02d' % x for x in nums)}，应为 00~{len(nums)-1:02d}）"
    return ""


# ---------------------------------------------------------------------------
# 第 1/2 层：产物核验
# ---------------------------------------------------------------------------

def check_single(full, keywords):
    """单实例产物核验。返回 (status, detail)。"""
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


def check_multi(base_dir, pattern, keywords):
    """追加型多实例核验。返回 (status, detail, matched_names)。"""
    matches = sorted(glob.glob(os.path.join(base_dir, pattern)))
    if not matches:
        return "missing", "缺失（该模式无匹配文件）", []
    names = [os.path.basename(m) for m in matches]
    bad = []
    for m in matches:
        nm = os.path.basename(m)
        if os.path.getsize(m) == 0:
            bad.append(f"{nm}（空文件）")
            continue
        text = read_text(m)
        if text is None:
            bad.append(f"{nm}（读取失败）")
            continue
        if keywords is EXISTENCE_ONLY:
            continue
        miss = [k for k in keywords if k not in text]
        if miss:
            bad.append(f"{nm}（缺 {'、'.join(miss)}）")
    seq = check_sequence(names)
    listing = "、".join(names) if len(names) <= 4 else "、".join(names[:4]) + f" 等 {len(names)} 个"
    parts = [f"{len(names)} 个：{listing}"]
    if bad:
        parts.append("问题文件：" + "；".join(bad))
    if seq:
        parts.append(seq)
    return ("weak" if bad else "ok"), " · ".join(parts), names


def check_artifact(base_dir, artifact_path, keywords):
    """返回 (status, detail, matched)。artifact_path 为 NOT_APPLICABLE → skipped(不判定)。"""
    if artifact_path is NOT_APPLICABLE:
        return "skipped", "产物在工程目录，由阶段 6.1 编译门兜底", []
    if base_dir is None:
        return "missing", "feature 目录不存在", []
    if "*" in artifact_path:
        return check_multi(base_dir, artifact_path, keywords)
    status, detail = check_single(os.path.join(base_dir, artifact_path), keywords)
    return status, detail, ([os.path.basename(artifact_path)] if status != "missing" else [])


# ---------------------------------------------------------------------------
# 扫描主流程
# ---------------------------------------------------------------------------

def scan(root, feature, skip_artifacts=None, only_batch=None):
    base = os.path.join(root, "docs", feature) if feature else None
    skip = skip_artifacts or set()

    batches, per_stage = (discover_batches(base) if base else ([], {}))
    if only_batch:
        batches = [b for b in batches if b == only_batch]

    totals = {"ok": 0, "weak": 0, "missing": 0, "skipped": 0}
    global_stages = {}     # stage_no -> {name, gate, entries}
    batch_stages = {}      # batch -> {stage_no: {name, gate, entries}}

    def note(status, stage_no, st, task_id, task_name, artifact, detail, matched, multi):
        totals[status] += 1
        return {
            "task_id": task_id, "task_name": task_name,
            "artifact": artifact or "(工程目录)", "status": status,
            "detail": detail, "matched": matched, "multi": multi,
        }

    for stage_no in sorted(DEF):
        st = DEF[stage_no]
        for task_id, task_name, artifact, keywords in st["tasks"]:
            is_skipped = (artifact is not NOT_APPLICABLE
                          and any(fnmatch.fnmatch(artifact, s) for s in skip))
            multi = bool(artifact and "*" in artifact)

            if is_batch_artifact(artifact):
                for b in batches:
                    # 路径里的批次名转义后拼入（保留产物侧通配符 `*`）
                    real = artifact.replace(BATCH_TOKEN, glob.escape(b))
                    if is_skipped:
                        status, detail, matched = "skipped", "lite 档可跳过", []
                    elif base is None:
                        status, detail, matched = "missing", "feature 目录不存在", []
                    else:
                        status, detail, matched = check_artifact(base, real, keywords)
                    e = note(status, stage_no, st, task_id, task_name,
                             real.replace(glob.escape(b), b), detail, matched, multi)
                    slot = batch_stages.setdefault(b, {}).setdefault(
                        stage_no, {"name": st["name"], "gate": st["gate"], "entries": []})
                    slot["entries"].append(e)
            else:
                if is_skipped:
                    status, detail, matched = "skipped", "lite 档可跳过", []
                elif base is None and artifact is not NOT_APPLICABLE:
                    status, detail, matched = "missing", "feature 目录不存在", []
                else:
                    status, detail, matched = check_artifact(base, artifact, keywords)
                e = note(status, stage_no, st, task_id, task_name,
                         artifact, detail, matched, multi)
                slot = global_stages.setdefault(
                    stage_no, {"name": st["name"], "gate": st["gate"], "entries": []})
                slot["entries"].append(e)

    warnings = []
    if feature is None:
        warnings.append("未识别 feature（docs/ 下无子目录），仅能报告「全部缺失」。")
    elif not batches:
        warnings.append(
            "未发现任何批次目录。请先用任务 1.1 在 5 个阶段建立同名批次目录"
            "（如 `01-需求/01-阅读进度续读/` … `06-交付/01-阅读进度续读/`）。")
    else:
        seq = check_batch_sequence(batches)
        if seq:
            warnings.append(seq)
        for b in batches:
            miss = [d for d, s in batch_alignment(b, per_stage) if s == "missing"]
            if miss:
                warnings.append(
                    f"批次 `{b}` 未在 {'、'.join(miss)} 建立同名目录——该批次未跑到这些阶段，"
                    "或目录名拼写不一致。")

    return {
        "batches": batches,
        "per_stage": per_stage,
        "global_stages": global_stages,
        "batch_stages": batch_stages,
    }, totals, base, warnings


# ---------------------------------------------------------------------------
# HTML 报告
# ---------------------------------------------------------------------------

CSS = """
:root{--bg:#f6f8fa;--card:#fff;--line:#d0d7de;--text:#1f2328;--dim:#59636e;}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;
background:var(--bg);color:var(--text);line-height:1.55}
.wrap{max-width:1120px;margin:0 auto;padding:24px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--dim);font-size:13px;margin-bottom:20px}
.summary{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}
.chip{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 18px}
.chip b{display:block;font-size:24px}.chip span{color:var(--dim);font-size:12px}
.warn{background:#fff8c5;border:1px solid #d4a72c;border-radius:8px;padding:10px 14px;
margin-bottom:10px;font-size:13px}
.batch{background:var(--card);border:1px solid var(--line);border-radius:10px;
margin-bottom:18px;overflow:hidden}
.batch-head{padding:12px 16px;background:#eef4ff;border-bottom:1px solid var(--line);
font-weight:600;font-size:15px}
.grp{background:var(--card);border:1px solid var(--line);border-radius:10px;
margin-bottom:18px;overflow:hidden}
.grp-head{padding:12px 16px;background:#f0f7f4;border-bottom:1px solid var(--line);
font-weight:600;font-size:15px}
.align{padding:8px 16px;font-size:12px;color:var(--dim);border-bottom:1px solid var(--line);
background:#fafbfc;font-family:ui-monospace,monospace}
.align .y{color:#1a7f37}.align .n{color:#cf222e}
.stage{border-top:1px solid var(--line)}
.stage:first-of-type{border-top:none}
.stage-head{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;
background:#fafbfc;border-bottom:1px solid var(--line)}
.stage-title{font-weight:600;font-size:14px}
.gate{font-size:12px;color:var(--dim);background:#eaeef2;padding:2px 8px;border-radius:20px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line)}
th{background:#f3f5f7;color:var(--dim);font-weight:600;white-space:nowrap}
tr:last-child td{border-bottom:none}
.tid{color:var(--dim);font-family:ui-monospace,monospace;white-space:nowrap}
.mono{font-family:ui-monospace,monospace;font-size:12px}
.pill{display:inline-block;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px}
.dim{color:var(--dim)}
.tag{display:inline-block;margin-left:6px;font-size:11px;color:#8250df;background:#f3eefc;
border:1px solid #dcc9f5;border-radius:4px;padding:0 5px}
.tag.conv{color:#0a6c53;background:#e6f4ef;border-color:#b7e0d3}
.foot{color:var(--dim);font-size:12px;margin-top:24px;border-top:1px solid var(--line);padding-top:12px}
"""


def render_stage_card(stage_no, st):
    rows = []
    for e in st["entries"]:
        tag = ("<span class='tag'>追加型</span>" if e["multi"]
               else ("<span class='tag conv'>收敛型</span>"
                     if e["artifact"] != "(工程目录)" else ""))
        rows.append(
            "<tr>"
            f"<td class='tid'>{e['task_id']}</td>"
            f"<td>{e['task_name']}</td>"
            f"<td class='mono'>{e['artifact']}{tag}</td>"
            f"<td><span class='pill' style='background:{STATUS_COLOR[e['status']]}'>"
            f"{STATUS_LABEL[e['status']]}</span></td>"
            f"<td class='dim'>{e['detail']}</td>"
            "</tr>")
    return (
        "<div class='stage'>"
        f"<div class='stage-head'><span class='stage-title'>阶段 {stage_no} · {st['name']}</span>"
        f"<span class='gate'>{st['gate']}</span></div>"
        "<table><thead><tr><th>任务</th><th>做什么</th><th>产出物</th><th>状态</th><th>说明</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")


def render_batch_block(batch, stages, align):
    flags = []
    for d, s in align:
        mark = {"ok": "<span class='y'>✓</span>",
                "missing": "<span class='n'>✗</span>",
                "no_stage": "<span class='n'>—</span>"}[s]
        flags.append(f"{d} {mark}")
    inner = "".join(render_stage_card(n, s) for n, s in sorted(stages.items()))
    return ("<div class='batch'>"
            f"<div class='batch-head'>批次 · {batch}</div>"
            f"<div class='align'>阶段对齐：{' | '.join(flags)}"
            "　（✗ = 该阶段有目录但缺此批次；— = 该阶段目录尚未建立）</div>"
            f"{inner}</div>")


def render_html(data, totals, feature, root, tier, warnings, batch_filter=None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    blocks = []

    for w in warnings:
        blocks.append(f"<div class='warn'>⚠ {w}</div>")

    # 全局单例区
    if data["global_stages"]:
        inner = "".join(render_stage_card(n, s) for n, s in sorted(data["global_stages"].items()))
        blocks.append(
            "<div class='grp'><div class='grp-head'>全局单例产物 · 所有批次共享（无批次目录）</div>"
            f"{inner}</div>")

    # 批次区
    for b in data["batches"]:
        stages = data["batch_stages"].get(b, {})
        align = batch_alignment(b, data["per_stage"])
        blocks.append(render_batch_block(b, stages, align))

    if not data["batches"] and batch_filter:
        blocks.append(f"<div class='warn'>⚠ 未找到批次 `{batch_filter}`。</div>")

    scope = f"批次过滤：{batch_filter} · " if batch_filter else ""
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>闭环校验报告 · {feature or '(未识别)'}</title>"
        f"<style>{CSS}</style></head><body><div class=\"wrap\">"
        "<h1>闭环校验报告</h1>"
        f"<div class=\"sub\">feature：<b>{feature or '(未识别)'}</b> · 档位：{tier} · {scope}"
        f"批次：{len(data['batches'])} 个 · 扫描根：{root} · 生成时间：{now}</div>"
        "<div class=\"summary\">"
        f"<div class=\"chip\"><b style=\"color:{STATUS_COLOR['ok']}\">{totals['ok']}</b>"
        "<span>已产出</span></div>"
        f"<div class=\"chip\"><b style=\"color:{STATUS_COLOR['weak']}\">{totals['weak']}</b>"
        "<span>缺字段</span></div>"
        f"<div class=\"chip\"><b style=\"color:{STATUS_COLOR['missing']}\">{totals['missing']}</b>"
        "<span>缺失</span></div>"
        f"<div class=\"chip\"><b style=\"color:{STATUS_COLOR['skipped']}\">{totals['skipped']}</b>"
        "<span>不判定</span></div>"
        "</div>"
        + "".join(blocks) +
        "<div class=\"foot\">本报告由 scan-artifacts.py（批次感知）生成，按 templates/ 必填章节做结构核验。"
        "文档分「批次层（<code>&lt;NN-需求名&gt;</code>，各阶段必须同名对齐）+ 产物层」两级；"
        "产物层带「追加型」标记的为多实例（须至少一个文件且序号从 00 连续），"
        "带「收敛型」的为单例（随上游演进原地更新）。"
        "<code>03-架构/</code> 与 <code>00-入口/</code>、<code>99-来源与日志/</code> 为全局单例，不属任何批次。"
        "本报告不替代人工闸门（a/p/b/c1/c2/d/交付门）。基准见 <code>skill/references/任务拆解.md</code>。</div>"
        "</div></body></html>")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

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
    batch_filter = None
    i = 1
    while i < len(argv):
        if argv[i] == "--feature" and i + 1 < len(argv):
            feature = argv[i + 1]; i += 2
        elif argv[i] == "--tier" and i + 1 < len(argv):
            tier = argv[i + 1]; i += 2
        elif argv[i] == "--batch" and i + 1 < len(argv):
            batch_filter = argv[i + 1]; i += 2
        elif argv[i] == "--out" and i + 1 < len(argv):
            out_path = argv[i + 1]; i += 2
        else:
            i += 1

    feature = feature or find_feature(root)
    if feature is None:
        print("警告：未识别 feature（docs/ 下无子目录），仅能报告「全部缺失」。")
        print("提示：先用 --feature 指定，或让任务 1.1 初始化 docs/<feature>/。")

    skip_artifacts = load_tier(tier)
    data, totals, base, warnings = scan(root, feature, skip_artifacts, batch_filter)
    out = out_path or os.path.join(root, "artifact-scan-report.html")
    html = render_html(data, totals, feature, root, tier, warnings, batch_filter)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"feature: {feature or '(未识别)'} · tier: {tier} · 批次: {len(data['batches'])} 个")
    if data["batches"]:
        print("批次清单: " + "、".join(data["batches"]))
    print(f"结果: 已产出 {totals['ok']} · 缺字段 {totals['weak']} · "
          f"缺失 {totals['missing']} · 不判定/已跳过 {totals['skipped']}")
    for w in warnings:
        print("  ⚠ " + w)
    print(f"报告已生成: {out}")


if __name__ == "__main__":
    main()
