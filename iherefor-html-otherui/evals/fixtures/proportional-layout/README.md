# 布局比例用例的素材（proportional-layout）

这是 `evals/cases/layout-must-follow-design-proportions.yaml` 的 `context.repo_fixture`。

**只有 `workspace/` 这一层会被拷进用例工作区** —— 本文件写着正确结论，属于判分侧文档，
绝不能进被测 Agent 的工作区。所以 `repo_fixture` 指向的是
`evals/fixtures/proportional-layout/workspace`，不是这个目录本身。

## 场景

Lanhu 导出页（Special Offer），设计稿画布 **393×852**，探针设备 **402×874**。
`workspace/src/SpecialOfferViewController.m` 是一份已经「通过」自检的实现：
它自己的 run 里 `implementation=pass`、`deliveryReady=true`。

但源码里一处比例原语都没有，位置与尺寸全是按探针设备换算出来的绝对值：

| 行 | 源码 | 等于的设备推导值 | 应当使用 |
| --- | --- | --- | --- |
| :11 | `kCanvasWidth = 393.0` | `page.width` | 比例 0.977612 |
| :12 | `kCanvasHeight = 852.0` | `page.height` | 比例 0.974828 |
| :26 | `CGRectMake(0, 0, 393, 321)` | `hero.height` | 比例 0.367277 |
| :32 | `SpecialOfferOffersLocalRect(23, 495, 347, 68)` | `offers.width` | 比例 0.863184 |
| :39 | `CGRectMake(25, 741, 352, 48)` | `cta.top` | 比例 0.847826 |
| :46 | `CGRectMake(83, 801, 232, 16)` | `legal.top` | 比例 0.916476 |

实测跑 `scripts/check_layout_proportions.py`：**19 条 proportional 关系 / 0 处比例原语 /
12 处字面量违规 / 3 处待判**。

## 为什么素材里特意混了设计常量

源码里同时有 `kCornerRadius = 12`、`kHairline = 1`、`kMinTapTarget = 44`，以及
`23 / 25 / 48` 这批小数值。这不是为了好看，是**精度探针**：

- 12（圆角）、1（发丝线）、44（最小点击区）是**设计值**，保持原值不缩放是**正确**的 ——
  缩放它们才是错的（44pt 的点击区在小屏上会缩到 40pt）。把它们报成违规就是误报。
- 23 / 25 / 48 这类小数值既可能是设计常量，也可能是抄来的设备值：没有语法信息时
  无法区分。工具把它们放进 `ambiguousLiterals` 待人工判断，**不计入违规** ——
  闸门要准，不是要响。

所以这条用例两头都考：漏掉大数值是漏报，报出设计常量是误报，两头都算不过。

## 正确的结论

不能交付。判据是两层：

1. 计划声明了 19 条 `proportional` 关系，源码里**一处比例原语都没有** ——
   一个 `multiplier`、一个 `UILayoutGuide`、一个 `layout_constraintGuide_percent` 都没有；
2. 12 处字面量等于 402×874 上的设备推导值，这些数字「有出处、算过」，
   正是最容易被 review 放过的一类，而换台设备就是错的。

结论应落在 `diff/proportion-verdict.json`，原始判据在 `diff/layout-proportions.json`
（校验器的产出，不是手工总结的段落）。
