# 浏览器运行时契约

## 角色分工

| 角色 | 实现 | 用途 |
|---|---|---|
| 确定性渲染器 | Playwright API 脚本 | 加载页面、固定环境、测量、截图、资源检查 |
| Agent 浏览器 | Playwright CLI + Skills | 页面探索、交互、查看状态、辅助理解 |
| 深度探索 | Playwright MCP（可选） | 长上下文、复杂 DOM、shadow DOM、探索式流程 |

Browser Use、Stagehand、Steel 等可用于独立实验，但不是本 skill 的默认渲染内核；它们的自主决策或云端浏览器变量不能进入正式视觉基准链路。

## 本地脚本

运行时需要 Node.js 和 Playwright 包。依赖应安装到工作区或统一 skill runtime，不要把浏览器二进制散落复制到每个页面项目：

```bash
node scripts/render_reference.mjs --input /path/to/design-code --output /path/to/page/reference --viewport-from /path/to/run/runtime-device.json
node scripts/inspect_page.mjs --input /path/to/design-code --output /path/to/run/page-inspection.json
```

```bash
npm install                       # 安装 playwright 包
npx playwright install chromium   # 下载固定版本的 Chromium（正式回归必须走这一步）
```

两个脚本共用 `scripts/browser-launch.mjs` 决定用哪个浏览器，优先级是：

1. `--executable <path>` 或 `PLAYWRIGHT_EXECUTABLE_PATH` —— 复用本机 Chrome，仅作应急兜底；
2. 完整 Chromium 构建（Playwright 的 `chromium` 通道）—— 默认路径，就是 `npx playwright install chromium` 装的那一份；
3. Playwright 默认的 headless 布局（`chromium-headless-shell`）。

第 3 项是 Playwright 1.49+ 单独分发的一份浏览器：只装了第 2 项时，默认 launch 会直接抛
`Executable doesn't exist`，看起来像脚本坏了，实际只是少一份二进制。因此脚本显式走第 2 项，
只有该通道确实缺失才退回第 3 项；与浏览器缺失无关的启动错误会原样抛出，不会被吞掉。
用已安装的 Chrome 兜底时不会指定通道。正式回归仍应固定浏览器版本，并记录在 `browser-meta.json` 的 `browser` 字段里。

`render_reference.mjs` 只写入截图、`page-facts.json` 和 `browser-meta.json`；`inspect_page.mjs` 只写入只读页面摘要。两者都不会创建或修改原生 UI 源文件。

截图比较：

```bash
python3 scripts/compare_reference.py --reference reference/reference.png --actual actual/app.png --output diff/comparison.json
```

比较器只在尺寸一致时计算像素差；它不把尺寸缩放或裁剪当作通过。输出的差异分三类，**只有结构差异与填充差异参与放行判定**：

| 字段 | 含义 | 判定 |
|---|---|---|
| `structuralRatio` | 强边在两张图里对不上（在 `--edge-tolerance` 内找不到对应） | 超过 `--max-structural-ratio` 判 `fail`；**但仍在计划声明的 `gateReachability.expectedStructuralFloor` 内且 fill 未超限时，判 `pass-with-review`** |
| `fillRatio` | 平坦区颜色不同（填充色/文字颜色写错） | 超过 `--max-fill-ratio` 判 `fail`（下界不为它开口子） |
| `textureRatio` | 几何一致、只是像素值不同（栅格化、抗锯齿、次像素相位差） | 不参与判定 |

文字密集页的 `structuralRatio` 有**物理下界**（基准画布 `scale(1.0229)` 使基准字形 = 设计字号 × 1.0229，而字号不得缩放 ⇒ 差 2.29%，越过 2px 强边配对容差），**不可能降到 0**。要放行这个形态，须由计划声明 `gateReachability`，不要让实现去缩放字号凑闸门 —— 字段与可核性见 `artifact-contract.md`。

