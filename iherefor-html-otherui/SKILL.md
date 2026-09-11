---
name: iherefor-html-otherui
description: 将 Lanhu 导出的可运行 HTML/CSS/JS 页面作为视觉基准，由 Agent 生成并验证 SwiftUI、UIKit Swift、UIKit Objective-C、Jetpack Compose Kotlin、Android Views Kotlin 或 Android Views Java UI；当用户要求从 Lanhu HTML 落地 iOS/Android 原生页面时使用。
---

# Lanhu HTML 到多平台原生 UI

本 skill 面向“视觉还原优先”的 Lanhu 页面落地。输入是 Lanhu 缓存中完整的 HTML、CSS、JS 和资源，而不是仅依赖 Lanhu 结构化图层 JSON。目标是由 Agent 针对所选原生技术栈编写生产代码，并通过浏览器基准截图、目标 App 截图和编译测试形成闭环。

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

## Lanhu MCP 输入

用户提供 Lanhu 链接时，必须先使用已配置的 `mcp__lanhu_mcp` 服务获取项目、设计和可运行 HTML/CSS/JS/资源，并写入 `.ihereforUI/pages/<page-id>/source/`；不能要求手工下载，也不能仅凭结构化 JSON 生成原生 UI。严格调用顺序、缓存、版本和失败处理见 [references/lanhu-input.md](references/lanhu-input.md)。

若 MCP 未安装、未构建、未注册或凭据未配置，必须先运行 `scripts/check_lanhu_mcp.py` 并按 Lanhu 输入参考引导安装/注册；这是阻塞条件，不能绕过 MCP 改用手工资源或继续生成代码。安装引导不得打印或持久化 Lanhu 凭据。

## 资源与代码质量

在复制资源或编写代码前，必须读取 [references/resource-and-code-quality.md](references/resource-and-code-quality.md)。先扫描并复用目标工程已有资源体系；没有既有约定时才使用平台默认目录。资源必须按使用场景语义命名，不能把 `img_0` 等来源编号作为生产名。生成代码必须按 screen/section/style/resources 分层，所有按钮和可点击元素都要连接到命名明确的点击处理空函数。

## 既有项目接入

如果目标工程不是空项目，或用户要求二次开发/新增页面，必须先读取 [references/existing-project-integration.md](references/existing-project-integration.md)，完成工程审计并生成 `.ihereforUI/integration/project-audit.json`、`.ihereforUI/integration/integration-plan.json` 及页面级接入计划。计划批准前不得写入生产代码；文件名、模块、导航、依赖、资源、状态、测试和回滚方式都必须先列明。

## 五类持续视觉事实（强制约束）

以下事实必须贯穿发现、计划、编码、截图和修复全过程，不能只在首次分析时阅读后凭记忆实现：

1. 资源位置与层级：记录每个图片/SVG/背景资源的 URL、原始尺寸、目标坐标、z-index/stacking context、裁剪和 transform，并建立原生资源映射。
2. 元素 bounding box：从运行中的 HTML 读取每个可见区域和关键元素的 `getBoundingClientRect()`，保存为事实表。
3. 视觉样式：记录最终字体/fallback、字号、行高、颜色、透明度、渐变、阴影、圆角、overflow 和 transform；无法等价表达的属性写入 `unsupported`。
4. 画布缩放关系：保存 HTML viewport、devicePixelRatio、目标设备 bounds、截图像素尺寸和坐标变换（scale/letterbox/inset）。禁止直接复制另一设备的绝对像素坐标。
5. 差异证据：每次修改都保存 actual screenshot、diff summary（整页及关键区域）和修改原因；没有 diff 或明确的 `not-run` 原因，不得声称视觉完成。

这些数据应落在 `page-facts.json`、`ui-implementation-plan.json`、`visual-review.json` 和 `diff/` 中，并能从原始 HTML 元素追溯到原生视图。上下文压缩或 Agent 换手后必须重新读取这些产物，不能依赖对话记忆。

## 统一画布缩放契约（强制）

Lanhu 画布坐标不是目标设备坐标。先计算 `scaleX = trueDeviceWidth / lanhuCanvasWidth`、`scaleY = trueDeviceHeight / lanhuCanvasHeight`；保持比例时使用统一 scale，否则显式记录 `fit`、`fill` 或 `letterbox`，不能悄悄拉伸。

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

实现计划必须包含 `canvasTransform.coordinateMapper`；禁止各组件自行手调比例或混用 Lanhu px、UIKit pt、Android dp 和截图 px。

## 顶部系统区域与安全区

状态栏、刘海、Dynamic Island、导航栏和手势区域属于截图画布的一部分，不能默认当作页面外部留白。Agent 必须先从 HTML 基准确认页面是否绘制到顶部系统区域，再为每个目标平台记录 `systemBars` 策略：

- `underlap`: 页面背景/图片延伸到状态栏或导航栏下方，前景内容使用显式 inset；
- `inset`: 页面整体从安全区之后开始，只有在 HTML 基准确实保留空白时使用；
- `mixed`: 背景 underlap、文字和交互控件 inset。

iOS 必须显式处理 `edgesForExtendedLayout`、`extendedLayoutIncludesOpaqueBars`、safe-area inset、状态栏样式和 home indicator 区域；不能把 `safeAreaLayoutGuide` 作为所有页面的根部起点。尤其要检查 `UIScrollView` 的 `contentInsetAdjustmentBehavior`：UIKit 可能自动注入顶部/底部 safe-area content inset，若页面坐标已经包含系统区域，必须设为 `never` 并显式设置 `contentInset`，否则整页会下移。Android 必须显式处理 `WindowInsets`/`setDecorFitsSystemWindows`、status/navigation bar 对比度和 edge-to-edge；不能依赖设备默认 inset。目标 App 截图必须和 HTML 使用同一画布坐标系，任何系统区域偏移都要进入 diff 和 `visual-review.json`。

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

