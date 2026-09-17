# iOS 自适应布局实践（强制）

> 本文是 `SKILL.md`「UIKit Auto Layout 尺寸契约」的权威展开，与
> [sizing-and-positioning.md](sizing-and-positioning.md) §2（尺寸轴）配套阅读。
> 该文规定的是什么量该用哪一类；本文规定的是每一类在四套技术栈里**怎么写**、
> **优先级怎么配**、以及交付前**怎么验证**。

## 0. 一句话

**Lanhu 的 `bounds` 是视觉参考，不是最终 Auto Layout 约束。**
实现前先判断每个尺寸由什么闭合，再把约束写进计划。一步都不能省：
`bounds` → 判定闭合方式 → 写约束 → 验证四类失效场景。

「设计稿给了 220 宽」不构成写 `constraintEqualToConstant: 220` 的理由 ——
那只是「在这台设备上量到 220」，而约束要保证的是**在任何宽度档、任何字号、任何语言下都成立**。

## 1. 八类 kind 的四平台等价写法

### 1.1 对照表

| `kind` | UIKit（Swift / ObjC） | SwiftUI | Compose | Views / XML |
|---|---|---|---|---|
| `fixed` | `constraintEqualToConstant:` | `.frame(width:)` / `.frame(height:)` | `.size()` / `.width()` / `.height()` | `layout_width="64dp"` |
| `intrinsic` | **不写宽高约束**，依赖 `intrinsicContentSize`；`sizeToFit()` / `systemLayoutSizeFitting` | 不给 `.frame`，让内容决定 | `wrapContentSize()` | `wrap_content` |
| `bounded` | `greaterThanOrEqualToConstant:` / `lessThanOrEqualToConstant:` | `.frame(minWidth:)` / `maxWidth:` / `minHeight:` | `.widthIn(min, max)` / `.heightIn(min, max)` / `sizeIn` | `layout_constraintWidth_min/max`、`minWidth`/`maxWidth` |
| `pinned` | `leadingAnchor` / `trailingAnchor` / `topAnchor` / `bottomAnchor` + `constant` | `.padding(.horizontal, 16)` + 父容器对齐 | `.padding()` + `fillMaxWidth()` / `align()` | `layout_constraint*_to*Of` + `layout_margin*` |
| `proportional` | `constraint(equalTo:…, multiplier:)` | `GeometryReader` 归一化、`.containerRelativeFrame` | `BoxWithConstraints` 的 `maxWidth` 派生、`weight` | `layout_constraintGuide_percent`、`layout_weight`、`layout_constraintDimensionRatio` |
| `equal` | `constraint(equalTo: sibling.widthAnchor)` | `.frame(maxWidth: .infinity)` 共享 + `HStack` 等分 | `Row` + `weight(1f)`；`IntrinsicSize` | `layout_constraintWidth` 互指、`layout_weight` |
| `centered` | `centerXAnchor` / `centerYAnchor` / `firstBaselineAnchor` 相等 | `.frame(maxWidth:.infinity, alignment:.center)` | `.align(Alignment.CenterHorizontally)` | `layout_constraint*_to*Of="parent"` + 居中 |
| `aspect-ratio` | `widthAnchor.constraint(equalTo: heightAnchor, multiplier: ratio)` | `.aspectRatio(16/9, contentMode: .fit)` | `.aspectRatio(16f/9f)` | `layout_constraintDimensionRatio="H,16:9"` |

### 1.2 关键界线：`fixed` 与 `intrinsic` 的区别不在写法，在**有没有那条约束**

```objc
// intrinsic：不给宽高，标签自己算
[label.leadingAnchor constraintEqualToAnchor:card.leadingAnchor constant:16];
[label.trailingAnchor constraintEqualToAnchor:card.trailingAnchor constant:-16];
[label.topAnchor constraintEqualToAnchor:card.topAnchor constant:12];
[label.bottomAnchor constraintEqualToAnchor:card.bottomAnchor constant:-12];

// bounded：给上下界，不给等值
[button.heightAnchor constraintGreaterThanOrEqualToConstant:44];
[button.widthAnchor constraintLessThanOrEqualToConstant:320];

// fixed：只有视觉常量才这样写
[icon.widthAnchor constraintEqualToConstant:24];
[icon.heightAnchor constraintEqualToConstant:24];
```

