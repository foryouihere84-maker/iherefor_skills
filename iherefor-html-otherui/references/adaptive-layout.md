# 平板与宽屏自适应规范（强制）

> 本文是「设计稿只有一个手机尺寸，目标 App 还要跑在平板、大屏、分屏、自由窗口上」这条链路的
> 权威规范。与 [sizing-and-positioning.md](sizing-and-positioning.md) 配套阅读：
> 那篇规定**尺寸轴**与**位置轴**，本文规定**宽度轴**。
> 三者管辖范围不重叠，但交界处有优先级：**父视图变宽之后怎么重排，以本文为准。**

## 0. 一句话

**布局是窗口宽度的连续函数，不是「手机一套、平板一套」的两张快照。**

| 轴 | 谁决定 | 表现形式 | 出处 |
|---|---|---|---|
| **尺寸** | 设计稿（或父子约束闭合） | `fixed` 设计值 / `pinned` 约束闭合 / `intrinsic` | [sizing-and-positioning.md](sizing-and-positioning.md) |
| **位置** | 父子视图层级 | 相对**直接父视图**的约束 | 同上 |
| **宽度** | **窗口当前宽度档** | **`widthPolicy`：内容列怎么收敛** | **本文** |

前两轴保证「换设备不崩」；宽度轴保证「换设备**不难看**」。缺宽度轴时，前两轴在 1024pt 上
会给出一个**错的**结果（见 §4 第 2 条），而不是「没有结果」。

## 1. 为什么不能只做两个断点

「手机 / 平板」两个断点是最常见的错解，因为**「平板」根本不是一个尺寸**：

- iPad 全屏竖 1024×1366pt、横 1366×1024pt；
- iPad 分屏 1/2、1/3 与 Slide Over 时宽度回落到 ~320pt —— 与手机同档；
- Stage Manager 与 iPadOS 26 的自由窗口下，宽度在 **320~1366pt 之间连续可变**；
- Android 侧同理：折叠屏展开/折叠、自由窗口、桌面模式，`sw600dp` 只是其中一档。

所以正确的心智模型是「**宽度档 + 连续重排**」：按宽度档做**决策**，但布局本身必须对
档位之间的任意宽度都不崩。两个断点的写法在分屏和自由窗口下必然失效。

Android 还有一条硬约束：**Android 15（API 35）起，`sw >= 600dp` 的设备上系统会忽略
方向锁定并强制应用可调整大小**；Android 16 在平板上完全忽略。所以锁方向在平板上不是
「保险」，而是直接变成信箱模式或布局崩塌。

## 2. 宽度档（`windowSamples`）

| 档 | 宽度 | iOS 尺寸类别 | Android WindowSizeClass | 典型场景 |
|---|---|---|---|---|
| `compact` | < 600pt/dp | `.compact` | `COMPACT` | 手机竖、iPad 分屏 1/3、Slide Over |
| `medium` | 600–839dp | `.regular` | `MEDIUM` | iPad 竖全屏 1024、折叠屏展开、手机横屏 |
| `expanded` | ≥ 840dp | `.regular` | `EXPANDED` | iPad 横 1366、Android 平板横屏 |

**注意 iOS 的 `medium` 与 `expanded` 都是 `.regular`** —— 这是「不能按尺寸类别直接当宽度档用」
的原因：`horizontalSizeClass == .regular` 在 1024 与 1366 上都成立，但内容列封顶策略在两者上
可能不同。尺寸类别是**决策入口**，不是宽度本身。

计划里**必须声明至少四个采样**：

| 采样 id | 档 | 为什么必须有 |
|---|---|---|
| `phone-compact` | `compact` | 设计稿探针设备，像素基准所在 |
| `tablet-regular-portrait` | `medium` | 最常见的平板姿态 |
| `tablet-regular-landscape` | `expanded` | 最宽的一档，`maxContentWidth` 是否生效在这里暴露 |
| `phone-regular-landscape` | `medium` | 手机横屏；漏掉它就会把「medium 一定来自平板」写成假设 |