### 1. 发现、设备探测与参考基准

1. 确认 Lanhu HTML 入口、CSS/JS 相对路径、资源目录和页面状态。
2. 按目标模式探测运行时设备尺寸（iOS 见 [references/ios-environment.md](references/ios-environment.md)，Android 用 `WindowMetricsCalculator`），写入本次 run 的 `runtime-device.json`。**没有设备尺寸就不允许渲染基准图。**
3. 用 Playwright 以设备点尺寸与设备 scale 渲染 HTML：`node scripts/render_reference.mjs --input <source> --output <page>/reference --viewport-from <run>/runtime-device.json`。基准图默认是视口截图；`--full-page` 只用于人工阅读，不参与像素比对。
4. 记录 console、network、字体和资源错误，并把 `reference.png`、`page-facts.json`、`browser-meta.json` 写入页面级 `reference/`。

四步都完成后才进入第 2 步。基准图与目标 App 截图像素尺寸不一致时，diff 结果不具证据效力，禁止用缩放/裁剪后的派生图凑尺寸。

### 2. 页面事实表

Agent 必须查看运行中的页面和基准截图，建立页面事实表：可见区域、真实叠层、组件候选、文本、图片/SVG、渐变、阴影、滚动容器、交互状态和不支持特性。不得直接把每个 DOM 节点当成原生组件。页面必须按视觉区域逐一复现（hero、标题/说明、每张卡片、CTA、页脚等），每个区域列出 bounding box、资源/层级、样式事实、原生组件映射和验证截图。

### 3. 目标实现计划

输出 `ui-implementation-plan.json`，至少包含目标模式、参考 viewport、组件边界、坐标系、布局策略、资源映射、可访问性标识、交互候选和 `unsupported` 项。该文件是 Agent 决策记录，不是生产源码生成器的输入模板。

### 4. Agent 编写代码

Agent 直接维护目标工程中的 canonical UI 源码。脚本禁止生成、重写或覆盖 `.swift`、`.kt`、`.java`、`.h`、`.m`、`.xml` 和 Compose 生产文件。父组件必须真实创建并约束其子组件；画布叠层页面不得被强行串成纵向列表。

### 5. 编译、运行和截图

按目标模式使用 Xcode 或 Gradle 编译，运行目标设备/模拟器，保存实际截图、日志、约束/布局错误和测试结果。iOS 与 Android 必须分别验证，不能用一个平台的通过推断另一个平台通过。

### 6. 视觉修复循环

比较 HTML 基准与目标 App 截图，按区域分析偏移、尺寸、字体、颜色、叠层、裁剪、圆角、阴影和资源差异。Agent 修改 canonical 源码后重新编译和截图，直到达到任务指定阈值，或把无法自动修复的差异明确记录为 `needs-review`。每轮必须记录 before/after 截图、diff 数值或未运行原因、受影响区域、事实来源和下一步动作，禁止只凭肉眼说“基本一致”。

用户判定 diff 不合格后，必须进入可恢复的修复迭代：读取上一轮产物、记录用户反馈和差异分类，创建新的 run（保留 `parentRunId`），只修改 canonical 源码，重新 build/test/截图/diff，并按区域回归。详细字段、停止条件和 `review.json` schema 见 [references/feedback-loop.md](references/feedback-loop.md)。

### 7. 交付闸门

只有在所选目标模式的编译、资源接入、测试和视觉比较都通过时才标记 `deliveryReady=true`。缺失基准、编译失败、测试未运行、存在未处理 `unsupported` 或重大视觉差异时，只能标记 `pass-with-review`、`fail` 或 `not-run`。

## 输出证据

多页面任务必须先在项目根创建 `.ihereforUI`。产物结构以 [references/artifact-contract.md](references/artifact-contract.md) 为唯一事实来源，生命周期、索引和恢复规则见 [references/project-management.md](references/project-management.md)。可用 `scripts/init_ui_workspace.py` 初始化目录与索引；它只创建中间产物目录，不修改生产源码。

每个页面、每个目标模式、每次运行至少产出（缺一即不合规）：

- `run.json`、`review.json`、`delivery-gate.json`
- `ui-implementation-plan.json`、`resource-policy.json`
- `runtime-device.json`；iOS 目标另需 `ios-environment.json`
- `actual/`：目标 App 截图、编译/测试日志
- `diff/`：整页与区域差异摘要（含阈值与两张输入图的像素尺寸）

页面级冻结基准（`reference/reference.png`、`page-facts.json`、`browser-meta.json`、`approved.json`）与跨页面汇总（`.ihereforUI/reports/`）不放在 run 目录内。`visual-review.json`、`manifest.json` 和 run 级 `assets/` 已废弃，映射关系见契约。

每次写完 run 必须用 `scripts/validate_run.py --run <run-dir>` 自检；`deliveryReady` 只由闸门脚本推导，不得手写覆盖。禁止把多个页面的产物放在同一目录、覆盖历史 run，或以聊天上下文代替索引。

## 参考资料

- 浏览器启动、隔离 session、字体/资源稳定化和截图契约：`references/browser-runtime.md`
- 六种输出模式的技术边界和选择规则：`references/target-modes.md`
- 页面事实表、实现计划和交付证据 schema：`references/artifact-contract.md`
- 分阶段落地计划：`references/execution-plan.md`
