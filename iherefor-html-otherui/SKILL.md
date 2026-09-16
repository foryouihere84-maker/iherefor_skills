---
name: iherefor-html-otherui
description: 将 Lanhu 设计稿映射为 SwiftUI、UIKit Swift、UIKit Objective-C、Jetpack Compose Kotlin、Android Views Kotlin 或 Android Views Java 原生 UI。以 lanhu-mcp 的 design overview（nodes[].bounds 绝对坐标）为主链路生成布局，样式恒量与切图以 inspect_design_region / export_design_assets 为准，编译通过为硬门槛。当用户要求从 Lanhu 落地 iOS/Android 原生页面时使用。
---

# Lanhu 设计稿到多平台原生 UI

本 skill 面向「视觉还原优先」的 Lanhu 页面落地。几何坐标以 `lanhu-mcp` 的 `get_design_overview` 返回的
`nodes[].bounds`（`{x,y,width,height}` 绝对坐标）为主链路，样式恒量以 `inspect_design_region` 的 `raw_style`、
切图以 `export_design_assets` 为准；目标是由 Agent 针对所选原生技术栈
编写生产代码，并**至少通过目标平台编译**。渲染 DOM 反推几何是备用链路（`bounds` 拿不到时才回退）。

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

1. **几何坐标以 `lanhu_get_design_overview` 的 `nodes[].bounds`（几何权威）为主链路**（`{x,y,width,height}` 绝对坐标，
   节点自带你 `parent_id` 父子层级）。渲染 DOM 读位置是**备用链路**——`bounds` 拿不到或不可信时才回退。
   `inspect_design_region` 的 `raw_style` 是样式恒量（字号/颜色/圆角/描边）与切图的权威来源。**`bounds` 管几何、`raw_style` 管样式，分工互补。**
2. Agent 负责语义理解、组件边界、目标技术栈实现。脚本可以提取事实、保存资源、编译和校验，但不得生成或覆盖生产 UI 源码。
3. 不得因为某个 CSS/JS 特性无法等价映射而静默删除；必须写入 `unsupported` 并进入交付报告。
4. 目标平台可以使用不同的组件树和布局策略；相同的是视觉目标，不是源代码形状。
5. 生成代码必须经过目标平台**编译通过**，不能以「代码生成完成」代替完成。
6. **约束策略不是「整页等比缩放」，而是两条独立的轴：尺寸固定、位置相对父视图。** 完整口径见下一节。

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
  **不得**写成探针设备上的绝对坐标（如 `x = 83`、`y = 132`）—— 那在换台设备时就错。
- 第一层的**尺寸仍是 `fixed`**（组件尺寸恒等于设计稿，绝不缩放）；自适应的是**位置**，不是尺寸。
- 第一层 → 第二层（及更深）的**相对关系固定**：第二层的位置基准是它的直接父视图（某个第一层元素），
  不是页面。只有第一层这一档按页面比例，往下不再套。
- **两条轴不共享同一个收口**：水平位置受**宽度档**收口（宽档改由 `widthPolicy` 重排，见下一节），
  但**垂直位置在所有宽度档下都按页面高度比例重排**——垂直轴的参考要素是**高度不是宽度**。
- 背景（`.page` 外框）按 `pinned + fullBleed` 四边铺满，与第一层子视图按比例重排是两回事。

`scripts/layout_proportions.py` 是**辅助工具**：它把事实表（`bounds`）+ 设备尺寸**转成 `layoutProportions` 声明片段**，
供 Agent 参考；**Agent 负责把它合并进 `ui-implementation-plan.json` 并逐条人工核对 `kind`/`basis`/`of`**，
不是「脚本生成 = 计划完成」。`scripts/check_layout_proportions.py` 按声明逐条核对源码，**计划驱动而非正则扫描**。

判定分两档：数值 > 48pt 的字面量不可能是手选的设计常量，判违规；≤ 48pt 与常见设计常量无法区分，
只列进 `ambiguousLiterals` 待人工确认，不计入违规。完整推演见 [references/sizing-and-positioning.md](references/sizing-and-positioning.md)。

## 宽度轴与平板适配（强制）

上两节只保证「换设备不崩」，回答不了第三个问题：**父视图宽到 1024pt 时，内容怎么收敛？**
缺这一轴时，`393×852 → 402×874` 上成立的那条「第一层位置按页面比例」推到 1024pt 会给出
**错的**结果：位置 ×2.6、尺寸 ×1，卡片左起 33pt 变 86pt、宽度仍是 327pt、右侧空出 611pt，
间距 13pt 被拉成 285pt。所以平板适配要补的不是「iPad 布局代码」，而是**宽度轴**。