采样是**验证的取样点**，不是布局的分支条件。实现里不得出现
`if device == "iPad"` 这类判断，也不得把采样 id 写进生产代码。

## 3. 宽度轴：`widthPolicy` 六档

`widthPolicy` 回答的是唯一一个问题：**父视图变宽时，这个区域的内容怎么收敛？**

| policy | 含义 | 何时用 | 反例 |
|---|---|---|---|
| `full-bleed` | 内容铺满窗口宽度 | 背景、hero 图、分割线、整宽色块 | 表单、正文 |
| `max-content-width` | 内容列封顶 `maxContentWidth`，水平居中 | 单列表单 / 详情 / 设置页 | — |
| `centered-column` | 同上限，但用系统阅读宽度引导线（iOS `readableContentGuide` 等） | 长文本、条款 | — |
| `grid` | 列数按宽度档切换 | 卡片列表、图库、宫格 | 固定单列 |
| `pane` | 单栏在宽档升级为双栏 / 侧栏 | 列表-详情、主从结构 | — |
| `stacked` | 保持单列且不拉宽，按内容固有宽度居中 | 需要逐字阅读的短内容 | 拉满 |

**`stretch-full-width` 不在枚举里，而且它是本规范要拦的头号问题。** 单列内容拉满 1024pt
是平板适配里最典型的缺陷：它不会让任何断言失败（元素确实没越界、尺寸也没变），
但阅读节奏彻底坏了。所以「拉满」必须由 `full-bleed` 显式声明，不能是默认行为。

`maxContentWidth` 是**设计常量**，不随窗口缩放。常见取值：iOS 600–700pt、
Android `sw600dp` 惯用 600dp。声明时必须同时给 `of`（基准父视图）与 `reason`。

## 4. 宽度轴与另外两轴的交界（三条硬规则）

### 4.1 宽度轴只改「容器宽度」与「第一层位置」，不改任何尺寸

