# 产物契约

本文件是 `.ihereforUI` 产物结构的**唯一事实来源**。`SKILL.md`、`project-management.md`
与 `scripts/validate_run.py` 都以本文件为准；出现分歧时先改本文件，再同步其他两处。

机器校验入口：

```bash
python3 scripts/validate_run.py --run .ihereforUI/pages/<page-id>/runs/<run-id>
```

## 三级结构

| 级别 | 路径 | 生命周期 |
|---|---|---|
| 项目 | `.ihereforUI/` | 整个任务 |
| 页面 | `.ihereforUI/pages/<page-id>/` | 页面注册到交付 |
| 运行 | `.ihereforUI/pages/<page-id>/runs/<run-id>/` | 一次生成或一次修复；只追加，不覆盖 |

一个 run 只对应一个页面 + 一个目标模式。同一页面的不同目标模式必须使用不同 run ID。

## 项目级

```text
.ihereforUI/
├── project.json                 # 项目索引：inputRoot、targetModes、当前页面
├── index.json                   # 机器索引（可选，由管理脚本生成）
├── integration/
│   ├── project-audit.json       # 既有工程只读审计
│   └── integration-plan.json    # 项目级接入计划
└── reports/
    ├── project-status.json      # 跨页面汇总，只由各页 status.json 生成
    └── delivery-gate.json       # 项目级交付闸门
```

## 页面级

```text
pages/<page-id>/
├── page.json                    # 页面元数据、HTML 入口、implementationPaths、runs
├── status.json                  # 页面级交付状态与 latestRunId
├── source/                      # 只读输入快照
│   ├── manifest.json            # 文件清单、sha256、image_id、版本、来源 URL
│   └── assets-manifest.json     # URL → 原生资源映射
├── plans/
│   ├── ui-implementation-plan.json
│   └── integration-plan.json     # 仅既有项目接入时需要
└── reference/                   # 当前**已批准**的视觉基准（冻结）
    ├── reference.png            # HTML 基准截图
    ├── page-facts.json          # 页面事实表（rect / rectInReference / textMetrics / 资源）
    ├── browser-meta.json        # 浏览器版本、viewport、运行时字体、注入记录、加载错误
    └── approved.json            # 批准记录：sha256、批准时间、批准人
```

事实表与浏览器元数据属于**基准**，因此放在页面级而不是 run 级：重新渲染不会自动替换
已批准基准，只有显式批准才写入 `approved.json`。

### `page-facts.json`（schemaVersion 3）

v1 只存了 CSS px 的 `rect` 与 CSS **声明**的 `fontFamily`，于是任何像素级比对都得自己
把 CSS px 换算到基准图像素 —— 每写一次就多一次错的机会。v2 把「元素在基准图里应该出现
在哪」直接算好。**v3 补上父子层级**：布局约束要「相对直接父视图」表达，而这件事在 v2 的事实表里
根本无从判断 —— 元素只有绝对 `rect`，谁是它的父视图没有记。

v3 起每个元素都带 `parentIndex` / `parentHops` / `positioningContextIndex`
（绝对定位元素才带最后一项）。**读不到这些字段时不得假设层级已知** ——
那意味着这是一份 v2 时代的事实表，任何「相对父视图」的推算都会退化成「相对整屏画布」。

