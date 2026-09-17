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

> **垂直（高度）轴不是第四根轴，它是位置轴本来就管的事。** 第一层子视图的纵向位置按
> 「页面高度」比例重排，与宽度档**无关**（见 §4.2）——较短手机 / 横屏下设备高度不足，
> 用「贴边」写死纵向位置会让底部缺失。宽度轴管不到的「高变矮」，交给位置轴的垂直分量处理。

## 0.5 多设备稿：先判断「有没有 xx-iPad 稿」，这决定走哪条路

本文后续的「宽度是连续函数、不要两个断点」（§1）**有一个前提**：设计稿**只有一份**（手机稿），
平板形态要靠宽度轴从那份稿**推导**出来。但 Lanhu 里常出现**成对稿**：`xx` 与 `xx-iPad`。
那一对不是「同一张稿在不同设备」，而是**两套并列的独立参考**——iPad 组的宽、高、字号、
资源、颜色都照 `xx-iPad` 稿自身取值，与 `xx` 稿**没有派生关系**。

所以第一步是分岔，而不是直接套宽度轴：

| 情形 | 判定 | 走哪条路 |
|---|---|---|
| 只有 `xx`（无 iPad 稿） | 设计列表里搜不到 `xx-iPad` | 宽度轴（§1 起的连续推导，`widthPolicy` 让内容在 1024pt 上合理排布） |
| 有 `xx` 与 `xx-iPad` | 同名成对 | **多设备稿**：iPad 档照 `xx-iPad` 稿完整还原，尺寸/字号/资源按稿分档（见下） |

**多设备稿不是宽度轴的例外，而是更具体的输入形态**：宽度轴回答「只有手机稿时 iPad 怎么办」，
多设备稿回答「有 iPad 稿时以哪份为准」。两者不冲突——有了 iPad 稿，就以稿为准，不再靠
宽度轴去猜。

多设备稿的硬规则，一句话：**「xx」和「xx-iPad」按两个独立 page 处理，逐维照各自稿还原，
只在 md5 逐字节相同时才允许共享。** 具体分四维，每一维都有「手机稿值 vs iPad 稿值」要落到
计划里，且几何取值优先来自**各自稿的 `bounds`**（`bounds` 缺失时才是渲染后的 `page-facts`；
不是 design_document 图层坐标，见 [lanhu-input.md](lanhu-input.md)）：

| 维度 | 分档依据 | 校验门 |
|---|---|---|
| 几何宽/高 | `diff_device_variants.py` diff 同名容器，产出 `sizeVariants[]` | `audit_adaptive.py` `sizeInvariance` 白名单 |
| 字号/字重 | 两稿 HTML 的 `font-size`/`font-family` 逐级对比（iPad 稿常更大，如标题 24→30） | 人工 + `resource-policy.json` 声明 |
| 位图资源 | 逐字节 md5 对比两稿同名资源，md5 不同即分档 | 人工 + `resource-policy.json` 声明 |
| 颜色 | 两稿 CSS 的 `background-color`/`color` 逐元素对比（如 CTA 灰→蓝） | 人工 + 计划声明 |

**数据源铁律（本次多轮踩坑的根）**：`design_document` 的图层 `rect` 有负偏移根画板、
rect 是相对父容器的、字号是 scale 还原中间值、文字节点可能缺失——**几何维优先用各自稿的
`bounds`（`dds-schema.json`）取值，`bounds` 缺失时才用「下载渲染后的 page-facts」**，
design_document 只在「父视图归属」上可靠。

历史教训（都写成了门）：① 复用手机稿资源到 iPad 档，得到低清/比例错/颜色错的画面——
需按每稿资源分档（md5 逐字节对比）；② 手动往 pbxproj 加资源时 Object ID 撞既有对象，
资源静默不进 bundle、UI 渲染成 0×0 且编译仍 SUCCEEDED——已由 `check_pbxproj_ids.py` 拦。

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

| 采样 id | 设备平台 | 宽度档 | 为什么必须有 |
|---|---|---|---|
| `phone-compact` | `phone` | `compact` | 设计稿探针设备，像素基准所在 |
| `tablet-regular-portrait` | `tablet` | `medium` | 最常见的平板姿态 |
| `tablet-regular-landscape` | `tablet` | `expanded` | 最宽的一档，`maxContentWidth` 是否生效在这里暴露 |
| `phone-regular-landscape` | `phone` | `medium` | 手机横屏；漏掉它就会把「medium 一定来自平板」写成假设 |