字号、行高、圆角、描边宽度、阴影、图标与位图资源的点值尺寸、最小点击区
（≥44pt / 48dp）在**全部宽度档上逐字相同**。这与
[sizing-and-positioning.md §2.2](sizing-and-positioning.md#22-哪些量永远不缩放) 是同一条约束，
只是现在多了一个更容易踩的场景：平板。

**「平板字大一点更好看」是错的。** 那会让同一页面在 iPhone 与 iPad 上出现两套排版，
而设计稿只有一套。

**唯一的合法例外：多设备稿的「照稿分档」。** 当同一设计在 Lanhu 里同时存在
`xx` 与 `xx-iPad` 两份稿、且 iPad 稿确实给出了**不同的尺寸参数**（例如按钮框 22 → 28 高、
而字号不变）时，iPad 档照 iPad 稿还原尺寸是**合规的分档**，不是「把手机稿等比放大」。
但这一档必须显式声明，才能和「整页等比放大」区分开 —— 位置在
`adaptiveLayout.sizeVariants[]`：

```json
"adaptiveLayout": {
  "sizeVariants": [
    {
      "region": "continueCta",
      "basis": "目的 + 目的-iPad 双稿（iPad 稿 image_id=…）",
      "values": {
        "phone-compact":           { "width": 68,  "height": 22 },
        "tablet-regular-portrait": { "width": 141, "height": 28 }
      },
      "why": "iPad 稿给出该档更大的按钮框；字号仍为设计值、未缩放"
    }
  ]
}
```

三条纪律：

1. **`basis` 与 `why` 都是必填**。没有这两项，`audit_adaptive.py` 的 `sizeInvariance`
   不把该元素算进分档白名单 —— 仍按「尺寸随窗口变」判 `size-not-invariant`。
2. **只有「尺寸真的分档」才需声明**；字号、圆角、描边、最小点击区**永远不参与分档**，
   它们在任何设备的稿里都该相等。分档的是「容器/控件的宽高」这类几何尺寸。
3. **`sizeInvariance` 不是被放宽，是被收窄到「未声明即违规」。** 声明过的分档放行，
   没声明的尺寸变化依旧拦下 —— 这条改动是为「双稿照稿还原」开合法的门，不是为
   「平板上把东西放大点」开的口子。

### 4.2 `adaptiveLayout` 存在时，第一层位置比例规则只在 `compact` 档生效

[sizing-and-positioning.md §3.1.1](sizing-and-positioning.md#311-第一层子视图位置按页面比例重排设备尺寸--设计稿尺寸时的适配核心)
规定「第一层子视图的位置按页面比例重排」，这条规则在 `393×852 → 402×874` 上是对的
（两轴比例差 2.3%，位置确实该跟着动）。但它**只在 compact 档成立**。

推到 1024pt 就会出事：位置按比例 ×2.6、而尺寸按契约 ×1，于是

- 卡片左起从 33pt 变成 86pt，宽度仍是 327pt —— 右侧空出 611pt；
- 卡片间距从设计稿的 13pt 被拉成 285pt；
- 整个页面的视觉重心落在左侧 40%，右边一片空白。

所以：**`adaptiveLayout` 存在时，regular / medium / expanded 档下第一层位置改由
`widthPolicy` 重排**（`max-content-width` 就是把它们收进居中的内容列里）。
`compact` 档维持原规则不变。

### 4.3 安全区与系统 UI 参与位置求解，不参与尺寸；平板的系统区域与手机不同

iPad 没有刘海与灵动岛，但有 home indicator、Stage Manager 的窗口控制条、
多任务下的窗口圆角与阴影。这些**只改变可用内容区的边界与原点**，
`fixed` 尺寸不受影响；`pinned` 关系应贴**安全区或内容区**而不是物理屏幕边缘。

「窗口 ≠ 屏幕」在平板上从一句提醒变成硬约束：分屏与自由窗口下，
`UIScreen.main.bounds` / `DisplayMetrics.widthPixels` 返回的是**整块屏**，不是你的窗口。
用它们做布局基准，在分屏下会得到错的原点与错的可用宽度。

| 平台 | 必须用 | 禁止用 |
|---|---|---|
| iOS UIKit | `view.bounds`、`view.window.windowScene` | `UIScreen.main.bounds` / `nativeBounds` |
| SwiftUI | `GeometryReader`、`@Environment(\.horizontalSizeClass)` | 屏幕尺寸推断 |
| Compose | `BoxWithConstraints`、`currentWindowAdaptiveInfo()` | `LocalConfiguration.screenWidthDp` 当窗口宽度 |
| Views/XML | `WindowMetricsCalculator`、`WindowSizeClass` | `DisplayMetrics.widthPixels` |

### 4.4 「iPhone 竖屏 + iPad 全方向」是合法组合，不算方向锁

有一种常见且正当的声明方式：iPhone 只支持竖屏，iPad 放开全方向。

```xml
<key>UISupportedInterfaceOrientations</key>
<array><string>UIInterfaceOrientationPortrait</string></array>
<key>UISupportedInterfaceOrientations~ipad</key>
<array>
  <string>UIInterfaceOrientationPortrait</string>
  <string>UIInterfaceOrientationLandscapeLeft</string>
  <string>UIInterfaceOrientationLandscapeRight</string>
</array>
```

它**不构成方向锁** —— iPad 侧仍然能拿到全部宽度档，宽度轴是可验证的。
判据是「**通用**方向集锁死单一方向**且没有** `~ipad` 方向集」：
那种情况下 regular 宽度档在**所有**设备上都拿不到。

所以「见到 `Portrait` 就报方向锁」是误报，而误报比漏报更伤 —— 它会训练出
「看到告警就忽略」的习惯，而这条告警本该是平板适配的主要防线之一。


## 5. 各模式的自适应原语

| 模式 | 判断宽度档 | 内容列封顶 | 列数切换 | 结构升级 |
|---|---|---|---|---|
| `ios-swiftui` | `@Environment(\.horizontalSizeClass)` | `.frame(maxWidth:)`、`.containerRelativeFrame` | `Grid` + 自适应列 | `NavigationSplitView`、`ViewThatFits` |
| `ios-uikit-swift` | `traitCollection.horizontalSizeClass`、`registerForTraitChanges` | `readableContentGuide`、`maxContentWidth` 约束 | `UICollectionViewCompositionalLayout` + `NSCollectionLayoutEnvironment` | `UISplitViewController`、`popoverPresentationController` |
| `ios-uikit-objective-c` | 同上（ObjC 写法） | 同上 | 同上 | 同上 |
| `android-compose-kotlin` | `currentWindowAdaptiveInfo()` / `WindowSizeClass` | `Modifier.widthIn(max = …)`、`contentMaxWidth()` | `GridCells.Adaptive` | `NavigationSuiteScaffold`、`ListDetailPaneScaffold` |
| `android-views-kotlin` | `WindowSizeClass`（`androidx.window`） | `layout_constraintWidth_max="@dimen/content_max_width"` | `GridLayoutManager` 的 `spanCount` | `NavigationRailView`、`SlidingPaneLayout` |
| `android-views-java` | 同上 | 同上 | 同上 | 同上 |

**Android 最省事的一条原语**是 ConstraintLayout 的
`layout_constraintWidth_percent="1"` + `layout_constraintWidth_max="@dimen/content_max_width"`：
一个约束同时表达「手机拉满、平板封顶」。配合资源限定符分档给值：

| 资源目录 | `content_max_width` | 效果 |
|---|---|---|
| `values/dimens.xml` | `0dp`（不限） | 手机上等于没有上限 |
| `values-sw600dp/dimens.xml` | `600dp` | 平板上封顶并居中 |

约束**现在就接上**，填值即生效 —— 这是「预留」最干净的形态（见 §6）。

## 6. 「预留」的契约（可核）

**预留 = 接口在、值仍是手机值。不是写第二套布局。**

这条区分很重要：写两套布局（一套在手机档不生效）会污染像素 diff、在门 1 里变成死代码，
而且它假设了「宽度只有两档」。正确的预留是**把结构位置留出来**，手机档下它退化为
与现在完全一致的布局。

每个模式**必须**留下下列 hook，且它们在手机档下不得改变任何视觉结果：

| 模式 | 必须预留 |
|---|---|
| `ios-swiftui` | 一个 `LayoutMetrics` 类型（`maxContentWidth`、`columns(for:)`）；内容区根视图上的 `.frame(maxWidth: LayoutMetrics.maxContentWidth)`；宽度档读取点（`horizontalSizeClass` 或 `containerRelativeFrame`） |
| `ios-uikit-swift` / `objective-c` | `traitCollectionDidChange` / `registerForTraitChanges` 的分支点（当前只需处理 compact，regular 分支留空并注释）；内容容器以 `readableContentGuide` 为基准；一条 `maxContentWidth` 的 `lessThanOrEqualTo` 约束（手机档取一个永不生效的极大值） |
| `android-compose-kotlin` | 根部提供 `WindowSizeClass`（`currentWindowAdaptiveInfo()`）；一个 `Modifier.contentMaxWidth()` 扩展；网格用 `GridCells.Adaptive` 而非 `GridCells.Fixed` |
| `android-views-kotlin` / `java` | `values/dimens.xml` 的 `content_max_width = 0dp` 与 `values-sw600dp/dimens.xml` 的 `= 600dp`；布局里**已接上** `layout_constraintWidth_max="@dimen/content_max_width"`；`NavigationRailView` 与 `BottomNavigationView` 的容器就位 |

**判定「预留了没有」的判据是可核的**：计划声明了 `max-content-width` 的每个区域，
源码里必须存在对应的封顶原语（约束 / modifier / dimens 引用）；计划声明了 `grid`
的区域，源码里不得出现固定 `GridCells.Fixed` / 写死的 `spanCount`。这两条由
`scripts/check_adaptive_layout.py` 在门 1 静态核对。

## 7. 验证：`adaptiveAudit` 与「为什么不做像素 diff」

### 7.1 平板这一关**不能**做像素比对

Lanhu 只提供一份设计稿，`reference/reference.png` 是**某一台设备**的像素基准。
拿它去比 iPad 截图，等于拿两个不同画布比对 —— `scripts/audit_alignment.py` 的
`domVsReference` 会直接判「基准不可信」，因为基准的渲染 viewport 与采集事实表时的
viewport 是同一套、而 iPad 截图不是。这不是「容差不够大」，是**证据类型不匹配**。

所以 `adaptiveAudit` 是**几何契约审计**：只断言几何关系，不比对像素。这与本 skill 的
优化方向（把问题从「需要截图诊断」降级为「静态告警并给出位置」）是同一个思路。

### 7.2 一半静态、一半运行期

**静态**（并入门 1，秒级，不编译）—— `scripts/check_adaptive_layout.py`：

- 禁止 `UIScreen.main.bounds` / `DisplayMetrics.widthPixels` 参与布局；
- 禁止方向锁定与 `UIRequiresFullScreen`；
- 计划声明了 `max-content-width` 的区域，源码里必须有对应封顶原语；
- 计划声明了 `grid` 的区域，不得出现固定列数；
- 源码里不得存在把设计常量乘屏幕系数的表达式（`* 1.0229`、`/ 393 * screenW` 之类）；
- `TARGETED_DEVICE_FAMILY` / `sw600dp` 资源目录的存在性。

**运行期**（多设备几何转储）—— `scripts/audit_adaptive.py`：

| 检查 | 断言 | 为什么它值得单独存在 |
|---|---|---|
| `sampleCoverage` | 计划声明的必需采样都有几何证据 | 缺采样时其余检查会「全绿」，那是假绿 |
| `sizeInvariance` | 同一 `fixed` 元素在全部采样上点值**逐字相等** | **把「尺寸不缩放」从文档口号变成可执行断言** —— 这是本规范最有价值的一条 |
| `insetPreservation` | 设计常量内边距在各采样上相等 | 拦「平板上边距被撑大」 |
| `noOverflow` | 元素不越出窗口 bounds | 拦分屏与自由窗口下的溢出 |
| `maxContentWidth` | 声明封顶的区域宽度 ≤ 声明值 + 容差，且水平居中 | 拦「声明了封顶但没生效」与「封顶了但没居中」 |
| `touchTarget` | 可交互元素 ≥ 44pt（iOS）/ 48dp（Android） | 拦「平板上点击区被放大/缩小」 |
| `noLetterbox` | 无黑边、非兼容缩放模式 | 拦「声称支持平板但以 iPhone 兼容模式运行」 |
| `continuity` | 多宽度采样下同 `fixed` 元素尺寸无变化、无未声明重叠 | 拦「只在两个断点上对，中间宽度崩」 |

### 7.3 与交付闸门的交叉

`adaptiveLayout` 声明的计划，其 `delivery-gate.status` **必须**包含 `adaptiveAudit`，
且 `scripts/validate_run.py` 会交叉核对：`diff/adaptive-audit.json` 判 fail 时
`adaptiveAudit` 不得记 `pass`。这与「对齐审计 needs-review 却 visualDiff=pass」是同一类
自相矛盾。未声明 `adaptiveLayout` 的计划不受这条约束（但会在计划里留下告警）。

## 8. 反例清单（看起来对，其实错）

| 反例 | 为什么错 |
|---|---|
| 整页等比放大到平板 | 44pt 点击区变 115pt、17pt 字号变 44pt；每个尺寸都错，而它「处处对齐」 |
| 单列内容拉满 1024pt | 元素没越界、尺寸没变，断言全绿但阅读节奏彻底坏了 |
| `if device == "iPad"` / 按设备型号分支 | 分屏、Slide Over、自由窗口下型号不变而宽度变了 |
| 锁竖屏当作「只支持手机」的保险 | Android 15+ 在 sw≥600dp 上忽略方向锁；iOS 上会变成信箱模式 |
| 用 `UIScreen.main.bounds` 当布局基准 | 分屏与自由窗口下它返回整块屏，不是窗口 |
| 只声明两个断点（手机 / 平板） | 断点之间的连续宽度无定义，分屏必崩 |
| 平板上把字号调大「更好看」 | 设计稿只有一套排版；这是把适配做成了重新设计 |
| 为了 iPad 单独写一套布局文件，手机档下不生效 | 死代码会污染 diff，且在门 1 里被判成未声明的分支 |
| 用 `TARGETED_DEVICE_FAMILY = 1,2` 就算支持了 iPad | 只声明了设备族，没有任何宽度档决策与方向声明，实际以竖屏或兼容模式运行 |

## 9. 落地检查清单

写实现计划时：

- [ ] 已声明 `adaptiveLayout`，含至少四个 `windowSamples`（`phone-compact` /
      `tablet-regular-portrait` / `tablet-regular-landscape` / `phone-regular-landscape`）；
- [ ] 每个可见区域都归入一个 `widthPolicy`，且**没有一个区域是「默认拉满」**；
- [ ] 声明 `max-content-width` / `centered-column` 的区域给了 `maxContentWidth.value` 与 `reason`；
- [ ] 声明 `grid` 的区域给了 `columnCount` 的 `compact` / `medium` / `expanded` 三档，且单调不减；
- [ ] `forbiddenAdaptations` 非空，至少含 `uniform-scale` / `stretch-full-width` / `font-scale`；
- [ ] 第一层位置比例规则已显式限定在 `compact` 档（§4.2）。

写代码后：

- [ ] 源码中不存在 `UIScreen.main.bounds` / `DisplayMetrics.widthPixels` 参与布局；
- [ ] 不存在方向锁定与 `UIRequiresFullScreen`；
- [ ] 声明 `max-content-width` 的区域，源码里有对应封顶原语；
- [ ] 声明 `grid` 的区域没有固定列数；
- [ ] 六模式各自的预留 hook 已就位（§6 表），且手机档视觉结果未变；
- [ ] 字号、圆角、描边、最小点击区在全部宽度档上数值一致。

交付前：

- [ ] 跑过 `scripts/check_adaptive_layout.py`（门 1，`violations == 0`）；
- [ ] 必需采样都有几何转储，跑过 `scripts/audit_adaptive.py`；
- [ ] `delivery-gate.status.adaptiveAudit` 与 `diff/adaptive-audit.json` 不矛盾。

## 10. 规范条款与实现落点对照

| 规范条款 | 落点 |
|---|---|
| §2 宽度档 | `ui-implementation-plan.json` 的 `adaptiveLayout.windowSamples[]` + `adaptive-targets.json` 的 `samples[]` |
| §3 宽度轴六档 | `adaptiveLayout.regions[].widthPolicy` + `maxContentWidth` |
| §4.1 尺寸不缩放 | `audit_adaptive.py` 的 `sizeInvariance`（复用 `layoutProportions` 的 `kind == "fixed"`） |
| §4.2 第一层比例只在 compact 生效 | `check_adaptive_layout.py` 的计划校验；`layoutProportions` 的 `forced: "first-level"` 需带 `widthClass: "compact"` |
| §4.3 窗口 ≠ 屏幕 | `check_adaptive_layout.py` 的 `screen-as-layout-source` / `display-metrics-as-layout-source` |
| §6 预留 hook 可核 | `check_adaptive_layout.py` 的 `missing-max-content-width` / `fixed-column-count` |
| §7 几何审计 | `diff/adaptive-audit.json`（`audit_adaptive.py` 产出） |
| §7.3 闸门交叉 | `validate_run.py` 的 `check_adaptive_gate` |