```json
{
  "schemaVersion": 3,
  "title": "Special Offer",
  "url": "file:///…/index.html",
  "viewport": {"width": 393, "height": 852, "devicePixelRatio": 2, "scroll": {"x": 0, "y": 0}},
  "documentSize": {"width": 393, "height": 852},
  "coordinateSpace": {
    "note": "rect 是 CSS px（视口相对）；rectInReference 是 reference.png 的像素坐标",
    "parentNote": "parentIndex 是最近可见祖先在 elements 里的下标；null 表示直接父视图就是整屏画布；parentHops 是中间跳过的不可见层数；positioningContextIndex 只出现在 absolute/fixed 元素上，null 表示坐标原点即视口；缺该字段表示元素不是绝对定位"
  },
  "referenceImage": {"path": "reference.png", "width": 786, "height": 1704,
                     "alphaBounds": {"x": 0, "y": 0, "width": 786, "height": 1704}},
  "elements": [
    {
      "index": 12,
      "tag": "div",
      "id": "plan-yearly",
      "className": "plan-card plan-card--yearly",
      "role": null,
      "ariaLabel": null,
      "src": null,
      "text": "Yearly $59.99 Save 40%",
      "ownText": "Yearly",
      "ownsText": true,
      "textMark": "12",
      "parentIndex": 4,
      "parentHops": 2,
      "rect": {"x": 20, "y": 310, "width": 353, "height": 190},
      "rectInReference": {"x": 40, "y": 620, "width": 706, "height": 380},
      "style": {"fontFamily": "\"PingFang SC\", sans-serif", "fontSize": "16px",
                "lineHeight": "24px", "color": "rgb(17, 17, 17)"},
      "fontFamily": "\"PingFang SC\", sans-serif",
      "fontsResolved": [{"family": "PingFang SC", "glyphCount": 214, "isCustomFont": false}],
      "primaryFont": {"family": "PingFang SC", "glyphCount": 214, "isCustomFont": false},
      "textMetrics": {
        "charCount": 6,
        "fontSize": 16,
        "lineHeight": 24,
        "advanceWidth": 147.5,
        "ownOnlyText": true,
        "hasDescendantTextElement": false,
        "rects": [{"x": 40, "y": 620, "width": 147.5, "height": 24}]
      }
    }
  ],
  "images": [
    {
      "src": "assets/hero.png",
      "rectInReference": {"x": 0, "y": 0, "width": 786, "height": 600},
      "naturalWidth": 500,
      "naturalHeight": 382,
      "alphaBounds": {"x": 0, "y": 0, "width": 500, "height": 382}
    }
  ],
  "textMetricsNote": "advanceWidth 是排版宽度（CSS px），字体被替换时必然变化；用它判断 fallback，不要用 CSS 声明的 fontFamily"
}
```

**字段以实际渲染产物为准。** 上面的清单由 `scripts/tests/test_page_facts_text_elements.py`
与实际渲染结果逐字段核对：契约里承诺的字段，渲染器必须真的产出。

| 字段 | 用途 |
|---|---|
| `id` / `className` / `tag` | 元素的 DOM 身份。这是事实表能提供的定位信息；**没有 `selector`**，要定位就自己按 `id`/`className` 组选择器 |
| `text` | `innerText` 聚合结果（含后代）。**不要拿它判断「这是不是文本元素」**，用 `ownText`/`ownsText` |
| `role` / `ariaLabel` | 可访问性事实，用于映射原生 accessibility identifier |
| `src` | 图片元素的资源地址（无则为 `null`） |
| `ownText` | 元素**自身直接子文本节点**拼成的文本。判断「这个元素是不是一个文本元素」只用它，不要用 `innerText` |
| `ownsText` | `ownText` 非空的布尔快照。审计脚本用它挑文本元素，避免把「只是包含文本的容器」混进来 |
| `textMark` | 该元素在标记阶段拿到的 `data-iherefor-text` 值。与 `index` 一致才说明字体是按同一套下标注入的（见下方 `fontJoin`） |
| `rectInReference` | 「DOM 说元素该在基准图的哪个像素位置」的唯一事实来源。比对 DOM 与基准图时用它，不要自己乘 dpr |
| `textMetrics.rects` | 实测排版结果（多行文本有多段）。有它时优先作为文本内容的预测位置，而不是 `rectInReference`（文本框比实际字迹大） |
| `textMetrics.ownOnlyText` | `rects` 只来自直接子文本节点（不含后代元素里的文字）。`false` 或缺失说明这是旧版事实表，`rects` 可能是跨后代的并集框 |
| `textMetrics.hasDescendantTextElement` | 该文本元素内部还嵌着别的文本元素。为 `true` 时 `rects` 与 `glyphCount` 的语义都变宽，做断言前必须看这一位 |
| `textMetrics.advanceWidth` | 排版宽度。字体被 fallback 替换时必然变化，是判断「字体没生效」的可靠信号 |
| `fontsResolved` / `primaryFont` | 运行时**实际用上**的字体（来自 CDP `CSS.getPlatformFontsForNode`，附 `glyphCount`）。CSS 声明的 `fontFamily` 只是请求，不是结果 |
| `alphaBounds` | 图片非透明内容 bounds。「frame 已缩放」不等于「图片已缩放」—— 透明留白会让两者不一致 |

**文本元素的定义必须只有一个**：`innerText` 会把所有后代文字聚合上来，于是每一个容器都成了
「幻影文本元素」。事故 run 里 34 个元素有 `innerText`、只有 18 个有直接文本 —— 用前者当文本
元素清单，字体测量和位置预测都会指到错误的框上。**一旦事实表里的文本元素含容器，那份事实表
就不适合再做元素级审计，只能重新渲染取一份新的。**

**不要用 `document.fonts.check()` 判断 fallback**：它对未安装的字体族同样返回 `true`。

