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
7. **组件之间的布局关系必须严格遵循设计稿的比例，不得写成固定 pt 值。** 判据是「这个量的正确性是否依赖于容器尺寸」：位置、间距、容器与图片 frame 的尺寸依赖容器尺寸，必须比例化；字号、圆角、描边宽度、最小点击区不依赖，保持设计值不缩放。完整契约见 [references/artifact-contract.md](references/artifact-contract.md#组件间布局关系必须用比例表达强制)。

## 比例布局契约（强制）

设计稿里组件之间的布局关系，实现时必须表达为**比例**，而不是把换算结果写成绝对值。
Lanhu 画布只有一个尺寸：`lanhuY = 132` 换算成 `132 * 1.0229 = 135.02pt` 之后写成字面量，
就把这个关系钉死在探针设备上了 —— 换台设备它就是错的，而它「有算过」，比一眼可疑的魔数更难发现。

实现计划必须给出 `layoutProportions`（每个区域的 `ratios` 与逐条 `relations`），
每条关系声明 `kind`：

- `proportional` —— 必须用比例表达。iOS 用 `multiplier` / `UILayoutGuide`，SwiftUI 用
  `GeometryReader`，Compose 用 `BoxWithConstraints` 派生比例或 `weight`，
  Views/XML 用 `layout_constraintGuide_percent` / `bias` / `layout_weight`。
- `intrinsic` —— 必须给出 `why`，说明为什么这个量不随容器缩放（通常是文本撑开或设计常量）。

`scripts/layout_proportions.py` 由事实表与设备尺寸生成这份声明与「探针设备上算出来的绝对值」
清单；`scripts/check_layout_proportions.py` 按声明逐条核对源码，**计划驱动而非正则扫描** ——
只有被声明为 `proportional` 的关系才要求比例表达，避免把圆角 12、边距 16 这类合法设计常量误报。

```bash
# 第 2 步：生成比例规格（rect 的坐标空间由 rectInReference == rect*dpr 自动判定，判不出就拒绝继续）
python3 scripts/layout_proportions.py --page-facts <page>/reference/page-facts.json \
    --target-mode ios-uikit-objective-c --output <run>/plans/layout-proportions.json

# 实现完成后：核对源码是否真的按比例写（只校验计划用 --plan-only）
python3 scripts/check_layout_proportions.py --plan <run>/ui-implementation-plan.json \
    --source <原生源码根>

# 交付前：连同布局比例一起判（不给 --source 就只告警，不假装验证过）
python3 scripts/validate_run.py --run <run-dir> --source <原生源码根>
```

判定分两档，理由是要**准**而不是要响：数值 > 48pt 的字面量不可能是手选的设计常量，判违规；
≤ 48pt 时与常见设计常量无法区分，只列进 `ambiguousLiterals` 待人工确认，不计入违规。
源码里等于「探针设备推导值」的绝对值、以及「计划声明了比例却一处比例原语都没有」都会被拦下。

### 比例模型与 `fit` 策略必须一致

`fit` 映射与比例映射是两条直线，最大偏差恰好等于 letterbox 厚度（`padding.max`）。
`padding.max` 超过位置容差时二者不可互换：实现用比例模型，**对齐审计也必须改用比例模型预测**，
否则是拿 `fit` 的预测框去量比例布局，把模型差报成实现错误。用
`python3 scripts/canvas_map.py --self-test` 后的 `axis_deviation()` 读这个值，不要凭感觉判断。

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
3. 视觉样式：记录最终字体/fallback、字号、行高、颜色、透明度、渐变、阴影、圆角、overflow 和 transform；无法等价表达的属性写入 `unsupported`。字体的「最终」指**运行时实际用上的**字体，不是 CSS 声明的 `fontFamily`：必须记录 `fontsResolved` / `primaryFont`（来自 CDP `CSS.getPlatformFontsForNode`，附 `glyphCount`）与 `textMetrics`（每个文本元素的 `advanceWidth`、`lineHeight`、`rects`）。`document.fonts.check()` 对未安装的字体族也返回 `true`，**不能**用来判断 fallback。
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

分析代码（区域 diff、对齐审计、确定性证据生成）必须 import 它。历史上「多乘一层 scaleY」的系统性偏移就来自手写换算，而这类错误在整页 diff 数值上完全看不出来：

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

实现计划还必须包含 `layoutProportions`：每个区域的 `ratios` 与逐条 `relations`（`kind` 为 `proportional` 或 `intrinsic`），以及 `forbiddenLiterals` 清单。`canvasTransform` 与 `layoutProportions` 分工不同，不要互相替代：

- `canvasTransform` 是**测量用**的桥 —— 把 Lanhu 坐标换算到设备点和截图像素，供审计与 diff 使用；
- `layoutProportions` 是**实现用**的规格 —— 告诉原生代码每条关系该写成哪个比例。

拿 `canvasTransform` 算出的绝对值去写约束，就是把测量桥当成了实现规格，这正是比例契约要禁止的动作。

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

### 1. 发现、设备探测与参考基准

1. 确认 Lanhu HTML 入口、CSS/JS 相对路径、资源目录和页面状态。
2. 按目标模式探测运行时设备尺寸（iOS 见 [references/ios-environment.md](references/ios-environment.md)，Android 用 `WindowMetricsCalculator`），写入本次 run 的 `runtime-device.json`。**没有设备尺寸就不允许渲染基准图。**
3. 用 Playwright 以设备点尺寸与设备 scale 渲染 HTML：`node scripts/render_reference.mjs --input <source> --output <page>/reference --viewport-from <run>/runtime-device.json`。基准图默认是视口截图；`--full-page` 只用于人工阅读，不参与像素比对。
4. 记录 console、network、字体和资源错误，并把 `reference.png`、`page-facts.json`、`browser-meta.json` 写入页面级 `reference/`。

四步都完成后才进入第 2 步。基准图与目标 App 截图像素尺寸不一致时，diff 结果不具证据效力，禁止用缩放/裁剪后的派生图凑尺寸。

**但「尺寸一致」只是同源的必要条件，不是内容对齐的证据。** 一次事故里基准图与实机截图都是 1206×2622、检查全绿，内容却整体差 6–21pt 且偏差随 y 递增。像素尺寸相等证明不了任何东西，必须另外跑一次元素级对齐审计：

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

字体被静默替换时，基准图会「**自洽地错**」：CSS 声明 `AvenirLT-Black`、页面里 `@font-face` 规则数为 0、也没有 generic fallback，Chromium 于是回落到默认衬线字体 Times。DOM 事实表与基准图因为用了同一套回落字体而互相印证 —— 对齐审计的 `domVsReference` 判 `aligned`，于是它把不一致归给 App 侧，而那句结论在它自己的视野内是**对的**。照着它去改 App 的字体，只会离设计稿越来越远。

所以对齐审计之后必须再核一次字体链，**声明 ≠ 结果**：

```bash
python3 scripts/audit_fonts.py \
    --page-facts   <page>/reference/page-facts.json \
    --browser-meta <page>/reference/browser-meta.json \
    --output       <run>/diff/font-chain.json
```

它逐元素比对「CSS 声明的族」与「运行时实际用上的族」（`primaryFont` / `fontsResolved`，来自 CDP `CSS.getPlatformFontsForNode`），退出码 0 = 一致，1 = 发生替换（账在**基准**侧），2 = 证据不足。判出替换时不得把 `reference` 记为 `pass`；`scripts/validate_run.py` 会拦住这种矛盾。修法是补 `@font-face` 或把声明的族换成运行时真实存在的族，然后**重新渲染基准、重新测量**，再判断 App 侧还有没有残余差异。

三条判定纪律，都指向同一件事——**闸门要准，不是要响**：

- **族名格式差异不算替换。** `Avenir-Medium`（CSS 写法）与 `Avenir Medium`（CDP 报回的 `familyName`）是同一个族。实测那页 18 个文本元素里 14 个是这种差异，逐字符比会把它们全报成替换，等于把闸门焊死。
- **系统关键字不算替换。** `-apple-system` / `system-ui` 由平台解析成系统 UI 字体，本来就没有可比对的族名字符串；命中它们却比不相等不构成证据。
- **没做字体测量的事实表判「证据不足」，不判干净。** 旧 schema 的 `page-facts.json` 没有 `primaryFont`；`fontMeasurement.ok` / `fontJoin.ok` 为 `false` 时元素上残留的字体字段也不能当成本次证据 —— 拿它下结论比没有数据更危险。

### 2. 页面事实表

Agent 必须查看运行中的页面和基准截图，建立页面事实表：可见区域、真实叠层、组件候选、文本、图片/SVG、渐变、阴影、滚动容器、交互状态和不支持特性。不得直接把每个 DOM 节点当成原生组件。页面必须按视觉区域逐一复现（hero、标题/说明、每张卡片、CTA、页脚等），每个区域列出 bounding box、资源/层级、样式事实、原生组件映射和验证截图。

**「文本元素」的判定只有一个：元素自身有直接子文本节点**（事实表里的 `ownsText` / `ownText`）。不要用 `innerText`——它把所有后代文字聚合上来，于是每个容器都变成「幻影文本元素」；一次事故里 34 个元素有 `innerText`、只有 18 个真有直接文本，用它当清单会让字体测量和位置预测都挂在错误的框上。同理 `textMetrics.rects` 只取直接子文本节点（`ownOnlyText: true`），否则一个既有自身文字又有子元素文字的表头会得到一个横跨两者的并集框。**一旦事实表里的文本元素含容器，或 `browser-meta.json` 的 `fontJoin.ok` 为 `false`，这份事实表就不能用于元素级审计，必须重新渲染取一份新的。**

### 3. 目标实现计划

输出 `ui-implementation-plan.json`，至少包含目标模式、参考 viewport、组件边界、坐标系、布局策略、资源映射、可访问性标识、交互候选和 `unsupported` 项。该文件是 Agent 决策记录，不是生产源码生成器的输入模板。

### 4. Agent 编写代码

Agent 直接维护目标工程中的 canonical UI 源码。脚本禁止生成、重写或覆盖 `.swift`、`.kt`、`.java`、`.h`、`.m`、`.xml` 和 Compose 生产文件。父组件必须真实创建并约束其子组件；画布叠层页面不得被强行串成纵向列表。

### 5. 编译、运行和截图

按目标模式使用 Xcode 或 Gradle 编译，运行目标设备/模拟器，保存实际截图、日志、约束/布局错误和测试结果。iOS 与 Android 必须分别验证，不能用一个平台的通过推断另一个平台通过。

### 6. 视觉修复循环

比较 HTML 基准与目标 App 截图，按区域分析偏移、尺寸、字体、颜色、叠层、裁剪、圆角、阴影和资源差异。比较器给出的差异是三类，**只有前两类参与放行判定**：

| 类别 | 含义 | 判定 |
|---|---|---|
| `structuralRatio` | 强边在两张图里对不上 —— 几何错位、尺寸变化、间距改错 | 超过 `--max-structural-ratio` 判 `fail` |
| `fillRatio` | 平坦区颜色不同 —— 填充色/背景色/文字颜色写错、整块缺遮罩 | 超过 `--max-fill-ratio` 判 `fail` |
| `textureRatio` | 几何一致、只是像素值不同 —— 字体栅格化、抗锯齿、次像素相位差 | **不参与判定**（这是噪点） |

不要用 `changedRatio` 判断能不能放行：它把三类混在一起，于是抗锯齿多的页面（HTML 用 Web 字体、App 用系统字体）永远撞上限，而真正错位的图只要背景色接近也可能因为纹理差异低而侥幸通过。结论必须带**区域级**明细（`regions`），整页一个数字看不出偏差随 y 的变化。

Agent 修改 canonical 源码后重新编译和截图，直到达到任务指定阈值，或把无法自动修复的差异明确记录为 `needs-review`。每轮必须记录 before/after 截图、diff 数值或未运行原因、受影响区域、事实来源和下一步动作，禁止只凭肉眼说"基本一致"。

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
- `diff/`：整页与区域差异摘要（含 `structuralRatio`/`textureRatio`/`fillRatio`、阈值与两张输入图的像素尺寸）、`alignment.json`（元素级位移证据）

`diff/` 里的放行类结论（`status` 为 `pass` 或 `pass-with-review`）必须自带 `structuralRatio` 与非空的 `regions`；只有 `changedRatio` 的结论不足以放行，校验脚本会拒绝。

页面级冻结基准（`reference/reference.png`、`page-facts.json`、`browser-meta.json`、`approved.json`）与跨页面汇总（`.ihereforUI/reports/`）不放在 run 目录内。`visual-review.json`、`manifest.json` 和 run 级 `assets/` 已废弃，映射关系见契约。

每次写完 run 必须用 `scripts/validate_run.py --run <run-dir>` 自检；`deliveryReady` 只由闸门脚本推导，不得手写覆盖。禁止把多个页面的产物放在同一目录、覆盖历史 run，或以聊天上下文代替索引。

## 人工验收入口

skill 根目录的 `index.html` 是一个纯静态差异查看器（无需服务器、无外部依赖）：用浏览器打开后选择包含 `.ihereforUI` 的项目目录，它会递归扫描各页面各 run 的 `diff/*.json`，并排展示 reference 与 actual 截图、差异数值与闸门状态。这是用户判定「合格 / 不合格」的入口；判定不合格后的修复流程见 [references/feedback-loop.md](references/feedback-loop.md)。

## 参考资料

- 浏览器启动、隔离 session、字体/资源稳定化和截图契约：`references/browser-runtime.md`
- 六种输出模式的技术边界和选择规则：`references/target-modes.md`
- 页面事实表、实现计划和交付证据 schema：`references/artifact-contract.md`
- 分阶段落地计划：`references/execution-plan.md`

## 验证脚本一览

| 脚本 | 作用 | 何时必须跑 |
|---|---|---|
| `scripts/canvas_map.py` | 唯一的坐标换算入口，正向 + 逆向 + 默认 `fit` 策略；`to_ratios` / `axis_deviation` 给出比例形式与模型偏差 | 任何需要换算坐标的分析之前；改坐标逻辑后跑 `--self-test` |
| `scripts/render_reference.mjs` | 确定性渲染基准图与事实表（含 `rectInReference`、`alphaBounds`、`textMetrics`、运行时字体） | 第 1 步建立基准 |
| `scripts/layout_proportions.py` | 把事实表位置转成 `layoutProportions` 比例规格，并列出「探针设备推导值」禁止清单 | 第 2 步写实现计划时；缺它就没法核对「有没有写成固定 pt」 |
| `scripts/check_layout_proportions.py` | 计划驱动地核对源码是否按比例表达；`--plan-only` 只校验计划 | 实现完成后、交付前；改了布局代码就要重跑 |
| `scripts/compare_reference.py` | 像素比较，输出结构/纹理/填充三分与区域明细 | 每次截图后 |
| `scripts/audit_alignment.py` | 元素级对齐审计，区分「基准不可信」与「App 不对」 | 每次截图后；尺寸一致也必须跑 |
| `scripts/audit_fonts.py` | 字体链审计：逐元素比对「CSS 声明的族」与「运行时实际用上的族」，判出静默字体替换 | 每次截图后；`alignment.json` 说「问题在 App 侧」时更要跑 |
| `scripts/validate_run.py` | run 产物契约校验，交叉核对闸门与证据；带 `--source` 时连同布局比例一起判 | 每次写完 run |

脚本级回归见 `scripts/tests/run_all.sh`（不需要 LLM，CI 每次跑）；Agent 行为红线见 `evals/README.md`。