**布局是窗口宽度的连续函数，不是「手机一套、平板一套」的两张快照。** iPad 不是一个尺寸：
全屏竖 1024×1366pt、横 1366×1024pt，分屏 1/3 与 Slide Over 回落到 ~320pt。按**宽度档做决策**，
但布局必须对档位之间的任意宽度都不崩。

实现计划必须给出 `adaptiveLayout`，至少包含四个采样（`phone-compact` /
`tablet-regular-portrait` / `tablet-regular-landscape` / `phone-regular-landscape`）、
每个区域的 `widthPolicy`、以及非空的 `forbiddenAdaptations`：

- `widthPolicy` 六档 —— `full-bleed` / `max-content-width` / `centered-column` / `grid` /
  `pane` / `stacked`。**`stretch-full-width` 不在枚举里**：单列内容拉满 1024pt 是本契约要拦的
  头号问题。「拉满」必须由 `full-bleed` 显式声明，不能是默认行为。
- `max-content-width` / `centered-column` 必须给 `maxContentWidth.value`（设计常量，
  600~700pt 量级，**不随窗口缩放**）与 `reason`；`grid` 必须给 `columnCount` 的三档
  且单调不减。
- **`firstLevelWidthClass` 缺省 `compact`**：只有**水平位置**受这一档收口；regular / medium /
  expanded 档下第一层水平位置改由 `widthPolicy` 重排。**垂直位置不受这条收口**。

三条交界规则：

1. **宽度轴只改「容器宽度」与「第一层位置」，不改任何尺寸。** 字号、行高、圆角、描边宽度、
   最小点击区（≥44pt / 48dp）在**同一平台的各个宽度档之间**逐字相同。
   **只有一套稿时**，「平板上字大一点更好看」是错的 —— 设计稿只有一套排版。
   **双稿时**，`xx` 与 `xx-iPad` 是两套并列的独立参考，跨稿尺寸照稿各自取值；
   出现差异必须逐档声明在 `adaptiveLayout.sizeVariants[]`（带 `basis`/`why`）。
2. **第一层水平位置比例规则只在 `compact` 档成立**，垂直位置始终按页面高度比例。
3. **窗口 ≠ 屏幕。** 分屏与自由窗口下 `UIScreen.main.bounds` / `DisplayMetrics.widthPixels`
   返回的是**整块屏**，不是你的窗口。iOS 用 `view.bounds` / `windowScene`，Android 用
   `WindowMetrics` / `WindowSizeClass`。

**「预留」的含义是「接口在、值仍是手机值」，不是第二套布局。** 六模式各自必须留的 hook 见
[references/adaptive-layout.md](references/adaptive-layout.md)。

```bash
# 门 0：宽度轴声明自检
python3 scripts/check_adaptive_layout.py --plan <run>/ui-implementation-plan.json --plan-only
# 门 1：声明与源码逐条核对（写码完成后、编译之前）
python3 scripts/check_adaptive_layout.py --plan <run>/ui-implementation-plan.json \
    --source <原生源码根>
```

`scripts/audit_adaptive.py` 的多宽度几何审计（`sizeInvariance` 等八项）在声明了 `adaptiveLayout`
时必须跑。完整规范见 [references/adaptive-layout.md](references/adaptive-layout.md)。

## 可移植性契约（强制约束）

本 skill 必须能在任意 coding agent / CLI 宿主下运行，**不得绑定任何具体宿主**。改写本 skill 时遵守：

1. 脚本、参考文档、工作流中不得出现宿主产品名，也不得假定某个宿主专有的命令、配置路径或配置格式。
2. 与宿主交互只允许通过通用形态表达：**MCP 的 stdio server 注册**（`command` + `args` + `env`）、**JSON 的 `mcpServers` 配置**、**TOML 的 `[mcp_servers.*]` 配置**、以及**标准命令行**。
3. 「去哪里找宿主的注册」属于**数据**，不属于逻辑：候选位置集中在 `scripts/mcp-registries.json`；表里没有的宿主用 `scripts/check_lanhu_mcp.py` 的 `--mcp-config` / `--registry-cmd` / `--registries` 显式指定，**不得为此修改脚本**。
4. 运行时环境（Python、Xcode、Android SDK 等）按能力探测，不按宿主假设。
5. 评测运行器的引擎选择（`evals/eval.yaml` 的 `engine.name`）属于评测工具自身的设置，不是本 skill 的依赖。
6. 新增文档或脚本时，若确实必须提到某个宿主的名字，只允许出现在 `scripts/mcp-registries.json` 这类适配器数据中，并附上「可替换/可删除」的说明。