采样是**验证的取样点**，不是布局的分支条件。实现里不得出现
`if device == "iPad"` 这类判断，也不得把采样 id 写进生产代码。

**「设备平台」（phone / tablet）与「宽度档」（compact / medium / expanded）是两根正交的轴。**
宽度档回答「父视图变宽时内容怎么收敛」，由窗口宽度决定；设备平台回答「照哪套稿的尺寸 /
字号」，由设备决定。`sizeInvariance` 的「尺寸不缩放」作用域是**同设备内**——同一台 phone 或
同一台 tablet 的各个宽度档之间尺寸必须逐字相等；跨设备（phone vs tablet）的差异才走
`sizeVariants` 分档（此时有 `xx` 与 `xx-iPad` 两份稿）。声明 `sizeVariants` 时，两个设备平台的
采样都必须有。

**宽度档由「实际窗口宽度」决定，不是随设备型号写死。** 上面表格里的 1024 / 1366 只是
iPad **全屏**的常见值，不是「iPad 的宽度档定义」：iPad 分屏 1/3、Slide Over 会回落到
~320pt（compact），Stage Manager / 自由窗口会在 320~1366 之间连续变化，而 Lanhu 导出的
iPad 稿画布也可能是 810pt 这类**非标值**（实测存在，不是只有 1024 / 1366）。所以 `width`
与 `widthClass` 都照**实际画布宽度**填报，810 宽的 iPad 稿按阈值（600~840）就近归 `medium`，
而不是因为「它是 iPad」就硬套 1024。`check_adaptive_layout.py` 会对「宽度与档位明显越界」的
采样给 warning 提示自查。

> **历史口径待澄清**：本文 §2 阈值表里 `medium` 定义为 600–839、`expanded` ≥ 840，但
> 「iPad 竖全屏 1024」在示例里被标为 `medium`——1024 > 839，按数值本应 `expanded`。
> 这是一个既有的、与数值阈值不一致的口径，牵涉多份示例与评测素材，**尚未收敛**。写计划时
> 优先照**实际宽度数值**归类（810→medium、1366→expanded），遇到 1024 这类边界值，明确标注
> 你把它归到哪一档并说明理由，不要默认「iPad 竖 = medium」。

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

### 4.1 宽度轴改变容器闭合结果，不缩放视觉常量

宽度轴只负责横向收敛。纵向布局不把页面高度当作默认比例基准；优先由 Auto Layout 的垂直约束、
UIStackView、UIScrollView 内容链和 intrinsic height 求解。`y` proportional 仅适用于有明确比例语义的
装饰或媒体区域，并且必须在关系的 `why` 中说明原因。