`browser-meta.json`（schemaVersion 3）相关字段：

| 字段 | 内容 |
|---|---|
| `fontMeasurement` | `method: "cdp:CSS.getPlatformFontsForNode"` 与是否成功；`glyphCountScope: "subtree-of-node"`（见下） |
| `fontMeasurementCoverage` | `{textElements, measured}` —— 有多少文本元素真的量到了 |
| `fontJoin` | 标记阶段与采集阶段是否同一套下标：`markedElements` / `joinedElements` / `unjoinedIndexes` / `textElements` / `textMarkMatches` / `textMarkMismatchCount` / `indexSpaceSkew` / `ok`。`ok: false` 时**整份字体数据作废**，它意味着字体被挂到了别的元素上 |
| `fontProbe` | `document.fonts` 的 `FontFace` 列表与 `probeNote`（记录 `check()` 不可用这件事） |
| `images[].alphaBounds` | 每张图片的非透明内容 bounds |
| `referenceImage` | `reference.png` 自己的 alpha bounds |

`browser-meta.json` 的 v3 与 v2 **字段完全一样**，变的只有版本号：一次渲染同时产出两份文件，
层级是加在 `page-facts.json` 上的。版本号跟涨是为了让「这份基准是哪一代渲染器采的」
一眼可辨 —— 看到 v2 的 `browser-meta.json` 就说明配套的 `page-facts.json` 里也读不到
`parentIndex`。

**`glyphCount` 是子树的字形数，不是该元素自身文字的字符数**。对叶子文本元素
`glyphCount == charCount` 成立；对内部还嵌着文本的元素，它是整棵子树的合计。断言前先看
`hasDescendantTextElement`，否则会误判成「量错了」。

## 运行级（每次 run 必需）

| 文件 | 必需条件 | 内容 |
|---|---|---|
| `run.json` | always | 运行标识、目标模式、父 run、基准哈希、状态 |
| `review.json` | always | 观察 / 假设 / 变更 / 验证 / 下一步（含 `parentRunId`） |
| `delivery-gate.json` | always | 7 项闸门状态、`unsupported` 计数、`deliveryReady` |
| `ui-implementation-plan.json` | always | 本次实现的区域、坐标系、资源映射与 `unsupported` |
| `resource-policy.json` | always | 资源目录决策、复用与新增、语义命名 |
| `runtime-device.json` | 所有目标模式 | 运行时尺寸 API 返回值与截图像素尺寸 |
| `ios-environment.json` | iOS 目标模式 | 工程入口、scheme、destination 探测结果 |
| `actual/` | always | 目标 App 截图、构建/测试日志 |
| `diff/` | always | 结构/纹理/填充三分与区域差异摘要；元素级对齐审计 `alignment.json`；基准字体链 `font-chain.json` |

### `run.json`

```json
{
  "schemaVersion": 1,
  "runId": "20260907-150000-objc-011",
  "pageId": "plan-selection",
  "targetMode": "ios-uikit-objective-c",
  "parentRunId": "20260907-140000-objc-010",
  "createdAt": "2026-09-07T15:00:00+08:00",
  "referenceBaseline": {"approved": "reference/approved.json", "sha256": "<reference.png 哈希>"},
  "status": "needs-review",
  "legacy": false
}
```

`parentRunId` 为 `null` 表示首轮。反馈迭代必须新建 run 并指向上一轮，禁止覆盖历史 run。

### `review.json`

```json
{
  "schemaVersion": 1,
  "runId": "20260907-120000-objc-006",
  "parentRunId": "20260907-104000-objc-005",
  "decision": "rejected",
  "feedback": [{"text": "标题和卡片整体偏下", "source": "user", "at": "2026-09-07T12:00:00+08:00"}],
  "observations": [{"region": "title", "category": "geometry", "evidence": ["diff/full-page.json"]}],
  "hypotheses": ["safe-area 自动 inset 与 Lanhu underlap 重复计算"],
  "changes": [{"file": "testUIProject/SubscriptionPlanSelectionViewController.m", "reason": "关闭自动 content inset"}],
  "verification": {"build": "pass", "tests": "pass", "visualDiff": "pass-with-review", "runtimeDevice": "runtime-device.json"},
  "nextAction": "等待用户复核"
}
```

`decision` 取值：`pending` | `accepted` | `rejected`。`category` 取值见 `feedback-loop.md`。

### `delivery-gate.json`

