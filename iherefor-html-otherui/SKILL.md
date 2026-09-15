---
name: iherefor-html-otherui
description: 将 Lanhu 导出的可运行 HTML/CSS/JS 页面作为视觉基准，由 Agent 生成并验证 SwiftUI、UIKit Swift、UIKit Objective-C、Jetpack Compose Kotlin、Android Views Kotlin 或 Android Views Java UI；当用户要求从 Lanhu HTML 落地 iOS/Android 原生页面时使用。
---

# Lanhu HTML 到多平台原生 UI

本 skill 面向“视觉还原优先”的 Lanhu 页面落地。输入是 Lanhu 缓存中完整的 HTML、CSS、JS 和资源，而不是仅依赖 Lanhu 结构化图层 JSON。目标是由 Agent 针对所选原生技术栈编写生产代码，并通过浏览器基准截图、目标 App 截图和编译测试形成闭环。

## 文档约定

- 标 **「强制」** 的小节，以及含「不得 / 禁止」的条目，是**硬约束**：违反即由闸门或校验脚本判 `fail`。例外只在原文显式写出。
- 用「应当 / 优先」表述的是**默认做法**：偏离时必须在实现计划或 `review.json` 里写明理由。
- 本文件只保留规则与判据。推演过程、反例清单与实测数据在 `references/` 中，需要时按文末索引去读，不要凭印象实现。

## 支持的输出模式

每次任务必须显式选择一个或多个目标模式，不得把不同平台的代码机械地复制成同一套组件：

- `ios-swiftui`: Swift + SwiftUI
- `ios-uikit-swift`: Swift + UIKit
- `ios-uikit-objective-c`: Objective-C + UIKit
- `android-compose-kotlin`: Kotlin + Jetpack Compose
- `android-views-kotlin`: Kotlin + Android Views/XML
- `android-views-java`: Java + Android Views/XML

## 核心原则

1. Lanhu HTML 页面是视觉基准和布局事实来源；结构化 JSON 只能作为辅助元数据。
2. 浏览器负责确定性渲染和测量，Agent 负责语义理解、组件边界、目标技术栈实现和视觉修复。
3. 脚本可以启动浏览器、提取事实、保存资源、截图、编译、测试和比较图像，但不得生成或覆盖生产 UI 源码。
4. 不得因为某个 CSS/JS 特性无法等价映射而静默删除；必须写入 `unsupported` 并进入交付报告。
5. 目标平台可以使用不同的组件树和布局策略；相同的是视觉目标，不是源代码形状。
6. 生成代码必须经过目标平台编译和截图验证，不能以“代码生成完成”代替视觉完成。
7. **约束策略不是「整页等比缩放」，而是两条独立的轴：尺寸固定、位置相对父视图。** 完整口径见下一节「尺寸与定位契约（强制）」。

## 尺寸与定位契约（强制）

**尺寸是常量，位置是约束。** 把整页当成一张图去缩放，等于把「设计稿恰好 393pt 宽」这个偶然事实
提升成布局规则：每个尺寸都被乘上屏幕相关系数，44pt 的点击区在窄屏缩成 40pt，字号缩放破坏排版。
设备之间本来就不等比（`393×852 → 402×874` 两轴比例分别是 `1.0229` 与 `1.0258`），
「等比」不是可选策略，而是一个不存在的东西。因此 `lanhuY = 132` 换算成 `135.02pt` 再写成字面量，
就是把布局钉死在探针设备上 —— 换台设备它就是错的，而它「有算过」，比一眼可疑的魔数更难发现。

实现计划必须给出 `layoutProportions`（每个区域的 `ratios` 与逐条 `relations`），
每条关系声明 `kind` 与位置基准 `of`。判据是**「这个值由谁闭合」**：

- `fixed` —— 设计稿给出封闭值的控件尺寸，写成字面设计值。**不参与任何比例缩放。**
- `pinned` —— 值由与父视图的约束闭合（贴边、占满、等分）。写成约束，不写比例系数：
  「左右各 16pt」是 `leading = parent.leading + 16`，不是 `width = parent.width * 0.9186`
  （后者在 430pt 宽的设备上给出 13.7pt 边距，而设计稿说的是 16pt）。
- `intrinsic` —— 必须给出 `why`，说明为什么这个量由内容决定（文本撑开、自适应图片）。
- `proportional` —— 只用于**确实**随父容器成比例变化的关系，必须给出理由；它不是默认项。
  必须用比例表达，且基准是**父视图**不是整页。iOS 用 `multiplier` /
  `UILayoutGuide`，SwiftUI 用 `GeometryReader`，Compose 用 `BoxWithConstraints` 派生比例或 `weight`，
  Views/XML 用 `layout_constraintGuide_percent` / `bias` / `layout_weight`。
- `centered` —— 居中或与兄弟元素对齐的锚点关系（`centerX` / `centerY` / `baseline` 相等）。

位置基准 `of` 默认是**直接父视图**；仅当直接父视图就是整屏画布时才写 `"root"`。
基准确认不了的要留痕待确认，不许默认填 `root`。

组件之间的布局关系仍须遵循设计稿，不得写成「探针设备上换算出来的绝对值」——
但这条约束管的是**位置与间距**，不适用于**控件尺寸**（尺寸一律取设计值）。

**第一层子视图（直接父视图 = 页面/page）的位置按页面比例重排，这是设备尺寸 ≠ 设计稿尺寸时**
**的自适应核心：**

- 第一层的**水平位置** `x = page.width × ratio`、**垂直位置** `y = page.height × ratio`，
  都写成相对 page 的比例原语（`multiplier`），标记 `forced: "first-level"`；
  **不得**写成探针设备上的绝对坐标（如 `x = 83`）—— 那在换台设备时就错。
- 第一层的**尺寸仍是 `fixed`**（组件尺寸恒等于设计稿，绝不缩放）；自适应的是**位置**，不是尺寸。
- 第一层 → 第二层（及更深）的**相对关系固定**：第二层的位置基准是它的直接父视图（某个第一层元素），
  不是页面。只有第一层这一档按页面比例，往下不再套。
- 背景（`.page` 外框）按 `pinned + fullBleed` 四边铺满，与第一层子视图按比例重排是两回事：
  前者是背景容器的铺满，后者是前景组件的重排。

`scripts/layout_proportions.py` 由事实表与设备尺寸生成这份声明与「探针设备上算出来的绝对值」
清单；`scripts/check_layout_proportions.py` 按声明逐条核对源码，**计划驱动而非正则扫描** ——
每一类 `kind` 有它自己的判据（`fixed` 的值得来自设计稿、`pinned` 不带比例系数、
`proportional` 才要求比例表达），这样才不会把圆角 12、边距 16、按钮高 44
这些**本来就该写成字面量**的设计常量误报成违规。

判定分两档：数值 > 48pt 的字面量不可能是手选的设计常量，判违规；≤ 48pt 与常见设计常量无法区分，
只列进 `ambiguousLiterals` 待人工确认，不计入违规。比这两档更硬的一层是**计划怎么声明，源码就得
怎么实现**：声明 `proportional` 的位置写成探针设备上的绝对值、声明 `pinned` 的贴边却带上比例系数、
声明 `intrinsic` 却不给理由，都会被拦下；反过来，声明 `fixed` 的尺寸和声明 `pinned` 的内边距本来
就该写成字面量，报成违规才是错。