## Lanhu MCP 输入

用户提供 Lanhu 链接时，必须先使用已配置的 `mcp__lanhu_mcp` 服务获取设计数据：
几何用 `lanhu_get_design_overview` 的 `nodes[].bounds`（几何权威），样式恒量用
`lanhu_inspect_design_region` 的 `raw_style`（权威），整页 HTML/CSS 参考用
`lanhu_get_ai_analyze_design_result`（**Legacy，仅参考**），切图用 `lanhu_export_design_assets`。
**⚠️ 工具名以 `references/lanhu-input.md` 开头的「工具名对照表」为准**——本 skill 早期版本写过的
`lanhu_get_dds_schema`/`lanhu_download_design`/`lanhu_get_design_document` 等名已不适用，不要按旧名找工具。
严格调用顺序与失败处理见 [references/lanhu-input.md](references/lanhu-input.md)。

若 MCP 未安装、未注册或凭据未配置，必须先运行 `scripts/check_lanhu_mcp.py` 并按输入参考引导安装/注册；
这是阻塞条件，不能绕过 MCP。安装引导不得打印或持久化 Lanhu 凭据。

## 每个阶段该读/写哪个文件（速查，回答「我现在该读什么」）

上下文压缩、Agent 换手、或「不知道该看哪个文件」时，按这张表定位。**不要凭对话记忆，
不要跨阶段混读。** 完整生命周期见 [references/project-management.md](references/project-management.md)。

| 阶段 | 该读入的文件 / 调用 | 该写出的文件 |
|---|---|---|
| 1. 发现与输入 | `lanhu_get_designs`→`lanhu_get_design_overview`→`lanhu_inspect_design_region`（样式）→`export_design_assets`（切图） | `reference/dds-schema.json`、`source/` |
| 2. 建事实表/计划 | `reference/dds-schema.json`（几何）+ `source/` CSS（样式恒量） | `ui-implementation-plan.json`（layoutProportions + typeFacts） |
| 3. 写码（门 0/门 1） | **只有** `ui-implementation-plan.json` 的 `relations[].kind` | 生产源码 |
| 4. 编译（门 2） | `ios-environment.json`（workspace/scheme/udid） | `actual/` 编译日志 |
| 5. 交付闸门 | `delivery-gate.json` + `validate_run.py` 推导 | `delivery-gate.json`（脚本推导，勿手写） |
| 6. 换手/恢复 | `project.json`→`page.json`→`status.json`→最新 run 的 `run.json`/`review.json`（按 run ID，不靠 mtime） | — |

**三条铁律**（违反会直接导致「不知道读什么」）：

1. **几何 vs 样式不混**：位置/尺寸/父子关系只看 `dds-schema.json` 的 `nodes[].bounds`；
   字号/颜色/圆角/描边只看官方 CSS 或 `inspect_design_region` 的 `raw_style`。两者互不替代。
2. **工具名以 lanhu-input.md 的对照表为准**：本 skill 早期写成 `lanhu_get_dds_schema`/`lanhu_download_design`/
   `lanhu_get_design_document` 的名字已废弃，实际是 `lanhu_get_design_overview`/`lanhu_inspect_design_region`/
   `lanhu_get_ai_analyze_design_result`/`lanhu_export_design_assets`。**先看对照表再调工具，别按旧名搜。**
3. **分页拿全 + 深层元素走 inspect**：`get_design_overview` 是分页接口（`limit` 1~60、默认 30，单页最多 60 个节点），
   节点多的页面只说一页会漏掉导航/按钮/进度条/色卡等深层元素——**必须循环 `offset` 直到 `truncated=false` 拿全所有
   `nodes[]`**；要看某个区域的完整 nested nodes + 样式再配合 `lanhu_inspect_design_region`。这是「元素找不到」的头号来源。

## 资源与代码质量

