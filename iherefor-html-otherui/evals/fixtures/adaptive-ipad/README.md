# 平板适配用例的素材（adaptive-ipad）

这是 `evals/cases/adaptive-ipad-requires-width-axis.yaml` 的 `context.repo_fixture`。

**只有 `workspace/` 这一层会被拷进用例工作区** —— 本文件写着正确结论，属于判分侧文档，
绝不能进被测 Agent 的工作区。所以 `repo_fixture` 指向的是
`evals/fixtures/adaptive-ipad/workspace`，不是这个目录本身。

## 场景

沿用 Special Offer 页（设计稿画布 393×852，探针设备 402×874），但这一版**多了一条轴**：
实现计划声明了 `adaptiveLayout`（宽度轴），而源码没照它做。

`workspace/src/SpecialOfferViewController.m` 是一份已经「通过」自检的实现：它自己的
`delivery-gate.json` 里七项闸门全 pass、`deliveryReady=true`。

## 三层判据，第一层与第三层是重点

### 计划本身是**完整的**（不要误报）

`ui-implementation-plan.json` 的 `adaptiveLayout`：

| 字段 | 值 |
| --- | --- |
| `model` | `continuous-window-width` |
| `windowSamples` | 4 个，覆盖 `compact` / `medium` / `expanded` |
| `firstLevelWidthClass` | `compact`（第一层位置比例只在这一档生效） |
| `regions[].widthPolicy` | `full-bleed`（hero）/ `max-content-width`（offers、cta，600pt）/ `stacked`（legal） |
| `forbiddenAdaptations` | `uniform-scale` / `stretch-full-width` / `font-scale` |

**把它报成违规（采样不足、policy 非法、禁止清单不全、封顶值缺失）是误报。**
误报比漏报更伤 —— 它会训练出「看到告警就忽略」的习惯。

### 源码没照它做（要报的三条）

| 违规 | 位置 | 为什么截图看不出来 |
| --- | --- | --- |
| `screen-as-layout-source` | `SpecialOfferViewController.m:27` 的 `UIScreen.main.bounds.width` | 全屏下它与 `view.bounds` **恰好相等**，只有分屏 / Slide Over / 自由窗口才分岔 |
| `orientation-locked` | `src/Info.plist` 只有 `UIInterfaceOrientationPortrait` | 竖屏锁死后永远走不到 regular 宽度档，「手机上是对的」证明不了任何事 |
| `missing-max-content-width-idiom` | 计划声明了 offers / cta 的 600pt 封顶，源码里没有任何封顶原语 | 手机档下封顶与不封顶**视觉一致**，像素 diff 全绿 |

实测跑 `scripts/check_adaptive_layout.py --plan ui-implementation-plan.json --source src
--targets adaptive-targets.json`：**4 个采样 / policy 分布 `{full-bleed:1,
max-content-width:2, stacked:1}` / 2 个源码文件 / 3 项违规 / exit 1**。

素材刻意让源码里**不含任何封顶原语的子串**（`maxContentWidth`、`readableContentGuide`、
`maxWidth`、`lessThanOrEqualToConstant`、`layout_constraintWidth_max` 等），否则这条
「声明了却没落地」的判据会静默失效。

### 交付闸门缺第八项

计划声明了 `adaptiveLayout`，闸门因此是 **8 项**，而 `delivery-gate.json` 只有 7 项 ——
缺 `adaptiveAudit`。少一项最容易伪装成「全绿」。

## 正确的结论

`status: fail`、`deliveryReady: false`，判据落在 `diff/adaptive-verdict.json`，
原始判据在 `diff/adaptive-layout.json`（校验器的产出，不是手工总结的段落）。

最常见的错误动作是**只跑 `--plan-only`**：那样只会得到 `status: pass` ——
计划确实没问题，问题在源码。`fail` 样本复刻的正是这个形态。

## 为什么这一关不做像素 diff

Lanhu 只提供一份设计稿，`reference.png` 是某一台设备的像素基准。拿它比 iPad 截图是拿
两个不同画布比对，会直接判「基准不可信」。
所以平板这一关断言的是**几何关系**（`scripts/audit_adaptive.py`），不是像素。
本用例只考静态那一半：几何审计需要真机多采样证据，`environment.type: none` 跑不出来。
