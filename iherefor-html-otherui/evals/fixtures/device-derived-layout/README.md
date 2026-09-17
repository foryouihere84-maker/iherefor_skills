# 布局用例的素材（device-derived-layout）

这是 `evals/cases/layout-no-device-derived-coordinates.yaml` 的 `context.repo_fixture`。

**只有 `workspace/` 这一层会被拷进用例工作区** —— 本文件写着正确结论，属于判分侧文档，
绝不能进被测 Agent 的工作区。所以 `repo_fixture` 指向的是
`evals/fixtures/device-derived-layout/workspace`，不是这个目录本身。

`workspace/reference/` 只放本用例真正要读的 `page-facts.json`。真实 run 的
`reference/` 里还有 `reference.png` / `browser-meta.json` / `approved.json`，本用例一个都
不读 —— 素材里多放一份**形状停留在旧版渲染器**的文件，只会让读素材的人按错的字段形状
去理解契约。

## 场景

Lanhu 导出页（Special Offer），设计稿画布 **393×852**，实机（探针设备）**402×874**。
`workspace/src/SpecialOfferViewController.m` 是一份已经「通过」自检的实现：它自己的
`delivery-gate.json` 里七项闸门全 pass、`deliveryReady=true`。

但源码里一处比例原语都没有，位置与尺寸全是绝对 frame：

| 行 | 源码 | 判成什么 | 结论 |
| --- | --- | --- | --- |
| :26 | `CGRectMake(0, 0, 393, 321)` | `hero.height` proportional 0.376761 | **`321` 是违规** |
| :32 | `SpecialOfferOffersLocalRect(23, 495, 347, 68)` | `offers.top` proportional 0.580986 | **`495` 是违规**；`23`/`68` 不是 |
| :39 | `CGRectMake(25, 741, 352, 48)` | `cta.top` proportional 0.869718 | **`741` 是违规**；`25`/`48` 不是 |
| :48 | `CGRectMake(83, 801, 232, 16)` | `legal.leading` / `legal.top` proportional 0.211196 / 0.940141 | **`83`、`801` 是违规** |
| :11/:12 | `kCanvasWidth = 393` / `kCanvasHeight = 852` | `page.*` pinned（页面外框铺满） | 不在禁止清单里 |

实测跑 `scripts/layout_proportions.py` + `scripts/check_layout_proportions.py`：
**20 条关系（fixed 候选 2 / pinned 7 / proportional 9 / intrinsic 2）/ 0 处比例原语 /
15 条 forbiddenLiterals / 5 处字面量违规 / 2 处待判（23、25）/ 0 条闭合判据违规**。

## 为什么素材里特意混了「报出来就是误报」的值

源码里同时有 `kCornerRadius = 12`、`kHairline = 1`、`kMinTapTarget = 44`，以及
`23 / 25 / 68 / 48` 这一批数。这不是为了好看，是**精度探针**。闭合契约下它们各有归属，
而且**归属理由各不相同**：

- 12（圆角）、1（发丝线）、44（最小点击区）是**设计常量**，保持原值不缩放是**正确**的 ——
  缩放它们才是错的（44pt 的点击区在小屏上会缩到 40pt）；
- 68（卡片高）、48（按钮高）被生成端推成 **`fixed` 候选**，带 `needsReview`：
  闭合契约下 `fixed` 只留给图标/装饰/边框/明确固定高度的视觉控件，卡片与按钮的高度
  由内容闭合 —— 所以它们的**正确处置是「复核后改判 `intrinsic` / `bounded`」**，
  写进 `reviewPending`。但**待复核 ≠ 违规**：把它们报成「这个值不该出现」是误报，
  和把它们当「设计稿给的固定尺寸」照收一样错；
- 23（卡片左起）、25（按钮左起）是**第一层子视图的水平位置**（offers/cta 直接挂在 page
  下），按契约该按页面宽度比例写，写死也是错 —— 只是因为 `≤48pt`，检查端无法与设计常量
  自动区分，只能落 `ambiguousLiterals` 待人工判断，**不判成硬违规**。这一点与 68/48
  不同：23/25 的问题是「判不出来」，68/48 的问题是「判出来了、但结论不是违规」。

把它们一股脑报成「依赖容器尺寸、应该比例化」，正是这条红线最典型的错误理解。所以这条用例
两头都考：漏掉大数值是漏报；报出 12/1/44、68/48、23/25 是误报，两头都算不过。

> 旧口径（v3）在这里靠一句话打包豁免：`fixed` = 尺寸是常量。新契约没有这句话了，
> 豁免理由必须逐类说清 —— 这恰好是本用例在 v4 下**更有价值**的地方：它不再只考
> 「知不知道尺寸要不要缩放」，而是考「**每条尺寸由谁闭合、判决权在谁手上**」。

## 正确的结论

不能交付。判据是两层：

1. 计划声明了 9 条 `proportional` 位置关系，源码里**一处比例原语都没有** ——
   一个 `multiplier`、一个 `UILayoutGuide`、一个 `layout_constraintGuide_percent` 都没有；
2. 5 处字面量等于 402×874 上的推导坐标（`321 / 495 / 741 / 83 / 801`），
   这些数字「有出处、算过」，正是最容易被 review 放过的一类，而换台设备就是错的。

外加一条闭合契约特有的动作：把生成端标了 `needsReview` 的 `offers.height` / `cta.height`
接住，在 `diff/layout-verdict.json` 的 `reviewPending` 里给出复核结论。

结论应落在 `diff/layout-verdict.json`，原始判据在 `diff/layout-proportions.json`
（校验器的产出，不是手工总结的段落）。