在复制资源或编写代码前，必须读取 [references/resource-and-code-quality.md](references/resource-and-code-quality.md)。先扫描并复用目标工程已有资源体系；没有既有约定时才使用平台默认目录。**切图归位是硬禁令**：切图/位图/SVG 严禁散落项目根目录或与源码混放，iOS 一律进 `Assets.xcassets/<业务域>/<name>.imageset/`（含 `Contents.json` 与 1x/2x/3x），Android 一律进 `res/drawable(-density)*`；违反即 `needs-review`，细节见「资源归位硬约束」。**注意：MCP 拿不到无损三倍率**，切图只有一张原图（通常 2x），`scale_urls` 里的 3x 是上采样假高清，禁止用它凑 imageset 的 3x 坑——真 3x 只能来自 SVG 或蓝湖按 3x 重新导出，详见「切图倍率的真相与正确获取」。资源必须按使用场景语义命名，不能把 `img_0` 等来源编号作为生产名。生成代码必须按 screen/section/style/resources 分层，所有按钮和可点击元素都要连接到命名明确的点击处理空函数。

## 既有项目接入

如果目标工程不是空项目，或用户要求二次开发/新增页面，必须先读取 [references/existing-project-integration.md](references/existing-project-integration.md)，完成工程审计并生成 `.ihereforUI/integration/project-audit.json`、`.ihereforUI/integration/integration-plan.json` 及页面级接入计划。计划批准前不得写入生产代码；文件名、模块、导航、依赖、资源、状态、测试和回滚方式都必须先列明。

## 持续视觉事实（强制约束）

以下事实必须贯穿发现、计划、编码全过程，不能只在首次分析时阅读后凭记忆实现：

1. 资源位置与层级：记录每个图片/SVG/背景资源的 URL、原始尺寸、目标坐标、z-index/stacking context、裁剪和 transform，并建立原生资源映射。每张图片还要记录其**非透明内容 bounds**（`alphaBounds`），因为「frame 对了」不等于「内容对了」。
2. 元素几何：从 `lanhu_get_design_overview` 的 `nodes[].bounds`（`{x,y,width,height}` 绝对坐标）读取每个区域和关键元素的几何——这是「组件该在哪」的权威事实来源；`bounds.x/y` 是位置、`width/height` 是尺寸、`parent_id` 是父子归属。`bounds` 缺失时才用备用链路的 DOM 实测值。深层元素（导航/按钮等被编组折叠的）用 `lanhu_inspect_design_region` 拿。
3. 视觉样式：记录字号、行高、颜色、透明度、渐变、阴影、圆角、overflow；来源是 `inspect_design_region` 的 `raw_style`（权威），legacy 的官方 HTML/CSS（`lanhu_get_ai_analyze_design_result`）仅作参考。无法等价表达的属性写入 `unsupported`。
4. 画布关系：保存设计稿画布尺寸、目标设备 bounds、`fit` 策略（scale、letterbox、inset）。禁止直接复制另一设备的绝对像素坐标。

这些数据应落在 `dds-schema.json`（bounds 几何）、`ui-implementation-plan.json`、`review.json` 和 `resource-policy.json` 中，并能从原始设计节点追溯到原生视图。上下文压缩或 Agent 换手后必须重新读取这些产物，不能依赖对话记忆。

## 顶部系统区域与安全区

状态栏、刘海、Dynamic Island、导航栏和手势区域属于截图画布的一部分，不能默认当作页面外部留白。Agent 必须先确认页面是否绘制到顶部系统区域，再为每个目标平台记录 `systemBars` 策略：

- `underlap`: 页面背景/图片延伸到状态栏或导航栏下方，前景内容使用显式 inset；
- `inset`: 页面整体从安全区之后开始，只有在设计稿确实保留空白时使用；
- `mixed`: 背景 underlap、文字和交互控件 inset。

iOS 必须显式处理 `edgesForExtendedLayout`、`extendedLayoutIncludesOpaqueBars`、safe-area inset、状态栏样式和 home indicator 区域。尤其要检查 `UIScrollView` 的 `contentInsetAdjustmentBehavior`。Android 必须显式处理 `WindowInsets`/`setDecorFitsSystemWindows`、status/navigation bar 对比度和 edge-to-edge。

## iOS 工程与设备环境

任意 iOS 目标模式必须先读取 [references/ios-environment.md](references/ios-environment.md)，并运行 `scripts/discover_xcode_environment.py` 探测 `.xcworkspace/.xcodeproj`、scheme、模拟器和真机。禁止凭记忆选择 `-project`、`-workspace`、scheme 或 destination；探测结果必须进入页面 run 的 `ios-environment.json`。

