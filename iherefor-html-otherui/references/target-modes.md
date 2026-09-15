# 输出模式边界

| 模式 | 语言 | UI 技术 | 首选布局策略 | 比例的表达方式 |
|---|---|---|---|---|
| `ios-swiftui` | Swift | SwiftUI | 声明式容器；重叠区域使用 ZStack/overlay | `GeometryReader` 归一化、`.containerRelativeFrame` |
| `ios-uikit-swift` | Swift | UIKit | Auto Layout + 必要的画布 frame | `NSLayoutConstraint` 的 `multiplier`、`UILayoutGuide` |
| `ios-uikit-objective-c` | Objective-C | UIKit | Auto Layout + 必要的画布 frame | 同上 |
| `android-compose-kotlin` | Kotlin | Jetpack Compose | Box/Row/Column；复杂叠层使用 Box | `BoxWithConstraints` 的 `maxWidth/maxHeight` 派生比例、`weight` |
| `android-views-kotlin` | Kotlin | Android Views/XML | ConstraintLayout/FrameLayout；必要时自定义 View | `layout_constraintGuide_percent`、`bias`、`layout_weight` |
| `android-views-java` | Java | Android Views/XML | ConstraintLayout/FrameLayout；必要时自定义 View | 同上 |

SwiftUI、UIKit Swift 和 UIKit Objective-C 是三个独立输出目标；不能因为它们都在 iOS 上就共享未经验证的生成源码。Android 同理，Compose 与传统 Views/XML 必须分别验证。

所有模式都必须：

- 保留页面真实叠层关系；
- **约束策略不是等比缩放：尺寸固定、位置相对父视图**（见 [sizing-and-positioning.md](sizing-and-positioning.md) 与 [artifact-contract.md](artifact-contract.md#布局关系与控件尺寸的约束口径强制)）：控件尺寸（按钮、文字、图标）与字号、圆角、描边宽度、最小点击区一律保持设计值不缩放；位置基准是**直接父视图**（父容器为整屏画布时即屏幕内容区），不得写成「探针设备上换算出来的绝对值」；确属成比例变化的关系才用比例，基准是父视图而非整页。禁止用比例缩放字号与最小点击区——那会让 44pt 的点击区在小屏上缩成 40pt；禁止用比例系数表达固定边距（16pt 不是 `width * 0.0397`）；
- 将资源映射为工程内稳定引用；
- 对字体替代、渐变、阴影、SVG、滤镜、动画和 JS 行为记录支持状态；
- 提供关键区域的 accessibility identifier；
- 通过目标平台编译和截图验证。
- 在运行时使用平台尺寸 API 获取真实窗口/根容器尺寸，保存 `runtime-device.json`；禁止使用设备型号对应的固定宽高或截图像素直接作为布局尺寸。
- **声明宽度轴**：每个区域必须归入一个 `widthPolicy`（见 [adaptive-layout.md](adaptive-layout.md)），
  并把该模式的预留 hook 写进代码（「接口在、值仍是手机值」）。单列内容拉满宽屏不在枚举内，
  必须由 `full-bleed` 显式声明。

## 每模式的自适应原语

三轴分工见 [adaptive-layout.md](adaptive-layout.md)：尺寸轴与位置轴保证「换设备不崩」，
宽度轴保证「换设备不难看」。下表是宽度轴在各模式上的落点 —— **同一个视觉目标，
不同技术栈的表达方式不同，不得互相照抄**。

| 模式 | 判断宽度档 | 内容列封顶 | 列数切换 | 结构升级 | 预留 hook |
|---|---|---|---|---|---|
| `ios-swiftui` | `@Environment(\.horizontalSizeClass)` | `.frame(maxWidth:)`、`.containerRelativeFrame` | `Grid` + 自适应列 | `NavigationSplitView`、`ViewThatFits` | `LayoutMetrics` 类型（`maxContentWidth` / `columns(for:)`）+ 内容区根视图上的 `.frame(maxWidth:)` |
| `ios-uikit-swift` | `traitCollection.horizontalSizeClass`、`registerForTraitChanges` | `readableContentGuide`、`maxContentWidth` 约束 | `UICollectionViewCompositionalLayout` + `NSCollectionLayoutEnvironment` | `UISplitViewController`、`popoverPresentationController` | `registerForTraitChanges` 分支点 + `readableContentGuide` 基准 + 一条手机档不生效的 `maxContentWidth` 约束 |
| `ios-uikit-objective-c` | `traitCollection.horizontalSizeClass`、`traitCollectionDidChange:` | 同上 | 同上 | 同上 | 同上（ObjC 写法） |
| `android-compose-kotlin` | `currentWindowAdaptiveInfo()` / `WindowSizeClass` | `Modifier.widthIn(max = …)`、`contentMaxWidth()` | `GridCells.Adaptive` | `NavigationSuiteScaffold`、`ListDetailPaneScaffold` | 根部提供 `WindowSizeClass` + `Modifier.contentMaxWidth()` 扩展 + 用 `Adaptive` 而非 `Fixed` |
| `android-views-kotlin` | `WindowSizeClass`（`androidx.window`） | `layout_constraintWidth_max="@dimen/content_max_width"` | `GridLayoutManager` 的 `spanCount` | `NavigationRailView`、`SlidingPaneLayout` | `values/dimens.xml` 的 `0dp` + `values-sw600dp/dimens.xml` 的 `600dp`，约束**已接上** |
| `android-views-java` | 同上 | 同上 | 同上 | 同上 | 同上 |

Android 最省事的一条原语是 ConstraintLayout 的
`layout_constraintWidth_percent="1"` + `layout_constraintWidth_max="@dimen/content_max_width"`：
一个约束同时表达「手机拉满、平板封顶」。`values/dimens.xml` 给 `0dp`（不限）、
`values-sw600dp/dimens.xml` 给 `600dp`，约束现在就接上，填值即生效。

**两个模式之间唯一可以共享的是「视觉目标」，不是「实现形状」。** 例如 iOS 的
`readableContentGuide` 与 Android 的 `content_max_width` 都在表达「内容列封顶并居中」，
但把其中一个的值直接搬到另一个平台、或让 UIKit 与 SwiftUI 共享同一份布局代码，
都不构成验证 —— 三个 iOS 目标、三个 Android 目标各自独立编译与截图。

## 系统栏/安全区实现规则

| 平台 | 必须确认 | 常见错误 |
|---|---|---|
| iOS UIKit / SwiftUI | HTML 是否 underlap 状态栏；`edgesForExtendedLayout`、`safeAreaInsets`、状态栏样式、home indicator | 用 safe-area 顶部约束包住整页，导致页面整体下移 |
| Android Compose | `enableEdgeToEdge`、`WindowInsets.statusBars`/`navigationBars`、内容与背景是否分离 | 直接对根 Column 加默认 padding，重复计算 inset |
| Android Views/XML | `WindowCompat.setDecorFitsSystemWindows`、`WindowInsetsCompat`、状态栏/导航栏颜色 | 同时使用 decor fitting 和手工 padding，页面整体下移 |

背景层应按 HTML 事实决定是否延伸到系统栏；文字、按钮等前景层单独应用安全区 inset。该决定必须写入实现计划的 `systemBars` 字段，并在实际截图中验证。
