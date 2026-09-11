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
python3 scripts/compare_reference.py --reference reference/reference.png --actual actual/app.png --output diff/summary.json --threshold 8
```

比较器只在尺寸一致时计算像素差；它不把尺寸缩放或裁剪当作通过。

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

## Agent 可见事实

Agent 可读取运行页面的 DOM、文本、属性、computed style、bounding box、层级、资源 URL、可访问性信息和交互状态。浏览器事实用于支撑决策，但不自动决定最终组件边界。
