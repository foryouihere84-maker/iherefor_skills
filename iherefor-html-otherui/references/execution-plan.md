# iherefor-html-otherui 分阶段落地计划

## 阶段 0：契约和目录

- 固定输入：Lanhu HTML/CSS/JS/assets 目录。
- 固定输出：`.ihereforUI/project.json` + `pages/<page-id>/` + `runs/<run-id>/`，按 `project/page/target/run` 隔离 reference、actual、diff 和报告。
- 多页面先注册页面索引，再逐页执行；页面状态相互隔离，项目汇总只由页面状态生成。
- 固定目标模式：SwiftUI、UIKit Swift、UIKit Objective-C、Compose Kotlin、Android Views Kotlin、Android Views Java。
- 完成标准：`scripts/tests/run_all.sh` 与 `scripts/validate_run.py` 通过，且旧 `lanhu-objc-ui` 不被修改。

## 阶段 1：Playwright 浏览器运行时

- 实现本地 HTML 加载、路径安全、隔离 session、viewport/deviceScaleFactor、字体和图片等待。
- 实现稳定化脚本：禁用动画、等待网络空闲、记录 console/network、保存浏览器元数据。
- 实现 reference screenshot、区域 screenshot 和页面事实提取。
- 页面事实必须包含资源坐标/层级、关键元素 bounding box、computed style、viewport 到设备截图的坐标变换；同一输入连续运行时这些事实和截图都要可复核。
- 所有图片和组件必须先经过统一 coordinate mapper；禁止按自然尺寸或 Lanhu 原始 CSS 尺寸直接放置。
- 完成标准：同一输入连续运行两次，截图和事实摘要在可接受误差内一致。
- 每次运行写入页面专属 `runs/<run-id>/run.json`，并记录基准哈希；不得覆盖已批准 reference。

## 阶段 2：Agent 页面审查契约

- 定义页面事实表和 `ui-implementation-plan.json`。
- 由 Agent 决定组件边界、画布/流式布局、叠层关系和交互候选。
- 明确无法转换项，不允许脚本静默降级。
- 完成标准：页面计划能追溯到 DOM、资源和 reference screenshot。

## 阶段 3：首批目标后端

- 先实现 `ios-swiftui` 和 `android-compose-kotlin` 的 Agent 指令与验证模板。
- 再补 `ios-uikit-swift`、`ios-uikit-objective-c`、`android-views-kotlin`、`android-views-java`。
- 每个后端独立定义资源、字体、渐变、阴影、绝对定位和 accessibility 映射。
- 完成标准：每个模式都能接入真实工程并通过最小编译 smoke test。

## 阶段 4：视觉闭环

- 统一采集目标 App screenshot。
- 支持整页 diff、区域 diff、阈值和差异摘要。
- 将差异反馈给 Agent，循环修改 canonical 源码。
- 每轮按区域保存 before/after screenshot、diff summary、受影响事实和修复说明；上下文切换后从这些产物恢复，而不是依赖聊天历史。
- 每轮视觉审查至少抽查一个图片、一个容器和一个文本区域的 Lanhu frame→target frame 映射，确认使用同一 scaleX/scaleY 和 origin。
- 完成标准：至少一个真实 Lanhu 页面在两个平台各有一条完整闭环记录。

## 阶段 5：交付闸门和回归

- 校验资源引用、字体、编译、测试、截图、diff 和 `unsupported` 项。
- 建立最小 fixture 页面，覆盖文本、图片、渐变、阴影、叠层、滚动和点击状态。
- 使用 quick validator，并对浏览器脚本执行实际 smoke test。
- 完成标准：失败原因可区分为页面事实、生成代码、工程配置、设备环境或签名问题。

## 暂不做

- 不自动把 JS 业务逻辑翻译成原生业务层。
- 不承诺任意 CSS 特性都能等价转换。
- 不把截图当作生产 UI 覆盖层来交付。
- 不修改或删除旧 `lanhu-objc-ui` skill。