**反面写法（旧契约的默认行为，新契约下判违规）：**

```objc
[label.widthAnchor constraintEqualToConstant:220];    // 文本宽度写死 → 换语言/开大字号必截断
[label.heightAnchor constraintEqualToConstant:20];    // 单行高度写死 → 多行文本被裁掉
[button.widthAnchor constraintEqualToConstant:120];   // 按钮宽度写死 → 长文案溢出
[button.heightAnchor constraintEqualToConstant:44];   // 触控下限写成固定高度 → 大字号下压扁
```

### 1.3 「设计稿有值」不等于「要写约束」

四种情况要分清：

| 设计稿给的 | 该怎么写 | 理由 |
|---|---|---|
| 图标 24×24 | `fixed` 24 | 图标是视觉常量，固定性本身是设计意图 |
| 卡片高 68（内含两行文本） | `intrinsic` + `minimumHeight = 68` | 68 是「不换行时的自然高度」，不是物理常量 |
| 按钮高 48 | `bounded >= 44` | 48 是视觉高度，44 是触控下限；大字号下允许增高 |
| 卡片宽 345（左右各 24） | `pinned` 左右 24（+ 可选 `bounded max`） | 345 是 `393 - 24×2` 的结果，不是因；边距才是因 |

判据：**把设计稿的宽度换掉，这个值还成立吗？** 不成立 → 它不是 `fixed`。

## 2. 优先级策略：谁扩张、谁压缩

光有约束还不够。Auto Layout 在「内容比容器大」或「内容比容器小」时，靠两类优先级仲裁。
**不显式设置，等于把仲裁交给系统默认值，行为不可预期。**

### 2.1 两类优先级

| 优先级 | 语义 | 默认值 | 调高的含义 |
|---|---|---|---|
| `contentHuggingPriority` | 抗拉伸 | `250`（`.defaultLow`） | 越大越**不愿变大** |
| `contentCompressionResistancePriority` | 抗压缩 | `750`（`.defaultHigh`） | 越大越**不愿变小** |

### 2.2 分配规则

- **必须完整显示的文本**（标题、价格、错误提示）→ 压缩阻力 `required`（1000），
  拉伸优先级低（`.defaultLow`）。它宁可把邻居挤开，也不许自己被截断。
- **可截断的次要文本**（副标题、时间戳）→ 压缩阻力 `.defaultLow`（250），
  设 `lineBreakMode = .byTruncatingTail`。
- **弹性填充区**（占位、分隔）→ 拉伸优先级 `.defaultLow` / `low`，让它吸收多余空间。
- **图标、视觉常量** → 压缩阻力 `required`，宽度由 `fixed` 约束钉死。
- **同优先级的兄弟会冲突** → 两个都是 `required` 且空间不足时，Auto Layout 会
  打破其中一条并打印 `Unable to simultaneously satisfy constraints`。必须靠 `>=` / `<=`
  或不同优先级制造出唯一的解。

```objc
// 标题：宁可挤压邻居，也不许自己被截断
[titleLabel setContentHuggingPriority:UILayoutPriorityDefaultLow
                              forAxis:UILayoutConstraintAxisHorizontal];
[titleLabel setContentCompressionResistancePriority:UILayoutPriorityRequired
                                           forAxis:UILayoutConstraintAxisHorizontal];

// 副标题：空间不够时先让它截断
[subtitleLabel setContentCompressionResistancePriority:UILayoutPriorityDefaultLow
                                              forAxis:UILayoutConstraintAxisHorizontal];
subtitleLabel.lineBreakMode = NSLineBreakByTruncatingTail;

// 图标：不许被压小
[iconView setContentCompressionResistancePriority:UILayoutPriorityRequired
                                         forAxis:UILayoutConstraintAxisHorizontal];
```