完整推演与反例清单见 [references/sizing-and-positioning.md](references/sizing-and-positioning.md)，
字段契约见 [references/artifact-contract.md](references/artifact-contract.md#布局关系与控件尺寸的约束口径强制)。

> **产物代际**：`schemaVersion < 3` 的 `layout-proportions.json` / `layout-verdict.json` 是旧的一轴
> 口径（非文字元素一律 `proportional`、位置一律 `of: "root"`、`kind` 只有两档），不能当作本契约的样例。

```bash
# 第 2 步：生成布局约束规格（rect 的坐标空间由 rectInReference == rect*dpr 自动判定，判不出就拒绝继续）
python3 scripts/layout_proportions.py --page-facts <page>/reference/page-facts.json \
    --target-mode ios-uikit-objective-c --output <run>/plans/layout-proportions.json

# 实现完成后：核对源码是否真的照计划声明的方式实现（只校验计划用 --plan-only）
python3 scripts/check_layout_proportions.py --plan <run>/ui-implementation-plan.json \
    --source <原生源码根>

# 交付前：连同布局约束一起判（不给 --source 就只告警，不假装验证过）
python3 scripts/validate_run.py --run <run-dir> --source <原生源码根>
```

### 比例模型与 `fit` 策略必须一致

`fit` 映射与比例映射是两条直线，最大偏差恰好等于 letterbox 厚度（`padding.max`）。
`padding.max` 超过位置容差时二者不可互换：实现用比例模型，**对齐审计也必须改用比例模型预测**，
否则是拿 `fit` 的预测框去量比例布局，把模型差报成实现错误。用
`python3 scripts/canvas_map.py --self-test` 后的 `axis_deviation()` 读这个值，不要凭感觉判断。

## 宽度轴与平板适配（强制）

上两节只保证「换设备不崩」，回答不了第三个问题：**父视图宽到 1024pt 时，内容怎么收敛？**
缺这一轴时，`393×852 → 402×874` 上成立的那条「第一层位置按页面比例」推到 1024pt 会给出
**错的**结果：位置 ×2.6、尺寸 ×1，卡片左起 33pt 变 86pt、宽度仍是 327pt、右侧空出 611pt，
间距 13pt 被拉成 285pt。所以平板适配要补的不是「iPad 布局代码」，而是**宽度轴**。

**布局是窗口宽度的连续函数，不是「手机一套、平板一套」的两张快照。** iPad 不是一个尺寸：
全屏竖 1024×1366pt、横 1366×1024pt，分屏 1/3 与 Slide Over 回落到 ~320pt，
Stage Manager 与 iPadOS 26 自由窗口下宽度在 320~1366pt 之间连续可变。Android 同理
（折叠屏、自由窗口、桌面模式）。所以按**宽度档做决策**，但布局必须对档位之间的任意宽度
都不崩 —— 「两个断点」的写法在分屏与自由窗口下必然失效。

实现计划必须给出 `adaptiveLayout`，至少包含四个采样（`phone-compact` /
`tablet-regular-portrait` / `tablet-regular-landscape` / `phone-regular-landscape`）、
每个区域的 `widthPolicy`、以及非空的 `forbiddenAdaptations`：

- `widthPolicy` 六档 —— `full-bleed` / `max-content-width` / `centered-column` / `grid` /
  `pane` / `stacked`。**`stretch-full-width` 不在枚举里**：单列内容拉满 1024pt 是本契约要拦的
  头号问题 —— 元素没越界、尺寸也没变，断言全绿，但阅读节奏彻底坏了。「拉满」必须由
  `full-bleed` 显式声明，不能是默认行为。
- `max-content-width` / `centered-column` 必须给 `maxContentWidth.value`（设计常量，
  600~700pt 量级，**不随窗口缩放**）与 `reason`；`grid` 必须给 `columnCount` 的三档
  且单调不减。
- **`firstLevelWidthClass` 缺省 `compact`**：上一节的「第一层位置按页面比例」只在这一档
  生效；regular / medium / expanded 档下第一层位置改由 `widthPolicy` 重排。这条是必需的收口，
  不是可选开关。

三条交界规则：

1. **宽度轴只改「容器宽度」与「第一层位置」，不改任何尺寸。** 字号、行高、圆角、描边宽度、
   最小点击区（≥44pt / 48dp）在全部宽度档上逐字相同。「平板上字大一点更好看」是错的 ——
   设计稿只有一套排版，那不是适配，是重新设计。
2. **第一层位置比例规则只在 `compact` 档成立**，见上。
3. **窗口 ≠ 屏幕。** 分屏与自由窗口下 `UIScreen.main.bounds` / `DisplayMetrics.widthPixels`
   返回的是**整块屏**，不是你的窗口，用它做布局基准会得到错的原点与错的可用宽度。
   iOS 用 `view.bounds` / `windowScene`，Android 用 `WindowMetrics` / `WindowSizeClass`。
   另外 Android 15（API 35）起，`sw >= 600dp` 设备上系统会忽略方向锁定并强制可调整大小，
   Android 16 在平板上完全忽略 —— 锁方向不是「只支持手机」的保险，是直接变成信箱模式。

**「预留」的含义是「接口在、值仍是手机值」，不是第二套布局。** 写两套布局（一套在手机档
不生效）会污染像素 diff、在门 1 里变成死代码，还隐含了「宽度只有两档」这个错误前提。
六模式各自必须留的 hook 与可核判据见
[references/adaptive-layout.md](references/adaptive-layout.md)。

**平板这一关不做像素比对。** Lanhu 只提供一份设计稿，`reference.png` 是某一台设备的像素
基准；拿它比 iPad 截图是拿两个不同画布比对，`audit_alignment.py` 的 `domVsReference` 会直接判
「基准不可信」。所以验证拆成两半：**静态**并入门 1（禁止模式、封顶原语存在性、方向锁、
设备族与资源目录），**运行期**做几何契约审计（多宽度采样，八项断言）。

```bash
# 门 0：宽度轴声明自检（采样、policy、maxContentWidth、columnCount 单调性）
python3 scripts/check_adaptive_layout.py --plan <run>/ui-implementation-plan.json --plan-only

# 门 1：声明与源码逐条核对（写码完成后、编译之前）
python3 scripts/check_adaptive_layout.py --plan <run>/ui-implementation-plan.json \
    --source <原生源码根>

# 交付前：多宽度采样的几何契约审计（不做像素比对）
python3 scripts/audit_adaptive.py --targets <run>/adaptive-targets.json \
    --plan <run>/ui-implementation-plan.json --output <run>/diff/adaptive-audit.json
```

`audit_adaptive.py` 的八项里，`sizeInvariance`（同一 `fixed` 元素在全部采样上点值**逐字
相等**）最有价值 —— 它把上两节的「尺寸不缩放」从文档口号变成可执行断言。`sampleCoverage`
缺必需采样时判 `fail`：缺采样会让其余七项「全绿」，那是**假绿**。

完整规范、六模式原语对照、反例清单与落地检查清单见
[references/adaptive-layout.md](references/adaptive-layout.md)；字段契约见
[references/artifact-contract.md](references/artifact-contract.md#ui-implementation-planjson-的-adaptivelayout)。

## 可移植性契约（强制约束）

本 skill 必须能在任意 coding agent / CLI 宿主下运行，**不得绑定任何具体宿主**。改写本 skill 时遵守：

1. 脚本、参考文档、工作流中不得出现宿主产品名，也不得假定某个宿主专有的命令、配置路径或配置格式。
2. 与宿主交互只允许通过通用形态表达：**MCP 的 stdio server 注册**（`command` + `args` + `env`）、**JSON 的 `mcpServers` 配置**、**TOML 的 `[mcp_servers.*]` 配置**、以及**标准命令行**。
3. 「去哪里找宿主的注册」属于**数据**，不属于逻辑：候选位置集中在 `scripts/mcp-registries.json`，脚本只按 `kind` 描述的通用水解析。新增或更换宿主时改数据表即可；表里没有的宿主用 `scripts/check_lanhu_mcp.py` 的 `--mcp-config` / `--registry-cmd` / `--registries`（或环境变量 `LANHU_MCP_CONFIGS` / `LANHU_MCP_REGISTRIES`）显式指定，**不得为此修改脚本**。
4. 运行时环境（Node、Python、浏览器、Xcode、Android SDK）按能力探测，不按宿主假设；不写「某宿主一定装了 X」这类推断。
5. 评测运行器的引擎选择（`evals/eval.yaml` 的 `engine.name`）属于评测工具自身的设置，不是本 skill 的依赖；它不影响 skill 的可移植性，换任何受支持的引擎都应能跑同一批用例。
6. 新增文档或脚本时，若确实必须提到某个宿主的名字，只允许出现在 `scripts/mcp-registries.json` 这类适配器数据中，并附上「可替换/可删除」的说明。

## Lanhu MCP 输入

用户提供 Lanhu 链接时，必须先使用已配置的 `mcp__lanhu_mcp` 服务获取项目、设计和可运行 HTML/CSS/JS/资源，并写入 `.ihereforUI/pages/<page-id>/source/`；不能要求手工下载，也不能仅凭结构化 JSON 生成原生 UI。严格调用顺序、缓存、版本和失败处理见 [references/lanhu-input.md](references/lanhu-input.md)。

若 MCP 未安装、未构建、未注册或凭据未配置，必须先运行 `scripts/check_lanhu_mcp.py` 并按 Lanhu 输入参考引导安装/注册；这是阻塞条件，不能绕过 MCP 改用手工资源或继续生成代码。注册按上述可移植性契约的通用形态进行，不依赖任何宿主专有命令。安装引导不得打印或持久化 Lanhu 凭据。

## 资源与代码质量

在复制资源或编写代码前，必须读取 [references/resource-and-code-quality.md](references/resource-and-code-quality.md)。先扫描并复用目标工程已有资源体系；没有既有约定时才使用平台默认目录。资源必须按使用场景语义命名，不能把 `img_0` 等来源编号作为生产名。生成代码必须按 screen/section/style/resources 分层，所有按钮和可点击元素都要连接到命名明确的点击处理空函数。

## 既有项目接入

如果目标工程不是空项目，或用户要求二次开发/新增页面，必须先读取 [references/existing-project-integration.md](references/existing-project-integration.md)，完成工程审计并生成 `.ihereforUI/integration/project-audit.json`、`.ihereforUI/integration/integration-plan.json` 及页面级接入计划。计划批准前不得写入生产代码；文件名、模块、导航、依赖、资源、状态、测试和回滚方式都必须先列明。

## 五类持续视觉事实（强制约束）

以下事实必须贯穿发现、计划、编码、截图和修复全过程，不能只在首次分析时阅读后凭记忆实现：

1. 资源位置与层级：记录每个图片/SVG/背景资源的 URL、原始尺寸、目标坐标、z-index/stacking context、裁剪和 transform，并建立原生资源映射。每张图片还要记录它在基准图里的**非透明内容 bounds**（`images[].alphaBounds`），因为「frame 对了」不等于「内容对了」。
2. 元素 bounding box：从运行中的 HTML 读取每个可见区域和关键元素的 `getBoundingClientRect()`，保存为事实表。同时保存 `rectInReference` —— 元素在 `reference.png` 里的像素 rect（`= (rect + scroll) * devicePixelRatio`）。这是「DOM 说元素该在哪」的唯一事实来源；只有 CSS px 的 `rect` 时，任何像素级比对都得各写一遍换算。
3. 视觉样式：记录最终字体/fallback、字号、行高、颜色、透明度、渐变、阴影、圆角、overflow 和 transform；无法等价表达的属性写入 `unsupported`。字体的「最终」指**运行时实际用上的**字体，不是 CSS 声明的 `fontFamily`：必须记录 `fontsResolved` / `primaryFont`（来自 CDP `CSS.getPlatformFontsForNode`，附 `glyphCount`）与 `textMetrics`（每个文本元素的 `advanceWidth`、`lineHeight`、`rects`）。判定字体有没有生效见「基准的字体链也要核」一节。
4. 画布缩放关系：保存 HTML viewport、devicePixelRatio、目标设备 bounds、截图像素尺寸和坐标变换（`policy`、scale、letterbox、inset，以及正向与逆向 mapper）。禁止直接复制另一设备的绝对像素坐标。
5. 差异证据：每次修改都保存 actual screenshot、diff summary（整页及关键区域）和修改原因；没有 diff 或明确的 `not-run` 原因，不得声称视觉完成。差异必须分类为**结构差异**（几何错位：边缘在两张图里对不上）、**填充差异**（平坦区颜色写错）与**纹理差异**（抗锯齿/字体栅格化：几何一致、只是像素值不同），放行判定只看前两类。

这些数据应落在 `page-facts.json`、`browser-meta.json`、`ui-implementation-plan.json`、`review.json` 和 `diff/` 中，并能从原始 HTML 元素追溯到原生视图。上下文压缩或 Agent 换手后必须重新读取这些产物，不能依赖对话记忆。

## 统一画布缩放契约（强制）

Lanhu 画布坐标不是目标设备坐标。先计算 `scaleX = trueDeviceWidth / lanhuCanvasWidth`、`scaleY = trueDeviceHeight / lanhuCanvasHeight`；保持比例时使用统一 scale，否则显式记录 `fit`、`fill` 或 `letterbox`，不能悄悄拉伸。

**默认策略是 `fit`**（等比缩放并居中：`scaleX == scaleY == min(ratioX, ratioY)`，余量均分为 letterbox）。这不是省略号式的「随便选一个」：393×852 → 402×874 时 `fit = 1.02290`、`fill = 1.02582`，差异 0.28%，在 852pt 高的画布上等于 **2.4pt 的累计错位** —— 已经超过契约要求的 2pt 位置容差。所以不得改用 `fill` 或 `custom` 来「凑」某个区域的位置；确需非等比时必须显式写明 `policy` 与 `reason`。

**坐标换算只允许通过 `scripts/canvas_map.py` 进行，禁止手写 `x * scaleY` 这类换算。** 该模块同时给出正向与逆向映射，二者是同一组参数的代数反解，不是两套约定：

```text
正向 lanhu → device:  targetX = (lanhuX - letterbox.x) * scaleX + origin.x
逆向 device → lanhu:  lanhuX  = (targetX - origin.x) / scaleX + letterbox.x
```

分析代码（区域 diff、对齐审计、确定性证据生成）必须 import 它。手写换算会引入「多乘一层 scaleY」这类系统性偏移，而这类错误在整页 diff 数值上完全看不出来：

```bash
python3 scripts/canvas_map.py --runtime-device <run>/runtime-device.json --canvas 393x852
python3 scripts/canvas_map.py --transform <run>/ui-implementation-plan.json \
    --forward 0,495,393,48 --box-to pixels
python3 scripts/canvas_map.py --self-test
```

任意元素必须使用同一 mapper：`targetX=(lanhuX-letterboxX)*scaleX+originX`、`targetY=(lanhuY-letterboxY)*scaleY+originY`、`targetWidth=lanhuWidth*scaleX`、`targetHeight=lanhuHeight*scaleY`。图片必须使用映射后的 target frame，不能直接使用自然尺寸、导出像素或原始 CSS width。文本字号/行高、间距、圆角、阴影和 transform 平移/缩放也遵守同一变换；图片 `contentMode`/`scaleType` 必须依据 HTML 的 object-fit/background-size 事实选择。

### 图片缩放硬约束（不可例外）

- 图片的**外框和内容绘制区域**必须同时使用同一 `scaleX/scaleY`；仅缩放 `UIImageView`/`Image`/`Image composable` 的 frame 不足以证明图片已正确缩放。
- 禁止让图片依赖 intrinsic/natural size、资源导出像素、`wrap_content`、SwiftUI 默认 ideal size 或 Compose 默认 intrinsic measurement；必须显式给出 mapper 计算后的 width/height。
- UIKit：`UIImageView` 必须使用 mapper 后的 frame 或显式 width/height constraints，`contentMode` 必须与 HTML `object-fit` 对应；禁止用未映射的 `sizeToFit`、intrinsic content size 或未拉伸的 `backgroundImage` 替代。UIButton 背景图必须使用 resizable image 或明确的 mapped bounds。
- SwiftUI：图片必须 `.resizable()` 后再 `.frame(width: mappedWidth, height: mappedHeight)`，并明确 `.scaledToFill()`/`.scaledToFit()`；不能只写 `Image("...")`。
- Compose：必须使用 `Modifier.width/height`（由 mapper 计算）和明确 `ContentScale.FillBounds/Crop/Fit`；不能依赖 `wrapContentSize`。
- Android Views：ImageView 必须有 mapper 后的 LayoutParams/constraints 和明确 `scaleType`；不能依赖 `adjustViewBounds` 或 drawable intrinsic size。
- 每张图片必须在 `page-facts`、实现计划和视觉 review 中记录：Lanhu frame、目标 mapped frame、contentMode/scaleType、自然尺寸、最终截图 frame。任一图片 frame 或尺寸证据缺失，交付闸门必须为 `needs-review`。
- 每轮 diff 必须至少抽查一张 hero 图片、一张卡片/背景图和一张图标，比较其实际 bounding box 与 mapper 预测值；整页 changedRatio 通过不能掩盖图片局部未缩放。
- 如果出现图片一侧留白、图片只占 mapped frame 一部分或与相邻组件出现断裂，必须判定为图片缩放失败；禁止通过移动旁边组件、裁剪 reference 或增加随机 padding 掩盖。优先检查 `contentsGravity/contentMode/scaleType/ContentScale`、图片 layer 的 bounds/contentsScale、资源透明边界和截图坐标换算。
- “图片 frame 已缩放”不等于“图片已缩放”：必须额外测量 PNG/SVG 的非透明 alpha 内容 bounds，并验证其在目标截图中的可见 bounds 与 Lanhu 可见 bounds 按 `scaleX/scaleY` 成比例；若资源存在透明留白，必须记录并按 HTML 的裁剪/背景尺寸规则处理。

目标设备尺寸必须在应用运行时通过平台 API 获取，禁止根据设备型号、截图常见尺寸或手工常量推断。每次运行必须同时记录 API 返回值、根窗口/内容 view bounds、截图像素尺寸和 device scale，再计算 mapper：

| 目标模式 | 运行时尺寸 API |
|---|---|
| iOS UIKit Objective-C | `[UIScreen mainScreen].bounds.size`，并核对 `self.view.bounds.size` |
| iOS UIKit Swift | `UIScreen.main.bounds.size`，并核对 `view.bounds.size` |
| SwiftUI | `GeometryReader` 的容器 size；必要时记录 `UIScreen.main.bounds.size` 作为屏幕证据 |
| Android Compose | `BoxWithConstraints`/`LocalConfiguration.current` 的实际 dp；截图前记录 `WindowMetricsCalculator` bounds |
| Android Views Kotlin/Java | `WindowMetricsCalculator.getOrCreate().computeCurrentWindowMetrics(activity).bounds`，并核对根 view width/height |

`UIScreen`、`GeometryReader`、`WindowMetrics` 返回值必须写入 `runtime-device.json`，并由它们计算 `scaleX/scaleY`；不得把 `402x874`、`393x852` 等示例尺寸直接写成生产 mapper。若 API 尺寸、根 view bounds 和截图换算不一致，必须停止视觉交付并记录差异原因。

实现计划必须包含 `canvasTransform.policy`、`canvasTransform.coordinateMapper.forward` 与 `canvasTransform.coordinateMapper.inverse`；禁止各组件自行手调比例或混用 Lanhu px、UIKit pt、Android dp 和截图 px。缺少 `inverse` 时分析代码只能自己反解，而手写反解正是「多乘一层 scaleY」的来源。

实现计划还必须包含 `layoutProportions`：每个区域的 `basis` / `parentIndex` 与逐条 `relations`（`kind` 为 `fixed` / `pinned` / `proportional` / `intrinsic` / `centered` 之一），以及 `forbiddenLiterals` 清单。`canvasTransform` 与 `layoutProportions` 分工不同，不要互相替代：

- `canvasTransform` 是**测量用**的桥 —— 把 Lanhu 坐标换算到设备点和截图像素，供审计与 diff 使用；
- `layoutProportions` 是**实现用**的规格 —— 告诉原生代码每条关系该按哪一类 `kind` 写、基准是哪一级父视图。

拿 `canvasTransform` 算出的绝对值去写约束，就是把测量桥当成了实现规格，这正是布局约束契约要禁止的动作。

## 顶部系统区域与安全区

状态栏、刘海、Dynamic Island、导航栏和手势区域属于截图画布的一部分，不能默认当作页面外部留白。Agent 必须先从 HTML 基准确认页面是否绘制到顶部系统区域，再为每个目标平台记录 `systemBars` 策略：

- `underlap`: 页面背景/图片延伸到状态栏或导航栏下方，前景内容使用显式 inset；
- `inset`: 页面整体从安全区之后开始，只有在 HTML 基准确实保留空白时使用；
- `mixed`: 背景 underlap、文字和交互控件 inset。

iOS 必须显式处理 `edgesForExtendedLayout`、`extendedLayoutIncludesOpaqueBars`、safe-area inset、状态栏样式和 home indicator 区域；不能把 `safeAreaLayoutGuide` 作为所有页面的根部起点。尤其要检查 `UIScrollView` 的 `contentInsetAdjustmentBehavior`：UIKit 可能自动注入顶部/底部 safe-area content inset，若页面坐标已经包含系统区域，必须设为 `never` 并显式设置 `contentInset`，否则整页会下移。Android 必须显式处理 `WindowInsets`/`setDecorFitsSystemWindows`、status/navigation bar 对比度和 edge-to-edge；不能依赖设备默认 inset。目标 App 截图必须和 HTML 使用同一画布坐标系，任何系统区域偏移都要进入 diff 和 `review.json`。

## 浏览器运行时

默认使用 Playwright Chromium：

- Agent 交互优先使用 Playwright CLI + Skills。
- 需要持续页面上下文、复杂 DOM/shadow DOM 或探索式交互时，可使用 Playwright MCP。
- 确定性渲染、事实提取和截图由固定 Playwright 脚本执行，不交给另一个自主浏览器 Agent。
- 每个任务使用隔离 session；记录浏览器版本、viewport、deviceScaleFactor、字体、locale、timezone 和资源加载结果。
- 渲染前等待 `document.fonts.ready`、图片完成和页面稳定；默认禁用动画/transition，除非任务明确验收动态状态。
- 同一页面至少保存 HTML reference screenshot、目标 App screenshot、diff 和运行参数。

## iOS 工程与设备环境

任意 iOS 目标模式必须先读取 [references/ios-environment.md](references/ios-environment.md)，并运行 `scripts/discover_xcode_environment.py` 探测 `.xcworkspace/.xcodeproj`、scheme、模拟器和真机。禁止凭记忆选择 `-project`、`-workspace`、scheme 或 destination；探测结果必须进入页面 run 的 `ios-environment.json`。真机和模拟器是不同证据类型，不能互相替代。

浏览器工作流的详细契约见 [references/browser-runtime.md](references/browser-runtime.md)。

## 强制 Agent loop

第 5～7 步合起来是**验证阶段**，按「静态门先跑、动态门只跑一次」组织，不要按字面顺序一路走到编译：

| 门 | 位置 | 成本 | 判什么 |
|---|---|---|---|
| 门 0 | 第 2 步写计划时 | 纯静态，秒级 | 计划自身完整：`layoutProportions` 的 `basis` / `parentIndex` / `kind` / `of` 是否齐全 |
| 门 1 | **第 4 步写码完成后、第 5 步编译之前** | 纯静态，秒级 | 层级与布局关系是否照计划实现（`check_layout_proportions.py --source`） |
| 门 2 | 第 5 步 | 需编译装机，约 10 s / 轮 | 只能靠运行才知道的事：能否编译、能否启动、运行期几何与交互 |
| 门 3 | 第 6～7 步 | 秒级 | 三类差异的具名区域归因、扣除已声明差异后的剩余值、交付闸门 |

**门 1 是唯一被前移的门，也是收益最大的一处**：层级与布局关系全部静态可判，把它的迭代留在编译之前，
编译与截图就只需要发生一次。门 1 比门 2 快约 70 倍（实测 0.14 s 对 9.9 s / 轮），
但真正的收益不是省下这几秒 —— 而是**避免让 Agent 经历一次完整的截图诊断循环**：
读一张整页截图、形成假设、改码、重跑，那是分钟级，而且可能建立在错误假设上。
门 1 直接给出 `文件:行号` 与规则名，把「看图猜」换成「读一条定位精确的告警」。

> **优化方向由此确定：盯「Agent 需要经历几轮推断」，不要盯「构建快几秒」。**
> 任何新增的检查，先问它能否把某一类问题从「需要截图诊断」降级为「静态告警并给出位置」。
> 成本结构的实测明细见 [references/feedback-loop.md](references/feedback-loop.md)。

### 1. 发现、设备探测与参考基准

1. 确认 Lanhu HTML 入口、CSS/JS 相对路径、资源目录和页面状态。
2. 按目标模式探测运行时设备尺寸（iOS 见 [references/ios-environment.md](references/ios-environment.md)，Android 用 `WindowMetricsCalculator`），写入本次 run 的 `runtime-device.json`。**没有设备尺寸就不允许渲染基准图。**
3. 用 Playwright 以设备点尺寸与设备 scale 渲染 HTML：`node scripts/render_reference.mjs --input <source> --output <page>/reference --viewport-from <run>/runtime-device.json`。基准图默认是视口截图；`--full-page` 只用于人工阅读，不参与像素比对。
4. 记录 console、network、字体和资源错误，并把 `reference.png`、`page-facts.json`、`browser-meta.json` 写入页面级 `reference/`。

四步都完成后才进入第 2 步。基准图与目标 App 截图像素尺寸不一致时，diff 结果不具证据效力，禁止用缩放/裁剪后的派生图凑尺寸。

**但「尺寸一致」只是同源的必要条件，不是内容对齐的证据。** 两张图像素尺寸完全相同、整页检查全绿，内容仍可能整体偏移且偏差随 y 递增。像素尺寸相等证明不了任何东西，必须另外跑一次元素级对齐审计：

```bash
python3 scripts/audit_alignment.py \
    --reference <page>/reference/reference.png \
    --actual    <run>/actual/app.png \
    --page-facts <page>/reference/page-facts.json \
    --runtime-device <run>/runtime-device.json \
    --output    <run>/diff/alignment.json
```

它把「谁和谁不符」分成两个必须区分开的故障，因为二者需要**相反的动作**：

- `domVsReference`（基准图 vs DOM 事实）：不符 ⇒ **基准本身不可信**（渲染 viewport/scale 与采集事实表时不一致），先重修基准，**不要**照着基准图调 App 代码。
- `referenceVsActual`（基准图 vs 实机截图）：不符 ⇒ 基准可信，问题在 App 实现侧，按区域改代码。

退出码 0 = 都在容差内，1 = 存在超容差偏移，2 = 证据不足。判 `needs-review` 时不得把 `visualDiff` 记为 `pass`；`scripts/validate_run.py` 会拦住这种矛盾。

### 基准的字体链也要核

字体被静默替换时，基准图会「**自洽地错**」：CSS 声明了某字族、页面里 `@font-face` 规则数为 0、也没有 generic fallback，Chromium 回落到默认衬线字体。DOM 事实表与基准图因为用了同一套回落字体而互相印证 —— 对齐审计的 `domVsReference` 判 `aligned`，于是它把不一致归给 App 侧，而那句结论在它自己的视野内是**对的**。照着它去改 App 的字体，只会离设计稿越来越远。

所以对齐审计之后必须再核一次字体链，**声明 ≠ 结果**：

```bash
python3 scripts/audit_fonts.py \
    --page-facts   <page>/reference/page-facts.json \
    --browser-meta <page>/reference/browser-meta.json \
    --output       <run>/diff/font-chain.json
```

它逐元素比对「CSS 声明的族」与「运行时实际用上的族」（`primaryFont` / `fontsResolved`，来自 CDP `CSS.getPlatformFontsForNode`），退出码 0 = 一致，1 = 发生替换（账在**基准**侧），2 = 证据不足。判出替换时不得把 `reference` 记为 `pass`；`scripts/validate_run.py` 会拦住这种矛盾。

**修法只有一种：把 CSS 声明的族改成 CDP 实际报回的那个名字，然后重新渲染基准、重新测量**，再判断 App 侧还有没有残余差异。**不要指望 `@font-face` 能救** —— CDP 报回的是**底层字体自己的名字**，不是 `@font-face` 里的 `font-family` 别名：实测 `@font-face{font-family:'MyAlias';src:url('Outfit-Bold.ttf')}` 报回 `Outfit`，`@font-face{font-family:'AvenirLT-Black';src:local('Avenir Black')}` 报回 `Avenir Black` —— 别名只会让「声明 vs 结果」继续对不上，闸门照样判替换。同理，macOS 上 CDP 报回的是**带字重的族名**（`font-family:Avenir` + `font-weight:900` 报回 `Avenir Black`），所以「声明裸族名 + 字重」也不成立。正确顺序是**先探宿主真实有什么**（读 `primaryFont`，或用一个临时页面跑一次 `CSS.getPlatformFontsForNode`），再照那个字符串写声明。实测数据与逐步配方见 [references/browser-runtime.md](references/browser-runtime.md#基准字体链的修法)。

三条判定纪律，都指向同一件事——**闸门要准，不是要响**：

- **族名格式差异不算替换。** `Avenir-Medium`（CSS 写法）与 `Avenir Medium`（CDP 报回的 `familyName`）是同一个族；逐字符比会把这类差异全报成替换，等于把闸门焊死。
- **系统关键字不算替换。** `-apple-system` / `system-ui` 由平台解析成系统 UI 字体，本来就没有可比对的族名字符串；命中它们却比不相等不构成证据。
- **没做字体测量的事实表判「证据不足」，不判干净。** 旧 schema 的 `page-facts.json` 没有 `primaryFont`；`fontMeasurement.ok` / `fontJoin.ok` 为 `false` 时元素上残留的字体字段也不能当成本次证据 —— 拿它下结论比没有数据更危险。

### 2. 页面事实表

Agent 必须查看运行中的页面和基准截图，建立页面事实表：可见区域、真实叠层、组件候选、文本、图片/SVG、渐变、阴影、滚动容器、交互状态和不支持特性。不得直接把每个 DOM 节点当成原生组件。页面必须按视觉区域逐一复现（hero、标题/说明、每张卡片、CTA、页脚等），每个区域列出 bounding box、资源/层级、样式事实、原生组件映射和验证截图。

**「文本元素」的判定只有一个：元素自身有直接子文本节点**（事实表里的 `ownsText` / `ownText`）。不要用 `innerText`——它把所有后代文字聚合上来，于是每个容器都变成「幻影文本元素」，字体测量和位置预测都会挂在错误的框上。同理 `textMetrics.rects` 只取直接子文本节点（`ownOnlyText: true`），否则一个既有自身文字又有子元素文字的表头会得到一个横跨两者的并集框。**一旦事实表里的文本元素含容器，或 `browser-meta.json` 的 `fontJoin.ok` 为 `false`，这份事实表就不能用于元素级审计，必须重新渲染取一份新的。**

### 3. 目标实现计划

输出 `ui-implementation-plan.json`，至少包含目标模式、参考 viewport、组件边界、坐标系、布局策略、资源映射、可访问性标识、交互候选和 `unsupported` 项。布局策略分两段：`layoutProportions`（尺寸轴 + 位置轴）与 `adaptiveLayout`（宽度轴，见「宽度轴与平板适配」）。该文件是 Agent 决策记录，不是生产源码生成器的输入模板。

**布局与字号的权威来源是 ``design-facts.json``，不是渲染 DOM 的反推。** 第 1 步已调用
`lanhu_get_design_document`（**必须 `depth: 99`**，默认只展开 2 层）并经 `scripts/lanhu_design_facts.py`
解析成 `reference/design-facts.json`：父视图归属（由 `children` 树推导，`metadata.parentId` 实测全 null
不可靠）→ `regions[].parentIndex`；字号/字体/文本/颜色（`style.typography`，字号已按 `canvas.scale` 还原）
→ `unsupported[typography]` 与字号常量；描边/填充/阴影（`style.borders`/`fills`/`shadows`）→ 覆盖式装饰层
与 border 内缩判据。**凡是 design-facts 已给出、Agent 却写成 `kindSource: "agent-decided"` 或靠 CDP/
`advanceWidth` 反推的，都属于可消除的推断，应回填。** 渲染 DOM 事实只负责 design-facts 给不了的那一半
（字体实际命中、计算后样式、`rectInReference`）。

计划里还必须有一份 `runtimeRisks` —— 把「只能在运行期暴露、但**现在就能决策**」的风险提前写下来，
逐条给出决策与理由。第 5 步是分钟级的取证门，这些问题一旦漏到那里才发现，就要重走一次编译截图：

- `interactionCoverage`：每个覆盖式装饰子视图（描边环、蒙版、渐变层）的
  `userInteractionEnabled` 决策。**默认必须是 NO**，只有确实要接收点击时才 YES。
- `scrollInset`：`UIScrollView.contentInsetAdjustmentBehavior` 的取值。
  页面坐标已含系统区域时必须设 `never` 并显式给 `contentInset`，否则整页下移。
- `systemBars`：`underlap` / `inset` / `mixed` 三选一，见「顶部系统区域与安全区」一节。
- `fontAvailability`：目标平台上每个字族**实际存在**的字重（用 `.ttc` 的 name 表核对，
  不要猜）。例如 `PingFangUI.ttc` 里只有 `PingFangTC-Medium`，没有 `PingFangTC-Semibold`；
  `fontWithName:` 会落到同族其它字重，而不是掉到系统 UI 字体。
- `windowSizing`：目标工程会不会以**兼容缩放模式**（iPhone 2x 放大）或信箱模式跑在平板上。
  判据是设备族与 iPad 资源/方向声明是否齐备（`TARGETED_DEVICE_FAMILY` 含 2、
  `Assets.xcassets` 有 iPad idiom、Info.plist 有 `UISupportedInterfaceOrientations~ipad`；
  Android 侧是 `sw600dp` 资源目录与 `resizeableActivity`）。这一条**截图看得出来**
  （黑边、整体模糊），但等到截图才发现就要重走一次编译装机。

计划里还要有一份 `gateReachability` —— 文字密集页的 `structuralRatio` 有一个**物理下界**
（基准画布 `scale(1.0229)` 使基准字形 = 设计字号 × 1.0229，而字号不得缩放，相差 2.29%
足以越过强边配对容差），它**不可能降到 0**。在计划里声明它，比较器才会按它判
`pass-with-review`；不声明就只能反复逼近不存在的 0。声明必须可核：

- `expectedStructuralFloor`：数值，且**必须 ≥ 比较器的 `maxStructuralRatio`**；
- `unavoidable`：非空清单，每项同时给 `cause`（为什么不可消除）与 `measuredShare`（实测占比）。

**它是「不可消除的下界」，不是「豁免额度」**：`fillRatio` 超限或结构差异超出下界，仍判 `fail`。
详见 `references/artifact-contract.md` 的 `gateReachability` 一节。

### 4. Agent 编写代码

Agent 直接维护目标工程中的 canonical UI 源码。脚本禁止生成、重写或覆盖 `.swift`、`.kt`、`.java`、`.h`、`.m`、`.xml` 和 Compose 生产文件。父组件必须真实创建并约束其子组件；画布叠层页面不得被强行串成纵向列表。

#### 4.1 写码完成后、编译之前：层级与布局静态核对（门 1）

**这一步必须在编译之前做，不要留到编译截图之后补。** 层级关系与布局关系
（`parentIndex` / `parentHops` / `positioningContextIndex`，以及逐条关系的 `kind` 与位置基准 `of`）
**全部是静态可判的**：`scripts/check_layout_proportions.py` 只读计划 JSON 与源码文本，
不编译、不起浏览器、秒级返回。把它排在编译之后，等于让每一次「声明 `pinned` 却写成比例系数」
「声明 `fixed` 却写成探针设备推导值」「`parentIndex` 指向的父视图根本不存在」这类错误，
都先付一次编译 + 装机 + 截图的成本才被发现，而发现后还要再付一次。

```bash
# 门 0：计划自检（还没有源码可查时先跑这个，确认 layoutProportions 自身完整）
python3 scripts/check_layout_proportions.py --plan <run>/ui-implementation-plan.json --plan-only

# 门 1：层级与布局关系逐条核对（写码完成后、编译之前）
python3 scripts/check_layout_proportions.py --plan <run>/ui-implementation-plan.json \
    --source <原生源码根>
```

`violations == 0` 才允许进入编译（`ambiguousLiterals` 是 ≤48pt 的待人工确认项，不计违规）。
有违规就改源码后重跑本门 —— **这一步的迭代不消耗编译，也不计入 `feedback-loop` 的轮次**。

**宽度轴的自适应检查也归在本门**，理由完全相同：封顶原语在不在、有没有出现方向锁与
`UIScreen.main.bounds`、`sw600dp` 资源目录在不在，全是静态可判的。把它留在编译之后，
等于为一次「平板上单列拉满 1024pt」付一次编译装机截图的成本 —— 而截图还**证明不了**它
（元素没越界、尺寸也没变，像素 diff 看不出来）。

```bash
# 宽度轴：门 0（声明自检）与门 1（声明 ↔ 源码逐条核对）
python3 scripts/check_adaptive_layout.py --plan <run>/ui-implementation-plan.json --plan-only
python3 scripts/check_adaptive_layout.py --plan <run>/ui-implementation-plan.json \
    --source <原生源码根>
```

两门的 `violations == 0` 都满足才允许进入编译。

本门的 stdout 是**人类可读摘要**（关系计数、违规逐条、待判清单）。要拿结构化结论
（逐条 `kind` / `file` / `line` / `relation`）就加 `--output <path>` 写 JSON —— 不要按 JSON
去解析 stdout。退出码：`0` = 通过，`1` = 存在违规，`2` = 用法或读取错误。

### 5. 编译、运行和截图

按目标模式使用 Xcode 或 Gradle 编译，运行目标设备/模拟器，保存实际截图、日志、约束/布局错误和测试结果。iOS 与 Android 必须分别验证，不能用一个平台的通过推断另一个平台通过。

**这一门只负责静态判不了的事**：能不能编译、能不能启动、运行期几何
（`UIScrollView.contentInsetAdjustmentBehavior` 自动注入的 safe-area inset、系统栏与灵动岛的实际几何）
和运行期交互（覆盖式装饰子视图会不会吞掉点击）。层级与布局关系已由门 1 保证，
所以本门失败时的归因不会发散到「是不是基准错了」。

**编译与截图在整个验证阶段只应发生一次**：布局类迭代已由门 1 用秒级静态核对吸收，
这里留在「一次取证」的位置上。若在这里发现布局类违规，说明门 1 没跑或没跑全 ——
补跑门 1，而不是继续在这里试错。本门只剩下无法静态证明的事：能不能编译、能不能启动、点击可用。

本门的验收清单（**每一项都必须真跑，不能靠读代码推断**）：

1. 编译 0 error，日志与测试结果落盘到 `actual/`。
2. 目标设备截图，像素尺寸与基准一致；不一致时 diff 不具证据效力。
3. **交互可用性必须真点**：像素 diff **证明不了**点击可用 —— 覆盖式装饰子视图
   （描边环、蒙版、渐变层）一旦 `userInteractionEnabled` 变 YES 就会吞掉卡片手势，
   而截图完全看不出来。做法是按归一化坐标点击并并行抓统一日志：

   ```bash
   xcrun simctl spawn <udid> log stream --style compact \
       --predicate 'eventMessage CONTAINS "IHEREFOR_EVENT"' > /tmp/events.log &
   xcodebuild test -project <工程> -scheme <scheme> -destination id=<udid> \
       -derivedDataPath <run>/DerivedData
   ```

   坐标按 `x * scaleX`、`y * scaleY + originY` 从设计值算（用 `canvas_map.py`，不要手写），
   并且**是机型专用**的。用坐标而不是 accessibilityIdentifier：`UIImageView` / `UILabel`
   默认不是 accessibility element，只设 identifier 未必检索得到，坐标点击走真实 hitTest。
   用例写在既有的 UI 测试 target 里（已在 target 中，不必改工程文件，风险最低）。
4. 运行期几何：`contentInsetAdjustmentBehavior` 是否自动注入了 safe-area inset、
   系统栏与灵动岛的实际几何，都要进 `diff/` 与 `review.json`。

### 6. 视觉修复循环

比较 HTML 基准与目标 App 截图，按区域分析偏移、尺寸、字体、颜色、叠层、裁剪、圆角、阴影和资源差异。比较器给出的差异是三类，**只有前两类参与放行判定**：

| 类别 | 含义 | 判定 |
|---|---|---|
| `structuralRatio` | 强边在两张图里对不上 —— 几何错位、尺寸变化、间距改错 | 超过 `--max-structural-ratio` 判 `fail`；**但仍在计划声明的 `gateReachability.expectedStructuralFloor` 内且 fill 未超限时，判 `pass-with-review`** |
| `fillRatio` | 平坦区颜色不同 —— 填充色/背景色/文字颜色写错、整块缺遮罩 | 超过 `--max-fill-ratio` 判 `fail`（**下界不为它开口子**） |
| `textureRatio` | 几何一致、只是像素值不同 —— 字体栅格化、抗锯齿、次像素相位差 | **不参与判定**（这是噪点） |

两类在放行形态上**不对称**：`fillRatio` 超限一律 `fail`（颜色写错永远是缺陷）；`structuralRatio`
超限时先判它是不是文字类的**物理下界**（见「目标实现计划」的 `gateReachability`），是则按声明的
下界放行并做量化归因。详见 [references/artifact-contract.md](references/artifact-contract.md) 的三分法一节。

不要用 `changedRatio` 判断能不能放行：它把三类混在一起，于是抗锯齿多的页面（HTML 用 Web 字体、App 用系统字体）永远撞上限，而真正错位的图只要背景色接近也可能因为纹理差异低而侥幸通过。结论必须带**区域级**明细（`regions`），整页一个数字看不出偏差随 y 的变化。

但 `regions` 是**网格切块**（字段是 `row` / `col` / `box`），它只能告诉你「差在哪一带」，
说不出「差在哪个控件」。放行结论要的是后者，所以每次比较都要同时给出 `attribution`：

```bash
python3 scripts/compare_reference.py --reference <page>/reference/reference.png \
    --actual <run>/actual/app.png --page-facts <page>/reference/page-facts.json \
    --output <run>/diff/comparison.json
```

`attribution` 把差异像素按**最小包含元素优先**互斥归属到具名区域，保证
`Σ(区域 changedPixels) + unattributed == 整页 changedPixels`（互斥且穷尽）。它另外给出
`declaredUnsupported` 与 `residual` —— **`residual`（扣除已声明差异后的剩余值）才是
`review.json` 该引用的数字**：整页比值里混着已声明为 `unsupported` 的差异（系统状态栏、
无法等价映射的 CSS 特性），不扣除就说不清「还剩多少是真缺陷」。
`--page-facts` 缺失或事实表没有 `rectInReference` 时，`attribution.status` 记
`insufficient-evidence` 并说明原因，**不冒充**「归因完成」。

Agent 修改 canonical 源码后重新编译和截图，直到达到任务指定阈值，或把无法自动修复的差异明确记录为 `needs-review`。每轮必须记录 before/after 截图、diff 数值或未运行原因、受影响区域、事实来源和下一步动作，禁止只凭肉眼说"基本一致"。

用户判定 diff 不合格后，必须进入可恢复的修复迭代：读取上一轮产物、记录用户反馈和差异分类，创建新的 run（保留 `parentRunId`），只修改 canonical 源码，重新 build/test/截图/diff，并按区域回归。详细字段、停止条件和 `review.json` schema 见 [references/feedback-loop.md](references/feedback-loop.md)。

### 7. 交付闸门

只有在所选目标模式的编译、资源接入、测试和视觉比较都通过时才标记 `deliveryReady=true`。缺失基准、编译失败、测试未运行、存在未处理 `unsupported` 或重大视觉差异时，只能标记 `pass-with-review`、`fail` 或 `not-run`。

**闸门是 7 项还是 8 项，取决于计划有没有声明 `adaptiveLayout`。** 声明了就多一项
`adaptiveAudit`（多宽度采样的几何契约审计），且它的取值受 `diff/adaptive-audit.json` 约束：
审计判 `fail` 时闸门不得记 `pass`，与「对齐审计 needs-review 却 visualDiff=pass」是同一类
自相矛盾。未声明的计划不要求该项 —— 但那样也就等于明确声明了「本页只交付手机档」。

`visualDiff` 这一项**不能凭手写凑**，它的取值受 `diff/` 的证据约束：

- 比较器判 `fail` ⇒ `visualDiff` 不得为 `pass`；
- 比较器判 `pass-with-review` ⇒ 默认原样记 `pass-with-review`，**唯一例外**是
  `reason == "structural-within-declared-floor"`（文字密集页的物理下界，已在计划里声明并量化归因）
  —— 此时记 `pass` 才是诚实的。

这条例外是必需的：没有它，比较器按下界放行了，`deliveryReady` 却永远推导为 `false`，
文字密集页就永远交付不了。反过来，把 `structural-diff-above-warn` 之类写成 `pass`，校验脚本会拦下。
**这是 `visualDiff` 升格的唯一例外**，修复闭环与其他文档都不得另立口径。

## 输出证据

多页面任务必须先在项目根创建 `.ihereforUI`。产物结构以 [references/artifact-contract.md](references/artifact-contract.md) 为唯一事实来源，生命周期、索引和恢复规则见 [references/project-management.md](references/project-management.md)。可用 `scripts/init_ui_workspace.py` 初始化目录与索引；它只创建中间产物目录，不修改生产源码。

每个页面、每个目标模式、每次运行至少产出（缺一即不合规）：

- `run.json`、`review.json`、`delivery-gate.json`
- `ui-implementation-plan.json`、`resource-policy.json`
- `runtime-device.json`；iOS 目标另需 `ios-environment.json`
- `actual/`：目标 App 截图、编译/测试日志
- `diff/`：整页与区域差异摘要（含 `structuralRatio`/`textureRatio`/`fillRatio`、阈值与两张输入图的像素尺寸）、`alignment.json`（元素级位移证据）

`diff/` 里的放行类结论（`status` 为 `pass` 或 `pass-with-review`）必须自带 `structuralRatio` 与非空的 `regions`；只有 `changedRatio` 的结论不足以放行，校验脚本会拒绝。

页面级冻结基准（`reference/reference.png`、`page-facts.json`、`browser-meta.json`、`approved.json`）与跨页面汇总（`.ihereforUI/reports/`）不放在 run 目录内。`visual-review.json`、`manifest.json` 和 run 级 `assets/` 已废弃，映射关系见契约。

每次写完 run 必须用 `scripts/validate_run.py --run <run-dir>` 自检；`deliveryReady` 只由闸门脚本推导，不得手写覆盖。禁止把多个页面的产物放在同一目录、覆盖历史 run，或以聊天上下文代替索引。

## 人工验收入口

skill 根目录的 `index.html` 是一个纯静态差异查看器（无需服务器、无外部依赖）：用浏览器打开后选择包含 `.ihereforUI` 的项目目录，它会递归扫描各页面各 run 的 `diff/*.json`，并排展示 reference 与 actual 截图、差异数值与闸门状态。这是用户判定「合格 / 不合格」的入口；判定不合格后的修复流程见 [references/feedback-loop.md](references/feedback-loop.md)。

## 字段速查

改产物前先查这张表，不要在正文里逐段找字段名。完整 schema 见 [references/artifact-contract.md](references/artifact-contract.md)。

| 产物 | 关键字段 |
|---|---|
| `page-facts.json` | `elements[]`：`rect`（CSS px）/ `rectInReference`（基准图像素，比对只用它）/ `parentIndex`·`parentHops`·`positioningContextIndex`（层级）/ `ownText`·`ownsText`（文本元素判定）/ `primaryFont`·`fontsResolved`·`textMetrics`；`images[].alphaBounds` |
| `browser-meta.json` | `fontMeasurement`（`method` / `glyphCountScope`）/ `fontMeasurementCoverage` / `fontJoin.ok`（`false` ⇒ 整份字体数据作废）/ `fontProbe` |
| `ui-implementation-plan.json` | `canvasTransform.policy` + `coordinateMapper.forward`·`inverse`（**测量用**）；`layoutProportions.regions[].basis`·`parentIndex` + `relations[].kind`·`of`·`why` + `forbiddenLiterals`（**实现用**）；`adaptiveLayout.windowSamples[]` + `regions[].widthPolicy`·`maxContentWidth` + `firstLevelWidthClass` + `forbiddenAdaptations`（**宽度轴**）；`runtimeRisks`（`interactionCoverage` / `scrollInset` / `systemBars` / `fontAvailability` / `windowSizing`）；`gateReachability.expectedStructuralFloor` + `unavoidable[].cause`·`measuredShare`；`unsupported` |
| `runtime-device.json` | 运行时尺寸 API 返回值、根 view bounds、截图像素尺寸、device scale |
| `adaptive-targets.json` | `samples[].id`·`widthClass`·`required`·`windowBoundsPoints`·`geometry`；`deviceFamily` |
| `diff/comparison.json` | `structuralRatio` / `fillRatio` / `textureRatio` / `changedRatio`；`regions[]`（`row`·`col`·`box`）；`attribution.status`·`declaredUnsupported`·`residual`·`unattributed` |
| `diff/alignment.json` | `domVsReference`（基准是否可信）/ `referenceVsActual`（App 是否对齐）；`coverage.excludedLowCoverage`；`offsetFit`；`crossCheckRequired`·`crossCheck` |
| `diff/font-chain.json` | 逐元素「声明族 vs 运行时族」比对结果与替换判定 |
| `diff/adaptive-audit.json` | `checks.sizeInvariance`·`insetPreservation`·`noOverflow`·`maxContentWidth`·`touchTarget`·`noLetterbox`·`continuity`·`sampleCoverage`；`status`·`violations` |
| `review.json` | `runId`·`parentRunId`·`decision`·`feedback`·`observations`·`hypotheses`·`changes`·`verification`·`nextAction` |
| `delivery-gate.json` | 7 项基础闸门状态（声明 `adaptiveLayout` 时为 8 项，多一项 `adaptiveAudit`）、`unsupported.count`、`deliveryReady`（只由脚本推导） |

三个容易混的点：

- **`kind` 五档**：`fixed` / `pinned` / `proportional` / `intrinsic` / `centered`，见「尺寸与定位契约」。
- **`basis` 与 `of` 不是两个概念**：region 级的位置基准字段叫 `basis`，relation 级叫 `of`，两者都指向**直接父视图**（`"root"` 仅在直接父即整屏画布时用）。不要因为名字不同就写成两个基准。
- **三轴不是三套字段**：尺寸轴与位置轴都在 `layoutProportions` 里，宽度轴在 `adaptiveLayout` 里。`canvasTransform` 是**测量桥**，不参与这两者。


## 参考资料

- 尺寸与位置两条轴的完整规范、推演与反例清单：`references/sizing-and-positioning.md`
- 平板与宽屏自适应的完整规范（宽度轴、六模式原语、预留 hook、几何审计）：`references/adaptive-layout.md`
- 浏览器启动、隔离 session、字体/资源稳定化和截图契约：`references/browser-runtime.md`
- 六种输出模式的技术边界和选择规则：`references/target-modes.md`
- 页面事实表、实现计划和交付证据 schema：`references/artifact-contract.md`
- 用户判定不合格后的修复闭环、停止条件：`references/feedback-loop.md`
- 产物生命周期、索引与恢复规则：`references/project-management.md`
- Lanhu MCP 调用顺序、缓存、版本与失败处理：`references/lanhu-input.md`
- iOS 工程与设备环境探测：`references/ios-environment.md`
- 既有项目接入的工程审计与接入计划：`references/existing-project-integration.md`
- 资源复用、语义命名与代码分层：`references/resource-and-code-quality.md`
- 分阶段落地计划：`references/execution-plan.md`

## 验证脚本一览

| 脚本 | 作用 | 何时必须跑 |
|---|---|---|
| `scripts/canvas_map.py` | 唯一的坐标换算入口，正向 + 逆向 + 默认 `fit` 策略；`to_ratios` / `axis_deviation` 给出比例形式与模型偏差 | 任何需要换算坐标的分析之前；改坐标逻辑后跑 `--self-test` |
| `scripts/render_reference.mjs` | 确定性渲染基准图与事实表（含 `rectInReference`、`alphaBounds`、`textMetrics`、运行时字体） | 第 1 步建立基准 |
| `scripts/normalize_lanhu_fonts.py` | 渲染前把 Lanhu 导出的「系统不存在族名」替换成真实族名（`AvenirLT-*` → `Avenir-*`），避免基准图带着回落字体（Times）自洽地错 | **下载后、渲染前必做**（第 1 步） |
| `scripts/lanhu_design_facts.py` | 把 `lanhu_get_design_document` 返回体解析成紧凑设计事实摘要（父视图归属 / 字号字体文本颜色 / 描边填充阴影），供实现计划直接引用而非从渲染 DOM 反推 | 第 1 步调用 `lanhu_get_design_document` 之后 |
| `scripts/layout_proportions.py` | 把事实表位置转成 `layoutProportions` 约束规格（尺寸是常量、位置相对直接父视图），并列出「探针设备推导值」禁止清单 | 第 2 步写实现计划时；缺它就没法核对「有没有写成探针设备上的固定 pt」 |
| `scripts/check_layout_proportions.py` | 计划驱动地核对源码有没有照计划声明的 `kind` 实现；`--plan-only` 只校验计划 | **门 0（`--plan-only`）在写码前，门 1 在写码完成后、编译之前**；改了布局代码就重跑。纯静态（只读计划与源码文本），秒级，不编译不起浏览器 |
| `scripts/check_adaptive_layout.py` | 宽度轴静态核对：`adaptiveLayout` 声明自身完整，且源码里有封顶原语、无方向锁 / `UIScreen.main` / 屏幕系数；`--plan-only` 只校验计划 | 同上，与布局约束同属门 0 / 门 1；声明了 `adaptiveLayout` 就必须跑。纯静态，秒级 |
| `scripts/compare_reference.py` | 像素比较，输出结构/纹理/填充三分、网格 `regions`，以及具名区域 `attribution`（含 `declaredUnsupported` 与扣除后的 `residual`） | 每次截图后 |
| `scripts/audit_alignment.py` | 元素级对齐审计，区分「基准不可信」与「App 不对」；框内近乎空白的图片/容器元素判 `insufficient-evidence`，不参与位移与比例拟合 | 每次截图后；尺寸一致也必须跑 |
| `scripts/audit_fonts.py` | 字体链审计：逐元素比对「CSS 声明的族」与「运行时实际用上的族」，判出静默字体替换 | 每次截图后；`alignment.json` 说「问题在 App 侧」时更要跑 |
| `scripts/audit_adaptive.py` | 多宽度采样的**几何**契约审计（八项：`sampleCoverage` / `sizeInvariance` / `insetPreservation` / `noOverflow` / `maxContentWidth` / `touchTarget` / `noLetterbox` / `continuity`），**不做像素比对** | 交付前；声明了 `adaptiveLayout` 就必须跑，结果落 `diff/adaptive-audit.json` |
| `scripts/validate_run.py` | run 产物契约校验，交叉核对闸门与证据；带 `--source` 时连同布局约束与宽度轴一起判 | 每次写完 run |

脚本级回归见 `scripts/tests/run_all.sh`（不需要 LLM，CI 每次跑）；Agent 行为红线见 `evals/README.md`。
