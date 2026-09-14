# 布局用例的素材（device-derived-layout）

这是 `evals/cases/layout-sizes-constant-positions-parent-relative.yaml` 的
`context.repo_fixture`。

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
**20 条关系（fixed 2 / pinned 11 / proportional 5 / intrinsic 2）/ 0 处比例原语 /
9 条 forbiddenLiterals / 5 处字面量违规**。

## 为什么素材里特意混了「应当照原值写」的值

源码里同时有 `kCornerRadius = 12`、`kHairline = 1`、`kMinTapTarget = 44`，以及
`23 / 25 / 68 / 48` 这一批数。这不是为了好看，是**精度探针**。两轴口径下它们各有归属：

- 12（圆角）、1（发丝线）、44（最小点击区）是**设计常量**，保持原值不缩放是**正确**的 ——
  缩放它们才是错的（44pt 的点击区在小屏上会缩到 40pt）；
- 68（卡片高）、48（按钮高）被判成 **`fixed`**：**尺寸是常量**，照设计稿原值写；
- 23（卡片左起）、25（按钮左起）被判成 **`pinned` 的固定内边距**：
  「贴父边 + 固定间距」本来就该写成约束常量。写成比例反而更糟 ——
  `width = 父宽 × 0.9186` 在 393pt 上对得上，在 430pt 宽的设备上只给 13.7pt 边距。

把它们报成「依赖容器尺寸、应该比例化」，正是这条红线最典型的错误理解。所以这条用例
两头都考：漏掉大数值是漏报，报出应当写的值（12/1/44、68/48、23/25）是误报，两头都算不过。

## 正确的结论

不能交付。判据是两层：

1. 计划声明了 5 条 `proportional` 位置关系，源码里**一处比例原语都没有** ——
   一个 `multiplier`、一个 `UILayoutGuide`、一个 `layout_constraintGuide_percent` 都没有；
2. 5 处字面量等于 402×874 上的推导坐标（`321 / 495 / 741 / 83 / 801`），
   这些数字「有出处、算过」，正是最容易被 review 放过的一类，而换台设备就是错的。

结论应落在 `diff/layout-verdict.json`，原始判据在 `diff/layout-proportions.json`
（校验器的产出，不是手工总结的段落）。