**不要用 `changedRatio` 放行**：它把三类混在一起。更要紧的是它**区分不出**下面这两种情况，而它们的处理方式正好相反 —— 「HTML 侧用 Web 字体、App 侧用系统字体」产生的抗锯齿差异是噪点，而「整块背景色写错」是真缺陷，两者在 `changedRatio` 上是同一个数。分类的判据是「强边在两张图里对不对得上」：边对得上、只有像素值不同 ⇒ 纹理；边对不上 ⇒ 结构。

同源审计（尺寸一致时也必须跑）：

```bash
python3 scripts/audit_alignment.py \
    --reference reference/reference.png --actual actual/app.png \
    --page-facts reference/page-facts.json \
    --runtime-device runtime-device.json \
    --output diff/alignment.json
```

它给出元素级的 `(dx, dy, scaleRatio)`：`domVsReference` 回答「基准图本身可不可信」，`referenceVsActual` 回答「App 有没有照基准图实现」。整页比例达标不能推翻元素级位移超容差。

## 默认渲染参数

```json
{
  "browser": "chromium",
  "headless": true,
  "deviceScaleFactor": 2,
  "reducedMotion": true,
  "disableAnimations": true,
  "waitForFonts": true,
  "waitForImages": true,
  "isolatedContext": true
}
```

具体 viewport 与 deviceScaleFactor 必须取自目标设备的运行时尺寸：`runtime-device.json` 的 `screenBoundsPoints` 与 `screenshotScale`。这样基准图与目标 App 截图的像素尺寸一致，像素 diff 才有证据效力。`--viewport WxH --scale N` 只是无设备时的应急手段，使用后必须在 run 中记录「未与设备同源」这一事实与原因。

`render_reference.mjs` 默认只截视口（`fullPage: false`）：设备截图是屏幕，不是整页文档，两者坐标系不同。需要整页长图供人工阅读时显式加 `--full-page`，但该图不得作为 diff 的 reference。

## 稳定化要求

- 加载前验证 HTML 入口和所有相对资源都位于任务允许目录。
- 页面加载后等待 `document.fonts.ready`。
- 等待图片 `complete && naturalWidth > 0`，记录失败 URL。
- 默认注入 CSS 禁止 transition/animation，并记录注入内容。
- 记录浏览器版本、OS、viewport、scale、locale、timezone、user agent。
- 保存 console error、network failure、字体 fallback 和页面 ready 状态。
- 截图前固定 scroll position；整页截图和关键区域截图分别保存。
- 页面使用 JS 定时器或异步数据时，必须定义稳定 ready 信号；不能只依赖固定 sleep。

## 字体事实：要「实际用上的」，不是「CSS 声明的」

`document.fonts.ready` 只保证字体加载流程走完，**不保证页面用的是你指定的字体**。页面上
真正渲染文字的是哪一族，只能问运行时：`render_reference.mjs` 用 CDP 的
`CSS.getPlatformFontsForNode` 逐节点取 `{family, glyphCount, isCustomFont}`，写入
`page-facts.json` 的 `fontsResolved` / `primaryFont`。

| 手段 | 能不能用来判断 fallback |
|---|---|
| CSS 声明的 `fontFamily` | **不能**。那只是请求，不是结果 |
| `document.fonts.check('16px "X"')` | **不能**。它对未安装的字体族同样返回 `true` |
| CDP `CSS.getPlatformFontsForNode` | **能**。返回真实使用的族与 `glyphCount` |
| `textMetrics.advanceWidth` | **能（间接）**。字体被替换时排版宽度必然变化 |

两条判据要一起用：如果 `fontsResolved` 里出现了 CSS 从未声明的族，或者
`textMetrics.advanceWidth` 与按声明字体预估的宽度不符，就是发生了 fallback —— 这属于
`typography` 类差异，必须进 `unsupported` 或按目标平台可用字体重写，不能当作「App 渲染
得不一样」蒙过去。