```json
{
  "schemaVersion": 1,
  "runId": "20260907-150000-objc-011",
  "status": {
    "reference": "pass",
    "browser": "pass",
    "sourceAssets": "pass",
    "implementation": "pass",
    "build": "pass",
    "tests": "pass",
    "visualDiff": "fail"
  },
  "unsupported": {"count": 0, "reviewedCount": 0, "items": []},
  "deliveryReady": false,
  "blockingReasons": ["visualDiff=fail"]
}
```

每个状态取值：`pass` | `pass-with-review` | `fail` | `not-run`。

`visualDiff` 的取值受 `diff/` 的证据约束，不能只看整页比例：

- `diff/alignment.json` 判 `needs-review` 时，`visualDiff` **不得**为 `pass`。尺寸相同、整页
  比例达标都推翻不了元素级位移超容差。
- `diff/` 里任何放行类结论（`pass` / `pass-with-review`）必须自带 `structuralRatio` 与非空
  `regions`；只有 `changedRatio` 的结论不足以放行。

`reference` 的取值还要受基准字体链约束：

- `diff/font-chain.json` 的 `substituted` 为 `true` 时，`reference` **不得**为 `pass`。基准图
  的排版结果本身就是用错字体排出来的，它「自洽地错」—— DOM 事实表与基准图互相印证，
  对齐审计只能把不一致归给 App 侧。先修基准的字体栈并重渲染，再谈 App 侧。

`deliveryReady` 为 `true` 的**充要条件**（校验脚本按此判定，不接受手写覆盖）：

1. 上述 7 项全部为 `pass`；
2. `unsupported.count == unsupported.reviewedCount`（不存在未审查的降级项）；
3. `unsupported` 的两个计数必须是**可读的整数**。

第 3 条的意思是「推不出来就别推」：`unsupported` 对象缺失、或 `count` / `reviewedCount`
不是整数（例如写成字符串 `"2"`）时，`delivery-gate.json` 本身已经不合规，校验脚本会**跳过**
`deliveryReady` 的一致性核对并留下告警，由你去补齐结构，它不会替你补一个取值。特别地，
**不会**把它推导成 `true` —— 缺字段时按「复核完毕」算（`None == None`），等于让「没做人工
复核」成为放行理由，这是必须堵死的一条。

前两条不满足时 `deliveryReady` 必须为 `false`，并在 `blockingReasons` 中列出原因；
第 3 条不满足时先补齐结构，再谈 `deliveryReady`。

### `ui-implementation-plan.json` 的 `canvasTransform`

```json
{
  "canvasSize": {"width": 393, "height": 852},
  "deviceSize": {"width": 402, "height": 874},
  "screenshotScale": 3,
  "screenshotPixels": {"width": 1206, "height": 2622},
  "policy": "fit",
  "reason": null,
  "uniformScale": true,
  "ratioX": 1.02290076,
  "ratioY": 1.0258216,
  "scaleX": 1.02290076,
  "scaleY": 1.02290076,
  "origin": {"x": 0.0, "y": 1.2443},
  "letterbox": {"x": 0.0, "y": 0.0},
  "contentBox": {"x": 0.0, "y": 1.244, "width": 402.0, "height": 871.511},
  "padding": {"left": 0.0, "top": 1.2443, "right": 0.0, "bottom": 1.2443, "max": 1.2443},
  "coordinateMapper": {
    "forward": {
      "x": "(lanhuX - letterbox.x) * scaleX + origin.x",
      "y": "(lanhuY - letterbox.y) * scaleY + origin.y",
      "width": "lanhuWidth * scaleX",
      "height": "lanhuHeight * scaleY"
    },
    "inverse": {
      "x": "(deviceX - origin.x) / scaleX + letterbox.x",
      "y": "(deviceY - origin.y) / scaleY + letterbox.y",
      "width": "deviceWidth / scaleX",
      "height": "deviceHeight / scaleY"
    }
  }
}
```

**`policy` 必填，默认 `fit`。** 393×852 → 402×874 时 `fit = 1.02290`（`scaleX == scaleY`）、
`fill = 1.02582`（`scaleX = 1.02290`、`scaleY = 1.02582`）。两者差 0.28%，在 852pt 高的画布上
等于 **2.4pt 累计错位**，已超过 2pt 的位置容差。因此：

- 缺省一律 `fit`（等比缩放并居中，余量均分为 letterbox）；
- 需要 `fill` 或 `custom` 时必须同时写 `reason`，不得默默拉伸；
- 不得为了让某个区域的位置对上而改 `policy` —— 那是拿整体比例去掩盖局部实现错误。