SwiftUI 里对应的是 `.layoutPriority(_:)`；Compose 里是 `Modifier.weight(..., fill = false)`
与 `Row`/`Column` 的测量顺序；Views 里是 `layout_constraintHorizontal_weight` 与
`layout_constraintHorizontal_chainStyle`。

### 2.3 两条硬规则

1. **凡是有两个及以上可变文本在同一行，必须显式分配压缩阻力。** 否则宽度不够时是随机截断。
2. **不许用 `required` 硬撑出冲突。** 冲突约束会在运行期被打破，且 `ambiguous layout` 会让
   几何在不同 iOS 版本上不一致。宁可给 `>=` / `<=` 或降一级优先级。

## 3. Dynamic Type（动态字体）

### 3.1 硬要求

- **字号走缩放通道，不走布局缩放。** UIKit 用 `UIFontMetrics` 包一层：

```objc
UIFont *base = [UIFont systemFontOfSize:17 weight:UIFontWeightSemibold];
label.font = [[UIFontMetrics metricsForTextStyle:UIFontTextStyleBody] scaledFontForFont:base];
label.adjustsFontForContentSizeCategory = YES;   // 系统字号变化时自动重算
```

SwiftUI 用 `.font(.body)` 或 `.font(.custom(..., relativeTo: .body))`；Compose 用
`MaterialTheme.typography` 或 `TextUnit` 的 `sp` 单位（`sp` 已含用户字号缩放，`dp` 不含）；
Views 用 `sp` 单位与 `android:textSize`（**不要**用 `dp` 写字号）。

- **承载文字的容器必须能增高。** 高度用 `intrinsic`（不给约束）或 `bounded >= n`，
  **不得** `equalToConstant`。
- **行数策略要显式。** `numberOfLines = 0`（不限行）配合 `lineBreakMode = .byWordWrapping`；
  定了行数上限的必须同时定截断行为。
- **不允许反向缩小字号去迁就固定高度。** 也**不允许**因为「字号大了会溢出」就把
  `adjustsFontForContentSizeCategory` 关掉（那等于放弃可访问性）。

### 3.2 `sp` / `dp` 的分工（Android 与 iOS 对齐理解）

| 单位 | 是否随用户字号缩放 | 用于 |
|---|---|---|
| `sp` | **是** | 字号 |
| `dp` / `pt` | 否 | 尺寸、间距、圆角、描边 |

iOS 没有 `sp` 的对应概念 —— `UIFontMetrics` 就是它的 `sp` 通道。

### 3.3 Large Content Viewer 与最小可变行高

对**不适合**随字号增大的控件（如导航栏图标），用 `showsLargeContentViewer`
与 `UILargeContentViewerInteraction` 提供放大的替代视图，而不是把图标做大。

## 4. 长文本与本地化

### 4.1 两种失效

| 失效 | 成因 | 修法 |
|---|---|---|
| 截断（`…`） | 宽度写死 / 压缩阻力不足 | 去掉定宽约束、设 `required` 压缩阻力、`numberOfLines = 0` |
| 溢出容器 | 高度写死 / 未允许增高 | 高度改 `intrinsic` 或 `>=`；父容器允许增高 |

### 4.2 长度预算

不同语言的同一句话长度差异可达 30%+（德语、俄语、芬兰语显著长于英语；中文、日文较短）。
**必须用「最长目标语言」而不是设计稿的英文去验算。** 验证时至少替换一处最长的按钮文案。

### 4.3 验证要求

- 至少一种比设计稿文案长 40% 的文本，在最小支持宽度下不截断、不溢出；
- 按钮文案变长时，按钮宽度按 `pinned` / `bounded` 增长，而非文字溢出按钮边界；
- 中文与英文各验一次（换行点不同）。

## 5. 触控下限（44pt）

- **44×44pt 是硬下限**，用 `>= 44` 表达，**不是** `== 44`。
- 视觉元素小于 44 时，用一个**更大的透明点击区**包住它，而不是把视觉元素强行做大：

