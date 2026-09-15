#!/usr/bin/env python3
"""决定「这轮修复后，该不该再开一轮编译截图」—— 把停止条件从认知判断变成可执行判定。

feedback-loop.md 的「停止条件」有 15 条，其中一半是**机制可判的**（依赖落盘产物里
确定性存在的字段：comparison/alignment 的 status 与 reason、regions 随 y 的变化、
parentRunId 链里上一轮的同区域差）。那些「Agent 该不该再开一轮编译」的判断，正是
最耗墙钟、也最容易被误判（见 feedback-loop.md 的成本结构：98% 是 Agent 循环）。

本脚本只做**机制可判的那一半**：读 run 的落盘产物，给出确定性的 ``stop``（附原因与
动作，Agent 不得再开编译）或 ``continue``（可再开，附注意项）。它**不替代文档**，也
不硬编码那些必须看区域内容才能判的规则（图片 alphaBounds、产品行为是否改变、资源 md5
等 —— 那些仍需 Agent + 人工确认）。

判据来源（仅读落盘产物，不重算、不重复实现任一 audit 逻辑）：

1. alignment 顶层 ``status=needs-review`` 且 ``reason=baseline-disagrees-with-dom``
   ⇒ ``stop``：基准不可信，先修基准（crossCheckRequired 时先交叉复核），禁止改 App 代码。
2. alignment 顶层 ``status=unmeasurable`` ⇒ ``stop``：证据不足，先补齐。
3. comparison ``status=pass-with-review`` 且 ``reason=structural-within-declared-floor``
   ⇒ ``stop``：文字密集页物理下界已达，反复逼近 0 只会白烧轮 + 诱使缩放字号。
4. comparison 只有 ``textureRatio`` 高（structural 与 fill 都在容差内）⇒ ``stop``：
   栅格化噪点不是缺陷，别改代码。
5. comparison ``regions[]`` 的 structuralRatio **随 row 单调递增** ⇒ ``stop``：
   坐标系/比例不一致，回到布局契约的坐标基准，别逐控件微调。
6. 关键产物缺失（无 comparison / 无 alignment / 无 reference）⇒ ``stop``：先补证据。
7. 上一轮（parentRunId 链）同区域 structural/fill 无改善 ⇒ ``stop``：连续两轮无改善，
   请求用户确认根因，别继续自动改。**（可选，需 ``--with-parent`` 才连 parent 一起判）**

其余情况 ⇒ ``continue``（附带「仍要看文档停止条件里那几条语义性规则」的提醒）。

用法：
    python3 scripts/decide_next_step.py --run-dir <run> [--with-parent]

输出：stdout 是人话结论（``停止 / 继续`` + 原因 + 动作），``--output <path>`` 写结构化
JSON（``decision`` / ``reason`` / ``action`` / ``checks[]``）。退出码：0 = continue，
1 = stop（命中硬停止），2 = 用法/读取错误。
"""
import argparse
import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8')), None
    except OSError as exc:
        return None, f'读取失败：{exc}'
    except ValueError as exc:
        return None, f'JSON 解析失败：{exc}'


def load_optional(path):
    if not path:
        return None, None
    p = Path(path)
    if not p.is_file():
        return None, None
    return load_json(p)


def regions_monotonic_in_y(regions):
    """regions 的 structuralRatio 是否随 row 单调递增（误差逐行放大 = 整体映射问题）。

    判定：取每个 row 的**最大** structuralRatio，看是否形成「严格递增且跨度显著」的
    上升序列。要求至少 3 个 row、且首个到末个增幅超过阈值，避免把轻微波动当单调。
    """
    if not regions or not isinstance(regions, list):
        return False
    rows = {}
    for r in regions:
        if not isinstance(r, dict):
            continue
        row = r.get('row')
        s = r.get('structuralRatio')
        if row is None or not isinstance(s, (int, float)):
            continue
        rows.setdefault(row, 0.0)
        rows[row] = max(rows[row], float(s))
    if len(rows) < 3:
        return False
    ordered = [rows[k] for k in sorted(rows)]
    first, last = ordered[0], ordered[-1]
    # 单调不减，且末行相对首行显著放大（≥ 1.5 倍、绝对差 ≥ 0.005）
    strictly_up = all(b >= a for a, b in zip(ordered, ordered[1:]))
    span_big = (last - first) >= 0.005 and last >= first * 1.5
    return strictly_up and span_big and last > first