## 强制 Agent loop

第 5 步（编译）是**验证阶段**，按「静态门先跑、动态门只跑一次」组织：

| 门 | 位置 | 成本 | 判什么 |
|---|---|---|---|
| 门 0 | 第 3 步写计划时 | 纯静态，秒级 | 计划自身完整：`layoutProportions` 的 `basis` / `parentIndex` / `kind` / `of` 是否齐全 |
| 门 1 | 第 4 步写码完成后、第 5 步编译之前 | 纯静态，秒级 | 层级与布局关系是否照计划实现（`check_layout_proportions.py --source`） |
| 门 2 | 第 5 步 | 需编译，约 10 s / 轮 | 能否编译通过 |

**门 1 是唯一被前移的门**：层级与布局关系全部静态可判，把它的迭代留在编译之前，
编译就只需要发生一次。门 1 直接给出 `文件:行号` 与规则名，把「看图猜」换成「读一条定位精确的告警」。

### 1. 发现、设备探测

1. 确认设计稿（image_id / 版本）与页面状态；按 [references/lanhu-input.md](references/lanhu-input.md) 走固定调用链。
2. **（主链路）调用 `lanhu_get_design_overview` 取 `nodes[].bounds`（几何权威）几何事实**，把**返回体原样落盘**到 `reference/dds-schema.json`——`dds-schema.json` 字段就是 MCP 的 `bounds`/`parent_id`/`node_type`/`name`/`asset_ids`，**不需要二次转换或脚本生成**。
3. **（样式与切图）调用 `lanhu_inspect_design_region` 拿样式恒量（raw_style），`lanhu_export_design_assets` 拿切图**到 `source/`。整页 HTML/CSS 参考可用 legacy 的 `lanhu_get_ai_analyze_design_result` 兜底。
4. 按目标模式探测运行时设备尺寸（iOS 见 [references/ios-environment.md](references/ios-environment.md)），
   写入本次 run 的 `runtime-device.json`。

### 2. 页面事实表

Agent 必须建立页面事实表：可见区域、真实叠层、组件候选、文本、图片/SVG、渐变、阴影、滚动容器、交互状态和不支持特性。**几何以 `bounds`（几何权威）为主、样式以 `inspect_design_region` 的 `raw_style` 为准**；`bounds` 缺失时用基准截图/DOM 补齐。不得直接把每个设计节点当成原生组件。页面必须按视觉区域逐一复现（hero、标题/说明、每张卡片、CTA、页脚等），每个区域列出 bounding box、资源/层级、样式事实、原生组件映射。

### 3. 目标实现计划

输出 `ui-implementation-plan.json`，至少包含目标模式、参考 viewport、组件边界、坐标系、布局策略、资源映射、可访问性标识、交互候选和 `unsupported` 项。布局策略分两段：`layoutProportions`（尺寸轴 + 位置轴）与 `adaptiveLayout`（宽度轴）。

**布局几何的权威来源，主链路是 `lanhu_get_design_overview` 的 `nodes[].bounds`（绝对坐标）。** 它直接给出「组件该在哪」：
`bounds.x/y` → 位置、`bounds.width/height` → 尺寸、`parent_id` → 父视图归属（`regions[].parentIndex`）。
**能拿到 `bounds` 就直接用它生成 `layoutProportions`，不要退回 DOM 反推几何。**
样式恒量（字号/字体/颜色/描边/圆角）以 `inspect_design_region` 的 `raw_style` 为准，legacy 的官方 HTML/CSS 仅作参考。

**只有当 `bounds` 缺失或不可信时，才降级到备用链路**：渲染 HTML、读 DOM 实测值。

**「权威有来源」是可执行约束。** 几何溯源落在 `layoutProportions`（其 `regions`/`relations` 直接引用 `bounds` 坐标），
样式恒量另由 `typeFacts` 溯源：每个文字/描边区域必须带一条 `typeFacts`，`kindSource` 指向
`inspect_design_region` 的 `raw_style`（`"html-css"`）或 fallback 的渲染 DOM（`"page-facts"`）。凡是权威来源已给出、
Agent 却写成 `kindSource: "agent-decided"` 或凭空编造常量值的，都属于可消除的推断。
字段与规则见 [references/artifact-contract.md](references/artifact-contract.md)。

