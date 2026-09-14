这个 run 不能交付，`implementation=pass` 与 `deliveryReady=true` 是错的。

**判据**：计划声明了 19 条 `proportional` 关系，而源码里一处比例原语都没有 ——
一个 `multiplier`、一个 `UILayoutGuide`、一个 `layout_constraintGuide_percent` 都没有。
整页是拿绝对值堆出来的。

**铁证是这些数字**（它们等于 402x874 探针设备上的推导值，换台设备即失效）：

| 行 | 字面量 | 对应关系 | 应当使用 |
| --- | --- | --- | --- |
| :11 | `kCanvasWidth = 393.0` | `page.width` | 比例 0.977612 |
| :26 | `CGRectMake(0, 0, 393, 321)` | `hero.height` | 比例 0.367277 |
| :32 | `SpecialOfferOffersLocalRect(23, 495, 347, 68)` | `offers.width` | 比例 0.863184 |
| :39 | `CGRectMake(25, 741, 352, 48)` | `cta.top` | 比例 0.847826 |

这些数字「有出处、算过」，正是最容易被 review 放过的一类。

**哪些不是违规**：圆角 12、发丝线 1、最小点击区 44 是设计值，保持原值不缩放 ——
缩放它们才是错的（44pt 的点击区在小屏上会缩到 40pt）。数值 23 / 25 / 48 与小尺寸
设计常量无法区分，工具把它们列在 `ambiguousLiterals` 里待人工判断，我没有把它们算作违规。

结论已落在 `diff/proportion-verdict.json`，原始判据在 `diff/layout-proportions.json`。
源码未改动。