def parent_no_improvement(run_dir):
    """沿 parentRunId 链找上一轮，比对同区域 structural/fill 是否无改善。

    只做粗粒度：比较本轮与其直接 parent 的整页 structuralRatio 与 fillRatio，
    若本轮两者都不低于 parent（无改善），返回 True。找不到 parent 链则返回 None。
    """
    review, err = load_optional(run_dir / 'review.json')
    if err or not isinstance(review, dict):
        return None
    parent_id = review.get('parentRunId')
    if not parent_id:
        return None
    # parent run 目录：run_dir 的同级目录下
    parent_dir = run_dir.parent / parent_id
    cur_cmp, _ = load_optional(run_dir / 'diff' / 'comparison.json')
    par_cmp, _ = load_optional(parent_dir / 'diff' / 'comparison.json')
    if not cur_cmp or not par_cmp:
        return None
    cur_s = cur_cmp.get('structuralRatio')
    cur_f = cur_cmp.get('fillRatio')
    par_s = par_cmp.get('structuralRatio')
    par_f = par_cmp.get('fillRatio')
    if not isinstance(cur_s, (int, float)) or not isinstance(par_s, (int, float)):
        return None
    # 无改善 = 本轮两个指标都不优于 parent（容差内即算「无改善」）
    no_better_s = cur_s >= par_s - 1e-6
    no_better_f = (cur_f if isinstance(cur_f, (int, float)) else 0) >= (
        par_f if isinstance(par_f, (int, float)) else 0) - 1e-6
    return bool(no_better_s and no_better_f)