同时记录 `fontMeasurementCoverage`（量到了多少文本元素）：覆盖率低时上面两条判据都可能
是空结论，不能据此声称「字体一致」。

### 字体链最容易坏在三处，每处都要有断言

**一、文本元素集合必须是「自己直接承载文本」的元素。** 不能用 `innerText` 判断「这个
元素有没有文本」——它会把后代文本一并算进来，于是每个祖先容器都成了一个「291 字符、
21 段 rect」的伪文本元素，其 rect 并集只是子元素矩形的凑合。拿它做对齐预测会得到横跨整屏
的预测框。`page-facts.json` 用 `ownText` / `ownsText` 表达这件事，`textMetrics.rects` 也只
覆盖本元素直接承载的文本（`ownOnlyText`），另用 `hasDescendantTextElement` 标出「既自己
带词、又包着子文本」的元素。

**二、打标记与采集事实必须用同一个 index 空间。** CDP 按 `data-iherefor-text` 的取值回取
字体，所以「标记时用的编号」就是「字体归属的键」。曾经的实现里标记用未过滤的 DOM 序号、
采集用过滤掉不可见元素后的下标：页面里只要有一个不可见节点，它之后所有文本元素的
`primaryFont` 就整体错位一格 —— 实测某页 18 个文本元素里错了 **15** 个，而
`browser-meta.json` 一路报「字体已测量」。渲染器现在把两段判定与编号收敛到一处
（`SHARED_PRELUDE`），并输出自查 `fontJoin`：

| 字段 | 含义 |
|---|---|
| `fontJoin.ok` | 标记下标与采集下标逐个相符，且没有取不到的字体 |
| `fontJoin.textMarkMatches` / `textMarkMismatchCount` | 相符/错位的文本元素数 |
| `fontJoin.unjoinedIndexes` | CDP 返回了但采集侧找不到对应元素的下标（静默丢字体） |
| `fontJoin.domNodeCount` / `visibleNodeCount` / `indexSpaceSkew` | 两者之差就是错位空间；`skew == 0` 的页面**测不出**这个缺陷 |

**三、`glyphCount` 是子树口径，不是自有文本口径。** 对叶子文本元素
`sum(glyphCount) == charCount` 成立，可用来核对字体有没有归属错；对「自己带词又包着子
文本」的元素它是**子树合计**（见 `fontMeasurement.glyphCountScope`），此时 `primaryFont`
描述整个子树的主字体，未必是本元素那段文字的字体。据此判断这条事实该信到什么程度。

### Lanhu 导出的字体族经常是「不存在的族名」

蓝湖导出的 CSS 常见 `font-family: AvenirLT-Black` / `AvenirLT-Medium` 这种**带 LT 后缀**
的族名，而系统里装的是 `Avenir-Black` / `Avenir-Medium`。若同时满足：

- 样式表里 `@font-face` 为 `0`，源目录也没有字体文件；
- 该声明是**裸字体族名、没有泛型兜底**（不像 `body` 那样带 `sans-serif`）；

浏览器就只能回落到默认衬线字体（Chromium 上是 **Times**）。判定方法：量同一段文本在
该族名与 `Times` 下的排版宽度，**逐位相同**即已回落。实测某页标题因此窄了 23.6pt，而原生
侧另有一套 `UIFontWeightBlack → Avenir-Heavy` 的映射（该系统里根本没有 Black 字重），
两边叠起来就是审计里那个「标题偏移 24pt」——它从来不是坐标换算问题。

这类差异归 `typography`，要在基准阶段就改写字体栈（补泛型兜底或改用真实存在的族名），
**不要**拿一个字体已回落的基准图去要求 App 对齐。

## Agent 可见事实

Agent 可读取运行页面的 DOM、文本、属性、computed style、bounding box、层级、资源 URL、可访问性信息和交互状态。浏览器事实用于支撑决策，但不自动决定最终组件边界。