```objc
// 图标视觉 24×24，点击区 44×44
[iconView.widthAnchor constraintEqualToConstant:24];
[iconView.heightAnchor constraintEqualToConstant:24];
[iconButton.widthAnchor constraintGreaterThanOrEqualToConstant:44];
[iconButton.heightAnchor constraintGreaterThanOrEqualToConstant:44];
[iconView.centerXAnchor constraintEqualToAnchor:iconButton.centerXAnchor];
[iconView.centerYAnchor constraintEqualToAnchor:iconButton.centerYAnchor];
```

- Android 对应 `48dp`。iOS 是 `44pt`。**平台硬下限不随设计稿变**（见
  [sizing-and-positioning.md §2.2](sizing-and-positioning.md)）。

## 6. 比例与图片（`aspect-ratio` / `proportional` / `contentMode`）

### 6.1 图片三件套

给图片定尺寸时必须同时说清三件事，缺一即会在某些尺寸下失真：

1. **比例**：`aspect-ratio` 约束（`width = height × ratio`），或让 `intrinsicContentSize` 提供；
2. **填充模式**：`contentMode`。`scaleAspectFill` 会裁剪，`scaleAspectFit` 会留边；
3. **裁剪语义**：`clipsToBounds = YES`，否则 fill 模式下内容会溢出 frame。

```objc
_imageView.contentMode = UIViewContentModeScaleAspectFill;
_imageView.clipsToBounds = YES;
// 不能用固定 frame 掩盖比例问题：即使当前资源的比例恰好合适
[_imageView.widthAnchor constraintEqualToAnchor:_imageView.heightAnchor multiplier:16.0/9.0];
```

**「用固定 frame 掩盖比例问题」是最常见的隐藏缺陷**：当前这张图的比例恰好合适，
换一张图（不同比例的分辨率版本、动态替换的运营图）就拉伸变形。

### 6.2 `proportional` 的合法用途

只有**确实**随父容器成比例的量才用它，并且必须给理由：

- 背景装饰区高度 = 父容器高度 × `0.155`（视觉上就该占固定比例）；
- 进度填充宽度 = 轨道宽度 × 进度值（语义上就是比例）；
- 全屏引导图的媒体区高度 = 窗口高度 × `0.376`（设计意图如此）。

**不合法**：卡片宽度 = 父宽 × `0.82`（真正的意图是「左右各留 35pt」，见
[sizing-and-positioning.md §2.1](sizing-and-positioning.md)）。

## 7. 冲突约束与 Ambiguous Layout

### 7.1 三类问题

| 问题 | 症状 | 判据 |
|---|---|---|
| **冲突约束** | 控制台 `Unable to simultaneously satisfy constraints`；某条被打破 | 出现即 fail，不允许「能跑就行」 |
| **Ambiguous Layout** | 约束不足以唯一确定 frame；不同 iOS 版本结果不一致 | `hasAmbiguousLayout == true` |
| **死约束** | 约束存在但被其他约束完全决定，永远不生效 | 静态可查：同一轴既有 `==` 又有 `==` 到不同常量 |

### 7.2 运行期检查

```objc
// 调试期断言：任何一个视图有歧义布局就停
#if DEBUG
- (void)assertNoAmbiguityInView:(UIView *)view {
    NSAssert(!view.hasAmbiguousLayout, @"Ambiguous layout: %@", view);
    for (UIView *sub in view.subviews) { [self assertNoAmbiguityInView:sub]; }
}
#endif
```

Xcode 的 Debug View Hierarchy 里也可以直接看「Ambiguous Layout」标记。
**这两项属于交付前必须实际跑一次的验证**（见 §9）。

### 7.3 静态可查的形态

以下形态在写码阶段就能静态判死，不必等运行期：

- 同一视图同一轴同时存在 `constraintEqualToConstant: 220` 与 `constraintEqualToAnchor:parent.widthAnchor`；
- 同一视图同时被 `isActive = YES` 的两条 `width ==` 约束钉住为不同值；
- 声明为 `intrinsic` 的关系，源码里却出现了该轴的 `constraintEqualToConstant:`；
- 声明为 `bounded` 的关系，源码里只有 `equalToConstant` 而没有任何 `greaterThanOrEqual` / `lessThanOrEqual`。