def decide(run_dir, with_parent):
    """返回 (decision, reason, action, checks)。decision ∈ {'stop','continue'}。

    判定顺序反映前提依赖：**先判基准可不可信（alignment），再判几何语义（compare）**。
    若基准本身不可信，compare 的下界/单调/噪点结论都建立在错误基准上，不得据此下结论。
    """
    checks = []
    diff = run_dir / 'diff'
    comparison_path = diff / 'comparison.json'
    alignment_path = diff / 'alignment.json'

    # 6. 关键产物缺失 ⇒ stop（comparison 是几何结论的前提，必须先有）
    comparison, err_c = load_optional(comparison_path)
    alignment, err_a = load_optional(alignment_path)
    if comparison is None:
        checks.append({'check': 'comparison-present', 'stop': True})
        return 'stop', '缺少 diff/comparison.json（像素比较没跑或没落盘）', \
               '先补齐比较证据，再决定下一步', checks
    if comparison.get('status') == 'fail' and comparison.get('reason') == 'size-mismatch':
        checks.append({'check': 'size-consistent', 'stop': True})
        return 'stop', '比较器判尺寸不一致（size-mismatch），基准/截图不是同源同尺寸', \
               '重渲染同源基准或同尺寸截图，禁止用缩放/裁剪派生图凑尺寸', checks

    # ── 第一层：基准可信度（alignment），是后面一切几何结论的前提 ──
    if alignment is not None:
        a_status = alignment.get('status')
        a_reason = alignment.get('reason')
        # 1. 基准不可信 ⇒ stop
        if a_status == 'needs-review' and a_reason == 'baseline-disagrees-with-dom':
            cc = alignment.get('crossCheckRequired')
            action = ('先做交叉复核（alignment.json 的 crossCheck.how），再决定是否重渲染基准并重新批准；'
                      '禁止在此状态下照着 referenceVsActual 的差去改 App 代码') if cc else \
                     ('先重渲染基准并重新批准，再比较实测截图；禁止改 App 代码')
            checks.append({'check': 'baseline-trustworthy', 'stop': True})
            return 'stop', f'对齐审计：基准图与 DOM 事实不符（{a_reason}），基准不可信', action, checks
        # 2. 证据不足 ⇒ stop
        if a_status == 'unmeasurable':
            checks.append({'check': 'alignment-measurable', 'stop': True})
            return 'stop', f'对齐审计不可测（{a_reason or "unmeasurable"}），证据不足', \
                   '先补齐 page-facts.json / runtime-device.json（或放宽探针阈值）再判', checks
        checks.append({'check': 'alignment-ok', 'stop': False})
    else:
        checks.append({'check': 'alignment-present', 'stop': False})

    # ── 第二层：几何语义（compare），基准可信之后才有意义 ──
    # 3. 物理下界已达 ⇒ stop
    if comparison.get('status') == 'pass-with-review' and comparison.get('reason') == 'structural-within-declared-floor':
        checks.append({'check': 'declared-floor-reached', 'stop': True})
        return 'stop', '文字密集页的物理下界已声明并命中（structural-within-declared-floor）', \
               '停止修改，记 pass-with-review + 量化归因；不要反复逼近不存在的 0，也不要缩放字号凑闸门', checks

    # 4. 只有纹理噪点 —— 软提示，不硬停。
    # 原停止条件的语义是「别为了修 textureRatio 去改代码」；但它本身不构成再开一轮的
    # 障碍（structural/fill 若有真实差异，纹理不是障碍）。只有 structural 与 fill 都
    # **显著低于容差**（接近 0）而 texture 异常高时，才值得把「这是噪点」标出来。
    s = comparison.get('structuralRatio')
    f = comparison.get('fillRatio')
    t = comparison.get('textureRatio')
    if all(isinstance(v, (int, float)) for v in (s, f, t)):
        warn_s = comparison.get('warnStructuralRatio')
        max_f = comparison.get('maxFillRatio')
        th_s = warn_s if isinstance(warn_s, (int, float)) else 0.02
        th_f_mx = max_f if isinstance(max_f, (int, float)) else 0.1
        # structural 与 fill 都远低于容差（≤ 其 1/4），texture 却显著高于两者
        if s <= th_s and f <= th_f_mx and t > max(s, f) * 4 and t > 0.01:
            checks.append({'check': 'texture-only-noise', 'stop': False,
                           'note': f'structural={s:.5f} fill={f:.5f} 都近 0，纹理 {t:.5f} 是栅格化噪点，别为它改代码'})

    # 5. 偏差随 y 单调递增 ⇒ stop
    regions = comparison.get('regions')
    if regions_monotonic_in_y(regions):
        checks.append({'check': 'y-monotonic-drift', 'stop': True})
        return 'stop', 'structualRatio 随 row（y 方向）单调递增，是整体映射/比例不一致', \
               '回到布局契约的坐标基准核对，不要逐控件微调位置', checks

    # 7. 连续两轮无改善（可选，需 --with-parent）
    if with_parent:
        no_impr = parent_no_improvement(run_dir)
        if no_impr is True:
            checks.append({'check': 'parent-no-improvement', 'stop': True})
            return 'stop', '连续两轮同一区域无改善（与 parentRunId 相比 structural/fill 均未下降）', \
                   '暂停自动修改，展示证据并请求用户确认根因', checks
        elif no_impr is False:
            checks.append({'check': 'parent-improved', 'stop': False})

    return 'continue', None, None, checks


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run-dir', required=True, help='run 目录（runs/<run-id>）')
    ap.add_argument('--with-parent', action='store_true',
                    help='连 parentRunId 链的上一轮一起判「连续两轮无改善」')
    ap.add_argument('--output', help='把结构化结论写到该路径')
    ap.add_argument('--quiet', action='store_true', help='不打印人话结论')
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        print(f'error: run 目录不存在：{run_dir}', file=sys.stderr)
        return 2

    decision, reason, action, checks = decide(run_dir, args.with_parent)

    payload = {
        'schemaVersion': 1,
        'runDir': str(run_dir),
        'decision': decision,
        'reason': reason,
        'action': action,
        'checks': checks,
        'note': ('本判定只覆盖机制可判的停止条件；图片 alphaBounds、产品行为是否改变、'
                 '资源 md5 分档等语义性规则仍需按 feedback-loop.md「停止条件」人工核对。'),
    }
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')

    if not args.quiet:
        if decision == 'stop':
            print(f"停止：{reason}")
            if action:
                print(f"动作：{action}")
        else:
            print("继续：未命中硬停止条件，可再开一轮编译")
        print("（其余语义性停止条件仍需按 feedback-loop.md 人工核对）")

    return 0 if decision == 'continue' else 1


if __name__ == '__main__':
    sys.exit(main())
