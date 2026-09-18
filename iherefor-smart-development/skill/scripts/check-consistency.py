#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check-consistency.py — iherefor-smart-development 四份同源文件一致性核验器

背景：本 skill 的「机检契约」分散在四处，任何一处改动都必须同步其余三处，否则校验会假绿：
  ① `scripts/scan-artifacts.py` 的 DEF 常量        —— 权威基准（产物路径 + 必填章节锚点）
  ② `templates/` 下的模板文件                        —— 产物长什么样的空壳
  ③ `templates/模板说明.md` 第 6 节清单表            —— 给人和模型看的映射表
  ④ `references/任务拆解.md` 各阶段「产出物」列      —— 给编排器看的任务契约

本脚本把 ①②③④ 逐一对照，任一处漂移即报错退出。改完契约后**必跑**。

约定差异（不是漂移，脚本显式归一化）：
  - 追加型产物：DEF 用 glob（`需求-*.md`），人类文档用 `需求-NN-<短名>.md`。两者视为等价。
  - 模板文件名：DEF 的 glob 映射到模板的 `00-<短名>` 占位（`需求-*.md` → `需求-00-<短名>.md`）。
  - 批次层：DEF 与模板目录都用 `<批次>` 占位符（= `NN-<需求名>`），无需归一化。
  - 同一产物被多个任务核验（如 `02-原型/<批次>/原型说明.md` 由 2.1 与 2.3 分段核验）：
    清单表须列出锚点的**并集**。

用法:
    python3 check-consistency.py            # 在 skill/ 目录下跑
    python3 check-consistency.py --skill <skill目录>