**`coordinateMapper` 必须同时含 `forward` 与 `inverse`。** 只定义正向时，任何从截图反推
Lanhu 坐标的分析代码都得自己反解，而手写反解正是「多乘一层 scaleY」的来源。实际换算一律
走 `scripts/canvas_map.py`，它由 `canvasTransform` 或 `runtime-device.json + 画布尺寸` 构造，
并保证 `inverse(forward(box)) == box`（见其 `--self-test`）。

### 布局关系与控件尺寸的约束口径（强制）

**尺寸是常量，位置是约束。** 组件尺寸照设计稿的封闭值写死（按钮高 44pt 就写 44），
不随容器缩放；位置相对**直接父视图**表达 —— 贴边写约束闭合、居中写对齐锚点，
**确属成比例关系时才用比例**。

反过来那句同样成立：把位置写成某一台设备上量出来的绝对坐标（`lanhuY = 132` 换算成
`132 * 1.0229 = 135.02pt` 再敲进约束），等于把这个关系钉死在探针设备上。换一台设备，
`135.02` 就是错的 —— 而它「有出处、算过」，比一眼可疑的魔数更难被发现。

> 两轴各自的可选类别（尺寸轴：`fixed` / `pinned` / `intrinsic` / `proportional`；
> 位置轴：`pinned` / `centered` / `proportional`）见
> [sizing-and-positioning.md](sizing-and-positioning.md) 与
> [`layoutProportions`](#ui-implementation-planjson-的-layoutproportions)。

#### 哪些量用哪一类关系

判据只有一个：**这个量的正确性是否依赖于容器尺寸？**

> **范围边界（重要）**：这条约束管的是**位置与容器的闭合关系**，**不管控件自身的尺寸**。
> 控件尺寸（按钮、文字、图标）必须与设计稿保持固定的绝对大小，不随屏幕或容器比例缩放；
> 位置基准是**直接父视图**而不是页面根。这两条与完整的三分类判据见
> [sizing-and-positioning.md](sizing-and-positioning.md) —— 该文是本节的权威展开，
> 下表与之冲突时以该文为准。

| 类别 | 处理 | 例 |
|---|---|---|
| 控件尺寸（按钮高、图标、头像、字号） | **固定设计值，不缩放** | 按钮高 44pt、图标 24pt、正文 17pt |
| 组件在主轴/次轴上的位置 | **相对直接父视图的约束**；确属成比例关系时才用比例 | 卡片内标题距卡片顶 24pt |
| 组件之间的间距 | **设计常量**（标准边距 4/8/16/24） | 卡片间距 16pt |
| 容器、装饰性区域、图片 frame 的尺寸 | **贴父派生**：写成对父视图的约束（贴边、占满、等分），**不带比例系数** | hero 背景四边贴 0、全宽 CTA 左右各 16pt |
| 确随父容器成比例变化的关系 | **比例**（基准是父视图，且须给理由） | 装饰区高度 = 父容器高度 × 0.155 |
| 文本驱动的固有尺寸 | 按内容撑开 | 标签高度由字号与行高决定 |
| 圆角、描边宽度、阴影、最小点击区 | **设计值，不缩放** | 圆角 12pt、点击区 ≥ 44pt |

**「贴父」不等于「比例」。** 设计稿说「左右各 16pt」，正确写法是
`leading = parent.leading + 16` / `trailing = parent.trailing - 16`，这条关系已经闭合；
改写成 `width = parent.width * 0.9186` 在探针设备上同样「对得上」，但 430pt 宽的设备上
会得到 13.7pt 边距 —— 设计稿说的是 16pt。

**禁止用比例去缩放字号和最小点击区。** 那会让 44pt 的点击区在小屏上缩成 40pt，
既违反平台规范，也让可访问性测试失败。

#### 平台惯用法

| 模式 | 比例的表达方式 |
|---|---|
| UIKit（Swift / Objective-C） | `NSLayoutConstraint` 的 `multiplier`、`UILayoutGuide` 占位 |
| SwiftUI | `GeometryReader` + 归一化计算、`.containerRelativeFrame` |
| Compose | `BoxWithConstraints` 的 `maxWidth` / `maxHeight` 派生比例、`weight` |
| Views / XML | `layout_constraintGuide_percent`、`layout_constraintHorizontal_bias`、`layout_constraintDimensionRatio`、LinearLayout 的 `layout_weight` |

#### 比例模型与 `fit` 策略的关系

`fit` 映射（`deviceY = lanhuY * scaleY + origin.y`）与比例映射
（`deviceY = (lanhuY / canvasH) * deviceH`）是两条直线，在纵横比不同的设备上并不等价：
它们在画布中段相交，向两端分岔，**最大偏差恰好等于 letterbox 的厚度**，也就是
`canvasTransform.padding.max`。于是判据是现成的：

- `padding.max <= 位置容差（2pt）` ⇒ 两种模型在容差内等价，`fit` 的预测框可以直接与
  比例实现比对，不需要额外处理；
- `padding.max > 位置容差` ⇒ 二者不可互换。此时实现必须用比例模型，**并且对齐审计也必须
  改用比例模型预测**，否则就是拿 `fit` 的预测框去量一个按比例布局的界面，把模型差报成实现错误。

393×852 → 402×874 时 `padding.max = 1.2443pt`，仍在容差内 —— 但这是**算出来的**结论，
不是可以假设的前提。`scripts/canvas_map.py` 的 `axis_deviation()` 给出这个值。

#### `ui-implementation-plan.json` 的 `layoutProportions`

由 `scripts/layout_proportions.py` 从 `page-facts.json` 生成。**字段以实际产物为准**，下面是
真实结构（数值取自 402×874 探针设备上的 Special Offer 页；原始素材在评测套件里，
路径 `evals/fixtures/device-derived-layout/` —— 那个目录不会装到被测工程上，
所以这里只写路径不做链接）：

```json
{
  "model": "fixed-size-parent-relative-position",
  "basis": "viewport",
  "axisPolicy": "per-axis",
  "basisSize": {"width": 402, "height": 874},
  "regions": [
    {
      "region": "offers",
      "index": 2,
      "parentIndex": 0,
      "parent": "page",
      "basis": "parent",
      "kindSource": "proposed",
      "ratios": {"xRatio": 0.058524, "yRatio": 0.580986,
                 "widthRatio": 0.882952, "heightRatio": 0.079812,
                 "centerXRatio": 0.5, "centerYRatio": 0.620892},
      "relations": [
        {"id": "offers.x", "axis": "x", "of": "page", "ofIndex": 0,
         "kind": "pinned", "edge": "leading", "inset": 23.0,
         "note": "贴父边 + 固定间距：这是约束闭合，不是比例"},
        {"id": "offers.y", "axis": "y", "of": "page", "ofIndex": 0,
         "kind": "proportional", "ratio": 0.580986,
         "note": "确属随父容器成比例变化的位置关系；基准是父视图，不是整页"},
        {"id": "offers.width", "axis": "width", "of": "page", "ofIndex": 0,
         "kind": "pinned", "edges": ["leading", "trailing"],
         "insets": {"leading": 23.0, "trailing": 23.0}, "inset": 23.0,
         "why": "两侧各留 23pt 内边距：值由内边距闭合，随父容器伸缩，而内边距本身是设计常量"},
        {"id": "offers.height", "axis": "height", "of": "page", "ofIndex": 0,
         "kind": "fixed", "value": 68}
      ],
      "nativeIdiom": [
        "[offers] leadingAnchor.constraint(equalTo: page.leadingAnchor, constant: 23)   // offers.x 贴边约束，不是比例",
        "[offers] centerYAnchor.constraint(equalTo: page.heightAnchor, multiplier: 0.580986)   // offers.y",
        "[offers] heightAnchor.constraint(equalToConstant: 68)   // offers.height 设计值，不随容器缩放"
      ]
    },
    {
      "region": "legal",
      "index": 4,
      "parentIndex": 0,
      "parent": "page",
      "basis": "parent",
      "relations": [
        {"id": "legal.x", "axis": "x", "of": "page", "ofIndex": 0,
         "kind": "proportional", "ratio": 0.211196},
        {"id": "legal.width", "axis": "width", "of": "page", "ofIndex": 0,
         "kind": "intrinsic",
         "why": "盒子宽度 232pt 且子树含文本，判为文字块：尺寸来自字体"}
      ]
    }
  ],
  "forbiddenLiterals": [
    {"relation": "offers.top", "deviceDerivedPt": 495.0,
     "why": "探针设备视口 402x874 上的绝对值，换台设备即失效，不得写成字面量",
     "ratioInstead": 0.580986},
    {"relation": "legal.leading", "deviceDerivedPt": 83.0,
     "why": "…用 leading/左边缘锚点时写这个绝对值是错的", "ratioInstead": 0.211196}
  ],
  "designConstantCandidates": {
    "pinnedInsets": [16.0, 23.0, 25.0],
    "note": "贴边内边距与 fixed 尺寸都是应当写的设计值；把内边距填进 designConstants，fixed 尺寸由 kind=fixed 的 value 自带"
  }
}
```

五条规则，每一条都对应一次踩坑：

1. **`relations[].kind` 必填，而且决定判据。** 尺寸轴四类 —— `fixed`（必须给 `value`：设计稿的
   封闭值，实现时**写字面量**）、`pinned`（必须给 `edges`：贴父边/占满/等分闭合，**不得带比例
   系数**）、`intrinsic`（必须给 `why`，不带 `axis`）、`proportional`；位置轴三类 —— `pinned`
   （贴边 + 固定 `inset`）、`centered`（对齐锚点）、`proportional`（必须给 `ratio` 与 `of`）。
   `fixed` 带上 `ratio`、`pinned` 带上 `multiplier` 都是自相矛盾，校验器直接判死。
2. **`basis` 与关系里的 `of` 必须指向直接父视图。** 事实表 v3 的 `parentIndex` 给出了层级：
   有父视图时 `basis` 就该是 `"parent"`、`of` 写父区域名；只有 `parentIndex` 为 `null`
   （直接父即整屏画布）才用 `of: "root"`。两者对不上会被判 `basis-mismatch` —— 单页单设备上
   两种写法给出的坐标**完全一样**，父容器一变尺寸就分道扬镳。
3. **`ratios` 同时给边缘与中心两套。** 实现侧两种锚点都会用到（`leading`/`top` 与
   `centerX`/`centerY`），只给中心比例会让「按左边缘对齐」这个最常见的写法没有可用的比例。
4. **`forbiddenLiterals` 只收 `proportional` 的关系。** `fixed` 的 `value` 与 `pinned` 的
   `inset` 都是**应当原样写进代码**的设计值，列进去等于要求实现者不要按设计稿做
   （校验器的 `forbidden-targets-non-proportional` 就是拦这个）。条目还必须**同量纲配对**：
   中心比例配中心点绝对值（`legal.centerX` → 0.506361），边缘比例配左/上边缘绝对值
   （`legal.leading` → 0.211196）。曾经把左边缘的绝对值（多为 0）配给中心比例，写成
   「0pt → 0.4888」—— 开发者照做会把元素放错半个身位，**这条「指导」本身就是错的**。
   `|pt| < 1` 的条目不入清单：`0` 在任何设备上都成立，列进去只会让每个 `0` 都报一次警。
5. **`designConstantCandidates` 是可复核的提示，`designConstants` 才是豁免。** 前者由生成端
   汇总贴边内边距（省得 Agent 去源码里翻），后者是计划里手写的数字数组，只能放数字
   （标准边距、圆角）。它不是「随手写个数字就放行」：豁免值会原样写进校验结果，审阅者看得到。

`rect` 的坐标空间由「`rectInReference == rect * devicePixelRatio`」**自动判定**，判不出来就
退出 2 并给出原因，绝不猜 —— 猜错会把 scale 乘两遍（`rect` 已经是设备点）。需要按 Lanhu 画布
空间算时用 `--rect-space lanhu` 显式指定，此时会告警提示与证据冲突。

校验走 `scripts/check_layout_proportions.py`，它**是计划驱动，不是正则扫描**：每一类关系都有
它自己的判据 —— `proportional` 要求比例原语，`fixed` 要求写字面量，`pinned` 要求贴边闭合且
不带系数，`intrinsic` 要求给出理由。纯正则扫描做不到这件事：它会把合法的设计常量
（圆角 12、标准边距 16）一起误报，训练出「看到告警就忽略」的习惯。

判定分两档，理由是**闸门要准，不是要响**：

- `forbidden-literal-used`（违规）—— 数值 > 48pt，不可能是手选的设计常量（没人把 393pt 当圆角）；
- `ambiguous-literal`（待判，不计入违规）—— 数值 ≤ 48pt 时与常见设计常量无法区分，列出待人工确认。

注意 `48pt` 这条线是**量级**判据，与 `kind` 判据是两回事：一条被声明为 `proportional` 的
关系在探针设备上算出 25pt，那是它落进了「待判」而不是「违规」—— 因为 25pt 既可能是抄来的
设备值，也可能是设计常量。**两轴口径下更该信 `kind`**：计划说 `pinned`，那 25pt 就是应当写的
内边距；计划说 `proportional`，那个绝对值才是错的。

注释里的数字、`100%`、`colorWithRed:22 / 255.0` 这类非布局数字一律跳过。

### `diff/` 的三类结论

| 文件 | 产出脚本 | 作用 |
|---|---|---|
| `comparison.json`（或 `full-page.json`） | `scripts/compare_reference.py` | 像素比较：`structuralRatio` / `textureRatio` / `fillRatio` 三分 + `regions` 区域明细 |
| `alignment.json` | `scripts/audit_alignment.py` | 元素级位移：`domVsReference` 与 `referenceVsActual` 两组比较 |
| `font-chain.json` | `scripts/audit_fonts.py` | 基准字体链：逐元素比对 CSS 声明的族与运行时实际用上的族 |

`font-chain.json` 的字段：`status`（`clean` / `substituted` / `insufficient-evidence`）、
`substituted`（true / false / null）、`missingFamilies`（声明了却没落地的族）、
`landedFamilies`（实际回落到什么）、`affectedElements`（含 `index` / 文本 / `advanceWidth`）、
`evidence`、`fixSide`（`baseline` / `none`）。`substituted` 为 `null` 表示证据不足 ——
事实表没做过字体测量，或 `fontMeasurement.ok` / `fontJoin.ok` 为 `false`。**不要**把
「证据不足」当成「没问题」。

比较结论的三分法不是分类癖好，而是判定的前提：

- `structuralRatio` —— 强边在两张图里对不上（`--edge-tolerance` 内找不到对应）。几何错位、
  尺寸变化、圆角/间距改错。超过 `maxStructuralRatio` 判 `fail`。
- `fillRatio` —— 平坦区颜色不同。填充色/背景色/文字颜色写错、整块缺遮罩。超过
  `maxFillRatio` 判 `fail`。
- `textureRatio` —— 几何一致、只是像素值不同（字体栅格化、抗锯齿、次像素相位差）。
  **不参与放行判定**。

判定只看前两类。把它们混在 `changedRatio` 里会双输：抗锯齿多的页面（HTML 侧用 Web 字体、
App 侧用系统字体）永远撞上限而无法交付，而真正错位的图只要背景色接近也可能因为纹理差异低
而侥幸通过。

`alignment.json` 把「谁和谁不符」分成两个需要**相反动作**的故障：

```json
{
  "schemaVersion": 1,
  "status": "needs-review",
  "reason": "constant-offset",
  "comparisons": {
    "domVsReference":    {"status": "aligned",      "reason": null},
    "referenceVsActual": {"status": "needs-review", "reason": "constant-offset",
                          "domDisagrees": false}
  }
}
```

- `domVsReference` 不符 ⇒ **基准不可信**（渲染 viewport/scale 与采集事实表时不一致）。
  先重修基准，**不要**照着基准图调 App 代码。
- `referenceVsActual` 不符 ⇒ 基准可信，问题在 App 实现侧，按区域改代码。
- 判 `needs-review` 时 `delivery-gate.status.visualDiff` 不得为 `pass`。

### `runtime-device.json`

```json
{
  "schemaVersion": 1,
  "platform": "iOS Simulator",
  "device": "iPhone 17",
  "udid": "006735BF-E25E-4629-8405-3CCE87156171",
  "source": "runtime NSLog from UIScreen and UIView bounds",
  "screenBoundsPoints": {"width": 402, "height": 874},
  "rootViewBoundsPoints": {"width": 402, "height": 874},
  "screenshotPixels": {"width": 1206, "height": 2622},
  "screenshotScale": 3,
  "evidence": "actual/runtime.log"
}
```

`screenBoundsPoints` 与 `screenshotScale` 必须来自运行时 API，禁止由设备型号推断；
`reference.png` 的像素尺寸必须等于 `screenshotPixels`（见 `SKILL.md` 的画布契约）。

## 已废弃字段与文件

| 旧产物 | 现状 | 取代者 |
|---|---|---|
| `visual-review.json` | 废弃 | `review.json` 的观察/验证字段 |
| `manifest.json` | 废弃 | `run.json` |
| run 级 `assets/` | 废弃 | `resource-policy.json` + 页面 `source/assets-manifest.json` |
| run 级 `page-facts.json` / `browser-meta.json` | 废弃 | 页面级 `reference/` 下的同名文件 |
| run 级 `canvas-transform.json` | 废弃 | `ui-implementation-plan.json` 的 `canvasTransform` |

历史 run 不需要迁移：在 `run.json` 中标记 `"legacy": true` 后，校验脚本跳过上述必需项，
但**不得**据此把页面判为 `ready`。

## 禁止事项

- 禁止把多个页面或多个目标模式的产物放在同一 run 目录。
- 禁止用 `latest.json` 或文件修改时间猜「最新 run」，一律按 run ID 读取。
- 禁止删除历史 run 来「清理」失败证据；只能把页面状态改为 `archived`。
- 禁止让脚本生成或覆盖生产源码：`.ihereforUI` 只保存事实、证据、计划和索引。