后两条由 `scripts/check_layout_proportions.py --source` 在门 1 核对（见 SKILL.md 的门 0 / 门 1）。

## 8. 保真底线：自适应 ≠ 放弃设计稿

新契约的风险方向与旧契约相反：旧契约怕「不还原」，新契约怕「自适应到不像设计稿」。
所以必须同时守一条底线：

1. **设计稿在它自己的宽度档上仍然是最强参考。** 所有闭合方式的选择合起来，
   必须能在设计稿宽度上复现设计稿的排版 —— 位置、尺寸、间距、层级都接近。
2. **换档后允许重排，但关系不得改变。** 元素的主次、分组、对齐方式在重排后要保持；
   不能出现「手机上卡片横排、平板上卡片被拉成整屏宽」这种关系改变。
3. **无法接近设计稿时显式记录。** 若某元素在任意宽度档下都无法接近，属于待确认项，
   写进计划的 `ambiguousLiterals` / `unsupported`，不要静默放过。
4. **不做「看起来更漂亮」的擅自优化。** 单列内容在平板上居中留白是**正确**的，
   把它改成双列是**重新设计**；只有在 `xx-iPad` 双稿存在时才照 iPad 稿取值。

## 9. 验证清单（交付前必须实际执行）

以下每项都要有证据（截图 / 日志 / 几何转储），不能只声明「已考虑」：

| # | 验证项 | 判据 |
|---|---|---|
| 1 | 是否使用了 `intrinsicContentSize` | 文本/按钮类元素源码里没有该轴的定值约束 |
| 2 | 是否存在必要的 `minimum` / `maximum` 约束 | 声明 `bounded` 的元素有 `>=` / `<=` 原语 |
| 3 | 是否存在冲突约束或 Ambiguous Layout | 控制台无冲突告警；`hasAmbiguousLayout` 全 false |
| 4 | 动态字体能否撑开 | 系统字号调到最大档，文本不被截断、按钮不压扁 |
| 5 | 长文本是否被压缩或截断 | 最长目标语言 + 40% 增量文案，最小宽度下不溢出 |
| 6 | 横竖屏与分屏是否可用 | 旋转、Slide Over、分屏 1/3 下布局成立 |
| 7 | 触控区域是否至少 44pt | 每个可点击元素实测 ≥ 44×44pt（含透明扩展区） |
| 8 | 是否尊重 safe area 与 readable width | 内容不被刘海/灵动岛/手势条遮挡；宽屏有可读宽度约束 |
| 9 | 优先级是否表达正确的压缩与扩张顺序 | 有并列可变文本处均显式设置了 hugging / compression |
| 10 | 是否在设计稿宽度档上复现了设计稿 | 设计稿宽度下的几何与设计稿 `bounds` 对照（见 `最终页面分析表.md`） |

第 4、5、6 项属于运行期验证；第 1、2、3、7、9 项可由 `check_layout_proportions.py --source`
静态核对 + 人工抽查；第 8、10 项靠 `最终页面分析表.md` 采样自核。

## 10. 计划字段（`layoutProportions` 的收敛条件）

逐类必填，缺即由 `check_layout_proportions.py --plan-only` 判 fail：

| `kind` | 必填 | 说明 |
|---|---|---|
| `fixed` | `value` + `why` | `why` 必须是「固定性本身是设计意图」，不能是「设计稿就这么写的」 |
| `intrinsic` | `why` | 说清为什么这个量由内容决定（文本、按钮、多语言、动态字体） |
| `bounded` | `min` 或 `max` 至少一个 | 两者都给时 `min <= max` |
| `pinned` | `edges`（或 `edge`） | 不得带比例系数 |
| `proportional` | `ratio` + `of` + 理由 | 基准是直接父视图 |
| `equal` | `with` 或 `to` | 声明等宽/等高对象 |
| `centered` | — | 不得带比例系数 |
| `aspect-ratio` | 正数 `ratio` | 图片、媒体、视觉卡片 |

设计稿的原始 `width`/`height` 记录在 `reference/dds-schema.json`，
**不自动等于生产约束** —— 它只是选择闭合方式时的参考事实。