`lanhu_get_design_document`（当前 MCP 已不暴露此工具，如需回看 Sketch 帧请用 `lanhu_inspect_design_region`）
是**可选辅助**，不是强制来源：它只可靠地提供「图层几何（`rect`）与描边/纯色填充」，
字号/渐变/文本语义存在系统性失真。**默认不调**，只有 `bounds` 与官方 HTML 在某处结论打架、需要回看 Sketch
原始帧时才调。

计划里还必须有一份 `runtimeRisks` —— 把「只能在运行期暴露、但现在就能决策」的风险提前写下来：
`interactionCoverage`（覆盖式装饰子视图的 `userInteractionEnabled`，默认 NO）、`scrollInset`、
`systemBars`、`fontAvailability`、`windowSizing`。每项给出决策与理由。

### 4. Agent 编写代码

Agent 直接维护目标工程中的 canonical UI 源码。脚本禁止生成、重写或覆盖 `.swift`、`.kt`、`.java`、`.h`、`.m`、`.xml` 和 Compose 生产文件。父组件必须真实创建并约束其子组件；画布叠层页面不得被强行串成纵向列表。

#### 4.1 写码完成后、编译之前：层级与布局静态核对（门 0 / 门 1）

```bash
# 门 0：计划自检
python3 scripts/check_layout_proportions.py --plan <run>/ui-implementation-plan.json --plan-only
# 门 1：层级与布局关系逐条核对
python3 scripts/check_layout_proportions.py --plan <run>/ui-implementation-plan.json --source <原生源码根>
# 宽度轴：门 0 与门 1
python3 scripts/check_adaptive_layout.py --plan <run>/ui-implementation-plan.json --plan-only
python3 scripts/check_adaptive_layout.py --plan <run>/ui-implementation-plan.json --source <原生源码根>
```

两门的 `violations == 0` 才允许进入编译。有违规就改源码后重跑 —— 这一步的迭代不消耗编译。
退出码：`0` = 通过，`1` = 存在违规，`2` = 用法或读取错误。

### 5. 编译

按目标模式使用 Xcode 或 Gradle 编译。iOS 与 Android 必须分别验证，不能用一个平台的通过推断另一个平台通过。
**编译通过是本验证阶段的唯一动态硬门槛。** 编译 0 error 后，验收进入交付闸门。

### 6. 交付闸门

只有在所选目标模式的编译、资源接入（切图归位见「资源归位硬约束」）都通过时才标记
`deliveryReady=true`。缺失源码、编译失败、存在未处理 `unsupported` 时，只能标记 `pass-with-review`、
`fail` 或 `not-run`。

**闸门是 6 项还是 7 项，取决于计划有没有声明 `adaptiveLayout`。** 声明了就多一项 `adaptiveAudit`
（多宽度采样的几何契约审计）。审计判 `fail` 时闸门不得记 `pass`。

## 输出证据

多页面任务必须先在项目根创建 `.ihereforUI`。产物结构以 [references/artifact-contract.md](references/artifact-contract.md) 为唯一事实来源，生命周期见 [references/project-management.md](references/project-management.md)。可用 `scripts/init_ui_workspace.py` 初始化目录与索引。

每个页面、每个目标模式、每次运行至少产出（缺一即不合规）：

- `run.json`、`review.json`、`delivery-gate.json`
- `ui-implementation-plan.json`、`resource-policy.json`
- `runtime-device.json`；iOS 目标另需 `ios-environment.json`
- `reference/dds-schema.json`（bounds 几何事实）、`reference/approved.json`
- `actual/`：编译日志

每次写完 run 必须用 `scripts/validate_run.py --run <run-dir>` 自检；`deliveryReady` 只由闸门脚本推导，不得手写覆盖。

## 字段速查

改产物前先查这张表，完整 schema 见 [references/artifact-contract.md](references/artifact-contract.md)。