"""

import os
import re
import sys
import importlib.util

# 非模板化的产物（日志类），不要求有模板文件，也从清单表豁免
NON_TEMPLATE_ARTIFACTS = {"99-来源与日志/运行日志.jsonl"}

BATCH_TOKEN = "<批次>"

PROBLEMS = []


def load_def(skill_dir):
    path = os.path.join(skill_dir, "scripts", "scan-artifacts.py")
    spec = importlib.util.spec_from_file_location("scan_artifacts", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DEF


def glob_to_template(p):
    """DEF 的 glob 路径 → 模板文件名（`*` → `00-<短名>`；`<批次>` 原样保留）。"""
    return p.replace("*", "00-<短名>")


def text_to_glob(t):
    """人类写法 → glob 写法：`NN-<短名>` / `00-<短名>` 归一化为 `*`。

    约定差异（不是漂移）：
      DEF 用 glob（`需求-*.md`，脚本要匹配多实例）
      人类文档用 `需求-NN-<短名>.md`（人看得懂）
    两侧都归一化到 glob 形式后再比对。
    """
    return re.sub(r"(?<=-)(?:NN|\d{2})-<短名>", "*", t)


def norm_scope(s):
    return s.replace("*", "").strip()


def main():
    skill_dir = os.getcwd()
    argv = sys.argv[1:]
    if "--skill" in argv:
        skill_dir = os.path.abspath(argv[argv.index("--skill") + 1])
    os.chdir(skill_dir)

    DEF = load_def(skill_dir)

    # ── ① 展开 DEF：路径 → [(task_id, anchors)]，支持同一路径多任务 ──────────
    path_tasks = {}          # artifact_path -> list[(task_id, anchors)]
    path_is_multi = {}       # artifact_path -> bool
    path_is_batch = {}       # artifact_path -> bool（是否批次内产物）
    for _stage, st in sorted(DEF.items()):
        for tid, _tname, art, kw in st["tasks"]:
            if art is None:
                continue
            path_tasks.setdefault(art, []).append((tid, kw))
            path_is_multi[art] = "*" in art
            path_is_batch[art] = BATCH_TOKEN in art

    # ── ② 模板文件存在性（双向） ─────────────────────────────────────────
    tmpl_files = set()
    for root, _dirs, files in os.walk("templates"):
        for fn in files:
            if fn == "模板说明.md" or fn.startswith("."):
                continue
            tmpl_files.add(os.path.relpath(os.path.join(root, fn), "templates"))

    real_artifacts = {a for a in path_tasks if a not in NON_TEMPLATE_ARTIFACTS}
    claimed = {glob_to_template(a) for a in real_artifacts}

    for art in sorted(real_artifacts):
        tp = glob_to_template(art)
        if tp not in tmpl_files:
            PROBLEMS.append(f"[模板缺失] DEF 产物 `{art}` 找不到模板 `templates/{tp}`")
    for tp in sorted(tmpl_files - claimed):
        PROBLEMS.append(f"[孤儿模板] `templates/{tp}` 未被 DEF 任何任务引用")

    # ── ③ 模板说明.md 第 6 节清单表 ↔ DEF ────────────────────────────────
    rows = {}
    with open("templates/模板说明.md", encoding="utf-8") as f:
        for line in f:
            m = re.match(
                r"^\|\s*`templates/(.+?)`\s*\|\s*`(.+?)`\s*\|\s*(\*\*)?(全局单例|批次内)(\*\*)?\s*"
                r"\|\s*(收敛型|追加型)\s*\|\s*(.+?)\s*\|\s*$",
                line.strip())
            if m:
                rows[m.group(1)] = (m.group(2), m.group(4), m.group(6), m.group(7))

    for tp, (prod, scope, typ, anchors) in sorted(rows.items()):
        if tp not in claimed:
            PROBLEMS.append(f"[清单越界] `模板说明.md` 列出 `{tp}`，但 DEF 无对应产物")
            continue
        art = next(a for a in real_artifacts if glob_to_template(a) == tp)
        # 作用域
        expect_scope = "批次内" if path_is_batch[art] else "全局单例"
        if norm_scope(scope) != expect_scope:
            PROBLEMS.append(f"[作用域不符] `{tp}` 清单标 {norm_scope(scope)}，DEF 判定为 {expect_scope}")
        # 类型
        expect_typ = "追加型" if path_is_multi[art] else "收敛型"
        if typ != expect_typ:
            PROBLEMS.append(f"[类型不符] `{tp}` 清单标 {typ}，DEF 判定为 {expect_typ}")
        # 产物列（glob ↔ NN-<短名> 归一化后比对）
        if text_to_glob(prod) != text_to_glob(art):
            PROBLEMS.append(f"[产物名不符] `{tp}` 清单产物列=`{prod}`，DEF=`{art}`")
        # 锚点：清单须为多任务锚点的并集
        union, seen = [], set()
        for _tid, kw in path_tasks[art]:
            for k in kw:
                if k not in seen:
                    seen.add(k)
                    union.append(k)
        def_anchors = " · ".join(union)
        if anchors != def_anchors:
            PROBLEMS.append(
                f"[锚点漂移] `{tp}`\n    清单 = {anchors}\n    DEF = {def_anchors}")

    if set(rows) != claimed:
        for tp in sorted(claimed - set(rows)):
            PROBLEMS.append(f"[清单遗漏] DEF 有 `{tp}`，但 `模板说明.md` 清单未列")

    # ── ④ 任务拆解.md 各阶段产出物列 ↔ DEF ──────────────────────────────
    with open("references/任务拆解.md", encoding="utf-8") as f:
        tb = f.read()
    tb_glob = text_to_glob(tb)      # 归一化到 glob 写法后做包含判断
    for art in sorted(real_artifacts):
        tp = glob_to_template(art)
        if art in tb_glob or tp in tb_glob:
            continue
        PROBLEMS.append(f"[任务拆解遗漏] `references/任务拆解.md` 未提及产物 `{art}`")

    # ── 输出 ───────────────────────────────────────────────────────────
    n_batch = sum(1 for a in real_artifacts if path_is_batch[a])
    n_global = len(real_artifacts) - n_batch
    print("=" * 72)
    print(f"skill 目录：{skill_dir}")
    print(f"DEF 产物条目 {len(path_tasks)} 条（需模板 {len(real_artifacts)} 条）")
    print(f"  批次内 {n_batch} 条 · 全局单例 {n_global} 条")
    print(f"  追加型 {sum(path_is_multi[a] for a in path_is_multi)} 条 · "
          f"收敛型 {sum(not path_is_multi[a] for a in path_is_multi)} 条")
    print(f"模板文件 {len(tmpl_files)} 个 · 清单表 {len(rows)} 行")
    print("=" * 72)
    if PROBLEMS:
        print(f"发现 {len(PROBLEMS)} 处漂移：")
        for p in PROBLEMS:
            print("  ✗", p)
        print("\n提示：四份同源文件（scan-artifacts.py DEF / templates/ / "
              "模板说明.md / 任务拆解.md）必须同步修改。")
        return 1
    print("四份同源文件一致性：全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