字号、行高、圆角、描边宽度、阴影、图标与位图资源的点值尺寸、最小点击区
（≥44pt / 48dp）在**同一个平台的各个宽度档之间逐字相同**。这与
[sizing-and-positioning.md §2.2](sizing-and-positioning.md#22-哪些量确实该用-fixed也就是永远不缩放的那一小组) 是同一条约束，
只是现在多了一个更容易踩的场景：平板。

**注意范围**：这一节管的是**视觉常量**（也就是计划里 `kind: fixed` 的那一小组）。
容器、文本、按钮的宽高**不在此列** —— 它们由 `intrinsic` / `bounded` / `pinned` 闭合，
在不同宽度档之间**本来就应该变化**。宽度轴改的是「容器被闭合的结果」，不是「所有尺寸都不动」。

**这条约束的作用域是「同一份参考稿、同一个平台」，不是「iPhone 必须等于 iPad」。**
它说的是：一份 iPhone 稿，在手机的不同宽度档（竖屏 / 横屏 / 大屏手机）之间**视觉常量**不变；
一份 iPad 稿，在 iPad 的不同宽度档（竖屏 / 横屏 / 分屏）之间**视觉常量**不变。
它**不**表达「iPhone 的尺寸必须等于 iPad 的尺寸」——那是一条不存在的约束。

**「只有一套稿时，平板上字大一点更好看」是错的。** 当 Lanhu 里只有 `xx` 这一份稿时，
iPad 侧的尺寸没有任何独立出处，Agent 擅自放大就是重新设计，不是适配。

**双稿是「两套并列的独立参考」，不是「手机稿 + 放大」。** 当同一设计同时存在 `xx` 与
`xx-iPad` 两份稿时，这两份稿是**互相独立的**：iPad 组件的宽、高、字号、圆角、描边
**全部以 `xx-iPad` 稿自身为准**，与 `xx` 稿**没有派生关系**。因此「把手机稿等比放大到
iPad」这个说法本身就不成立——「放大」隐含了一个「从手机稿派生」的来源，而双稿之间
不存在这个来源。Agent 要做的不是「放大」，是「照 `xx-iPad` 稿再读一遍尺寸」。

跨平台尺寸若照两份稿各自取值、出现了差异，必须逐档声明在
`adaptiveLayout.sizeVariants[]`，`audit_adaptive.py` 的 `sizeInvariance` 才按分档白名单放行；
未声明的尺寸差异仍判 `size-not-invariant`。**不必手写**：用
`scripts/diff_device_variants.py --phone <xx>.document.json --tablet <xx-iPad>.document.json`
按图层名对齐自动 diff 容器宽高、生成 sizeVariants 片段（文本层与位置差异自动排除）：

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
      "why": "目的-iPad 稿中该按钮宽高为 141×28，照 iPad 稿取值，与目的稿无派生关系（字号跨稿差异走 typeFacts 溯源，不进本条目）"
    }
  ]
}
```

三条纪律：

1. **`basis` 与 `why` 都是必填**。没有这两项，`audit_adaptive.py` 的 `sizeInvariance`
   不把该元素算进分档白名单 —— 仍按「尺寸随窗口变」判 `size-not-invariant`。
2. **`sizeVariants` 声明的是「跨平台分档」，不是「平板上放大」。** 它的条目表达
   「`xx` 稿给 A、`xx-iPad` 稿给 B」，两个值各自由各自的稿决定，谁也不派生自谁。
   `sizeVariants` 的 `values` **只放宽高**——因为 `sizeInvariance` 只审计几何尺寸。
   **字号、圆角、描边不经 `sizeVariants` / `sizeInvariance`**：它们是样式恒量（`typeFacts`），
   各自照稿溯源，**iPhone 与 iPad 的字号可以相同，也可以不同**，二者没有强关联。
   唯一不随稿动的只有**平台硬下限**：最小点击区 ≥44pt / 48dp，那是可访问性规范，不是设计值。
3. **`sizeInvariance` 不是被放宽，是被收窄到「未声明即违规」，且「同设备内」永不豁免。**
   声明过的**跨平台**分档放行，没声明的尺寸变化依旧拦下。但有一条更硬的线：**同一设备
   （phone / tablet）内部的各个宽度档之间，尺寸必须逐字相等，`sizeVariants` 不能豁免**——
   同一台手机竖屏 / 横屏两个采样之间按钮尺寸变了，判 `size-not-invariant-within-device`。
   分档只允许发生在**跨设备**（phone vs tablet）之间，因为只有那里才有 `xx` 与 `xx-iPad`
   两份稿作为两个独立的取值来源。设备维度由 `windowSamples[].deviceClass` 声明或由 id 前缀
   （`phone-*` / `tablet-*`）推断——这是 `sizeInvariance` 能区分「同设备」与「跨设备」的依据。

### 4.2 `adaptiveLayout` 存在时，第一层**水平**位置比例规则只在 `compact` 档生效

[sizing-and-positioning.md §3.1.1](sizing-and-positioning.md#311-第一层子视图横向可重排纵向由内容链闭合)
规定「第一层子视图的位置按页面比例重排」。这条规则要**分轴看**：

- **水平位置** `x = page.width × ratio` 只在 **compact 档成立**。推到 1024pt 就会出事：
  位置按比例 ×2.6、而尺寸按契约 ×1，于是

  - 卡片左起从 33pt 变成 86pt，宽度仍是 327pt —— 右侧空出 611pt；
  - 卡片间距从设计稿的 13pt 被拉成 285pt；
  - 整个页面的视觉重心落在左侧 40%，右边一片空白。

  所以：**`adaptiveLayout` 存在时，regular / medium / expanded 档下第一层水平位置改由
  `widthPolicy` 重排**（`max-content-width` 就是把它们收进居中的内容列里）。
  `compact` 档维持原规则不变 —— 这条收口由 `firstLevelWidthClass` 表达，**只管水平轴**。

- **垂直位置**不属于宽度轴，也不默认采用页面高度比例。它由 safe area、相邻元素、垂直栈、
  intrinsic height 和滚动内容链闭合；短屏或长文本时允许滚动，不压缩整列内容。

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

Lanhu 只提供一份设计稿，其几何基准是**某一台设备**的 `bounds`。拿它直接比 iPad 的几何，
等于拿两个不同画布比对 —— 这不是「容差不够大」，是**证据类型不匹配**。所以 `adaptiveAudit`
只断言**几何关系**（视觉常量尺寸不变、贴边、不溢出、封顶等），不做像素比对。
这里的「尺寸不变」**只对 `kind: fixed` 的视觉常量成立**；`intrinsic` / `bounded` / `pinned`
的尺寸在各采样间按定义就会变化，审计不得把它们报成差异。

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
| `sizeInvariance` | 未声明分档的同一 `fixed` 元素，在**同一平台**的全部采样上点值**逐字相等** | **把「尺寸不缩放」从文档口号变成可执行断言** —— 这是本规范最有价值的一条（`sizeVariants` 声明的跨平台分档除外） |
| `insetPreservation` | 设计常量内边距在各采样上相等 | 拦「平板上边距被撑大」 |
| `noOverflow` | 元素不越出窗口 bounds | 拦分屏与自由窗口下的溢出 |
| `maxContentWidth` | 声明封顶的区域宽度 ≤ 声明值 + 容差，且水平居中 | 拦「声明了封顶但没生效」与「封顶了但没居中」 |
| `touchTarget` | 可交互元素 ≥ 44pt（iOS）/ 48dp（Android） | 拦「平板上点击区被放大/缩小」 |
| `noLetterbox` | 无黑边、非兼容缩放模式 | 拦「声称支持平板但以 iPhone 兼容模式运行」 |
| `continuity` | 多宽度采样下同 `fixed` 元素尺寸无变化、无未声明重叠 | 拦「只在两个断点上对，中间宽度崩」 |

### 7.3 与交付闸门的交叉

`adaptiveLayout` 声明的计划，其 `delivery-gate.status` **必须**包含 `adaptiveAudit`，
且 `scripts/validate_run.py` 会交叉核对：`diff/adaptive-audit.json` 判 fail 时
`adaptiveAudit` 不得记 `pass`。未声明 `adaptiveLayout` 的计划不受这条约束（但会在计划里留下告警）。

## 8. 反例清单（看起来对，其实错）

| 反例 | 为什么错 |
|---|---|
| 只有一份手机稿、却拿它乘系数放大去填 iPad | 那是「没有 iPad 稿 + 擅自派生」；有 `xx-iPad` 稿时照 iPad 稿是独立取值，不是放大 |
| 单列内容拉满 1024pt | 元素没越界、视觉常量没变，断言全绿但阅读节奏彻底坏了 |
| 把「视觉常量不变」误读成「所有尺寸都不变」 | 容器、卡片、文本列的宽高本就该随宽度档重排；一律写死等于放弃自适应，回到旧契约 |
| 反过来，把视觉常量也交给宽度档去改 | 字号、圆角、描边、44pt 触控区不随窗口缩放；那会破坏排版与可访问性 |
| `if device == "iPad"` / 按设备型号分支 | 分屏、Slide Over、自由窗口下型号不变而宽度变了 |
| 锁竖屏当作「只支持手机」的保险 | Android 15+ 在 sw≥600dp 上忽略方向锁；iOS 上会变成信箱模式 |
| 用 `UIScreen.main.bounds` 当布局基准 | 分屏与自由窗口下它返回整块屏，不是窗口 |
| 只声明两个断点（手机 / 平板） | 断点之间的连续宽度无定义，分屏必崩 |
| 只有一套稿时，平板上把字号调大「更好看」 | 设计稿只有一套排版，字号无独立出处；这是把适配做成了重新设计。有 `xx-iPad` 稿时字号照 iPad 稿，不在此列 |
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
- [ ] 视觉常量（`kind: fixed`：字号、圆角、描边、图标、最小点击区）在**同一平台的**全部宽度档上数值一致（跨平台无此约束，双稿各自照稿）；
- [ ] 容器、文本、按钮的宽高**没有**被写死：它们由 `intrinsic` / `bounded` / `pinned` 闭合，随宽度档重排。

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
| §4.2 第一层水平比例只在 compact 生效、纵向由内容链闭合 | `check_adaptive_layout.py` 的计划校验（`firstLevelWidthClass` 只管水平轴）；`layoutProportions` 只对 x 标记 `forced: "first-level"` |
| §4.3 窗口 ≠ 屏幕 | `check_adaptive_layout.py` 的 `screen-as-layout-source` / `display-metrics-as-layout-source` |
| §6 预留 hook 可核 | `check_adaptive_layout.py` 的 `missing-max-content-width` / `fixed-column-count` |
| §7 几何审计 | `diff/adaptive-audit.json`（`audit_adaptive.py` 产出） |
| §7.3 闸门交叉 | `validate_run.py` 的 `check_adaptive_gate` |