| 产物 | 关键字段 |
|---|---|
| `dds-schema.json` | `nodes[].bounds`（`{x,y,width,height}`，几何权威）；`nodes[].parent_id`（父视图）；`nodes[].node_type`/`name`/`asset_ids`；顶层 `canvas`（画布尺寸）/`snapshot_id` |
| `ui-implementation-plan.json` | `layoutProportions.regions[].basis`·`parentIndex` + `relations[].kind`·`of`·`why` + `forbiddenLiterals`；`adaptiveLayout.windowSamples[]` + `regions[].widthPolicy` + `firstLevelWidthClass` + `forbiddenAdaptations`；`typeFacts[].kindSource`（`html-css` / `page-facts`）；`runtimeRisks`；`unsupported` |
| `runtime-device.json` | 运行时尺寸 API 返回值、根 view bounds、device scale |
| `review.json` | `runId`·`parentRunId`·`decision`·`feedback`·`observations`·`changes`·`verification`·`nextAction` |
| `delivery-gate.json` | 6 项基础闸门状态（声明 `adaptiveLayout` 时为 7 项）、`unsupported.count`、`deliveryReady`（只由脚本推导） |

三个容易混的点：

- **`kind` 五档**：`fixed` / `pinned` / `proportional` / `intrinsic` / `centered`。
- **`basis` 与 `of` 不是两个概念**：region 级的位置基准字段叫 `basis`，relation 级叫 `of`，两者都指向**直接父视图**。
- **三轴不是三套字段**：尺寸轴与位置轴都在 `layoutProportions` 里，宽度轴在 `adaptiveLayout` 里。

## 参考资料

- 尺寸与位置两条轴的完整规范：`references/sizing-and-positioning.md`
- 平板与宽屏自适应的完整规范：`references/adaptive-layout.md`
- 六种输出模式的技术边界：`references/target-modes.md`
- 页面事实表、实现计划和交付证据 schema：`references/artifact-contract.md`
- 用户判定不合格后的修复闭环：`references/feedback-loop.md`
- 产物生命周期、索引与恢复规则：`references/project-management.md`
- Lanhu MCP 调用顺序、主/备链路与失败处理：`references/lanhu-input.md`
- iOS 工程与设备环境探测：`references/ios-environment.md`
- 既有项目接入的工程审计与接入计划：`references/existing-project-integration.md`
- 资源复用、语义命名与代码分层：`references/resource-and-code-quality.md`

## 验证脚本一览

| 脚本 | 作用 | 何时必须跑 |
|---|---|---|
| `scripts/check_lanhu_mcp.py` | 检查 Lanhu MCP 注册与凭据就绪（只读，不打印凭据） | 开始前；阻塞时引导注册 |
| `scripts/lanhu_design_facts.py` | （**可选/当前 MCP 不可用**）把 `lanhu_get_design_document` 返回体解析成设计事实摘要，仅交叉佐证 | 需要回看 Sketch 帧时（当前改用 `lanhu_inspect_design_region`） |
| `scripts/layout_proportions.py` | 把几何事实转成 `layoutProportions` 约束规格，并列出「探针设备推导值」禁止清单 | 第 3 步写实现计划时 |
| `scripts/check_layout_proportions.py` | 计划驱动地核对源码有没有照计划声明的 `kind` 实现；`--plan-only` 只校验计划 | 门 0 写码前、门 1 写码后编译前；纯静态 |
| `scripts/check_adaptive_layout.py` | 宽度轴静态核对：声明完整 + 源码有封顶原语、无方向锁 / 屏幕系数 | 门 0 / 门 1；声明了 `adaptiveLayout` 就必须跑 |
| `scripts/audit_adaptive.py` | 多宽度采样的几何契约审计（八项），不做像素比对 | 交付前；声明 `adaptiveLayout` 时必须跑 |
| `scripts/diff_device_variants.py` | 双稿尺寸 diff：按图层名对齐生成 `sizeVariants[]` | 存在 `xx` / `xx-iPad` 成对稿时 |
| `scripts/check_pbxproj_ids.py` | pbxproj Object ID 唯一性门 | 每次手动改 `project.pbxproj` 之后、编译之前 |
| `scripts/discover_xcode_environment.py` | 探测 Xcode 工程 / scheme / 模拟器 | iOS 目标写代码前 |
| `scripts/validate_run.py` | run 产物契约校验，交叉核对闸门与证据；带 `--source` 时连布局约束一起判 | 每次写完 run |
| `scripts/init_ui_workspace.py` | 初始化 `.ihereforUI` 目录与索引 | 新项目开始时 |
| `scripts/cleanup_run.py` | 回收 run 里契约外的 DerivedData；只删编译缓存，证据一律保留 | 每次 run 交付后 |
| `scripts/decide_next_step.py` | 决定「这轮修复后该不该再开一轮编译」（读落盘产物做确定性判定） | 出结果后、考虑再开下一轮编译前 |
