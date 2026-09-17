# 产物契约

本文件是 `.ihereforUI` 产物结构的**唯一事实来源**。`SKILL.md`、`project-management.md`
与 `scripts/validate_run.py` 都以本文件为准；出现分歧时先改本文件，再同步其他两处。

> **`v3` 起的主链路变更**：几何坐标以 `dds-schema.json` 的 `bounds` 为主链路（见页面级
> **主链路（v3 起）**：几何坐标以 `dds-schema.json` 的 `bounds` 为主链路，样式恒量以
> `inspect_design_region` 的 `raw_style` 为准（legacy 的官方 HTML/CSS 仅参考），切图以
> `lanhu_export_design_assets` 为准。渲染 DOM 的 `page-facts.json`、像素 `diff/`、`canvasTransform` 坐标换算等
> **渲染链产物已整体删除**，不再属于本契约的任何流程。

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
└── reference/                   # 当前**已批准**的几何基准（冻结）
    ├── dds-schema.json          # bounds 几何事实（主链路，组件位置/尺寸/父子归属）
    ├── design-document.json     # （已废弃）旧 lanhu_get_design_document 原始返回体，仅交叉佐证用
    ├── design-facts.json        # （已废弃）旧工具产物，仅佐证图层几何/描边/纯色填充，不参与权威判定
    └── approved.json            # 批准记录：sha256、批准时间、批准人
```

几何基准（`dds-schema.json`）属于**基准**，因此放在页面级而不是 run 级：只有显式批准才
写入 `approved.json`。

### `design-facts.json`（已废弃，由已经下架的 `lanhu_get_design_document` + `scripts/lanhu_design_facts.py` 产出，当前 MCP 不再生成）

`design-facts.json` 是已下架工具 `lanhu_get_design_document` 返回体的**降噪摘要**，回答「设计稿说
应该什么样」。它是**可选交叉佐证**，只可靠地覆盖**图层几何（`rect`）与描边/纯色填充**这一小半；
字号、渐变、文本语义存在系统性失真（`canvas.scale` 折半字号、`metadata.parentId` 全 null）。
当前 MCP 已无此工具，如须回看 Sketch 帧请改用 `lanhu_inspect_design_region`。

**几何的权威来源是 `dds-schema.json` 的 `bounds`（主链路），渲染 DOM 的 `page-facts.json` 是备用链路**
——凡是 bounds 或 page-facts 已给出、计划却写成 `kindSource: "agent-decided"` 或
凭空编造常量值的，都属可消除推断。`bounds` 缺失/不可信时以渲染 DOM 为准；`design-facts` 与
两个权威来源不一致时，以权威来源为准并记归因信号。

```json
{
  "source": {"name": "目的", "imageId": "…", "projectId": "…",
             "canvas": {"width": 393, "height": 852, "scale": 2, "device": "iOS @1x"}},
  "scale": {"canvasScale": 2.0, "fontSizeScaled": true,
            "note": "rect 坐标未缩放；fontSize 已按 canvas.scale 还原，fontSizeRaw 是 document 原文"},
  "summary": {"layerCount": 64, "rootCount": 8, "typographyCount": 15,
              "borderCount": 7, "fillCount": 20, "shadowCount": 0,
              "visibleFalseCount": 0, "exportImageCount": 22,
              "depthDistribution": {"0": 8, "1": 31, "2": 19, "3": 4, "4": 1, "5": 1}},
  "roots": [{"id": "…", "name": "矩形"}],
  "hierarchy": [{"id": "…", "name": "椭圆形", "parentId": "4D8E1C99…", "depth": 1}],
  "typography": [{"id": "…", "name": "Continue", "rect": {"x": 77, "y": 372.5, "width": 68, "height": 22},
                  "parentId": "4D8E1C99…", "depth": 1, "text": "Continue",
                  "fontFamily": "Avenir-Black", "fontFamilyRaw": "AvenirLT-Black",
                  "fontSize": 14.0, "fontSizeRaw": 7, "fontWeight": 400,
                  "lineHeight": 14, "letterSpacing": 0, "textAlign": "left", "color": "#1A1A1A"}],
  "borders": [{"id": "…", "name": "Border", "borders": [{"color": {"…": "rgba(0,0,0,1)"}, "width": 0.5, "style": "solid", "radius": 0}]}],
  "fills": [], "shadows": []
}
```

关键字段约定：

| 字段 | 含义 |
|---|---|
| `scale.canvasScale` / `scale.fontSizeScaled` | 画布 scale 及「是否对字号做了还原」。**`rect` 坐标是未缩放的画布点坐标，但 `fontSize` 已按 scale 还原**（`fontSizeRaw` 是 document 原文） |
| `hierarchy[].parentId` / `depth` | 父视图归属**由 `parent_id`/`source_parent_id` 推导**（`metadata.parentId` 实测全 null 不可靠）；`parent_id == null` 即根层。**仅供佐证，`regions[].parentIndex` 的权威来源是 `dds-schema.json` 的 `parent_id`（主链路），`bounds` 缺失时才是 `page-facts.json` 的 `parentIndex`/`parentHops`** |
| `typography[].fontSize` / `fontSizeRaw` | `fontSize` 是还原后的字号（**可能存在 scale 折半失真，勿当权威**），`fontSizeRaw` 是 document 原文（已除过 scale） |
| `typography[].fontFamily` / `fontFamilyRaw` | `fontFamily` 已 normalize（`AvenirLT-*` → `Avenir-*`），`fontFamilyRaw` 是 document 原声明；**权威字号/字体以 `inspect_design_region` 的 `raw_style` 为准，渲染 DOM 实测为辅（备用链路）** |
| `borders[].borders[].width` | 描边粗细，回答「描边画在 frame 上还是独立装饰层」 |
| `summary.depthDistribution` | 层级深度分布，快速判断画布叠层复杂度 |

**几何权威是 `bounds`（`dds-schema.json`，主链路），渲染 DOM（`page-facts.json`）是备用链路；样式权威是 `inspect_design_region` 的 `raw_style`（legacy 官方 HTML/CSS 仅参考）。** `design-facts` 只是可选佐证，给**声明值**（图层几何、描边、纯色填充）；
`bounds` 给**语义几何**（绝对坐标 + `parent_id` 父子归属），`page-facts` 给**渲染实测值**（父视图归属 `parentIndex`、`rectInReference`、字号、实际命中字体 `fontsResolved`、`advanceWidth`、计算后样式、颜色）。
几何不一致时以 `bounds` 为准、`bounds` 缺失时以渲染 DOM 为准；样式不一致时以 `raw_style` 为准，并把差异记为归因信号；
「字体上声明 vs 命中」（`AvenirLT-*` 声明了却不存在的族名）是已知的正确差异，不做交叉核对产生噪音。

## 运行级（每次 run 必需）

| 文件 | 必需条件 | 内容 |
|---|---|---|
| `run.json` | always | 运行标识、目标模式、父 run、基准哈希、状态 |
| `review.json` | always | 观察 / 假设 / 变更 / 验证 / 下一步（含 `parentRunId`） |
| `delivery-gate.json` | always | 6 项基础闸门状态（声明 `adaptiveLayout` 时为 7 项）、`unsupported` 计数、`deliveryReady` |
| `ui-implementation-plan.json` | always | 本次实现的区域、坐标系、资源映射、`runtimeRisks`、`adaptiveLayout` 与 `unsupported` |
| `resource-policy.json` | always | 资源目录决策、复用与新增、语义命名 |
| `过程中页面分析表.md` | always | 第 2 步元素梳理摊平表：几何（`bounds`）+ 样式（`raw_style`）+ 资源 + 组件映射的单元素视图 |
| `最终页面分析表.md` | always | 第 5 步验证对照表：关键元素实测几何 vs 设计稿 `bounds`，含偏差 / 状态 / 宽度档 |
| `runtime-device.json` | 所有目标模式 | 运行时尺寸 API 返回值 |
| `adaptive-targets.json` | 声明了 `adaptiveLayout` | 宽度档采样清单与各自的几何证据位置 |
| `ios-environment.json` | iOS 目标模式 | 工程入口、scheme、destination 探测结果 |
| `actual/` | always | 构建/测试日志 |
| `diff/` | always | 结构/纹理/填充三分与区域差异摘要；元素级对齐审计 `alignment.json`；基准字体链 `font-chain.json`；自适应几何审计 `adaptive-audit.json`（声明 `adaptiveLayout` 时必需） |

### `run.json`

```json
{
  "schemaVersion": 1,
  "runId": "20260907-150000-objc-011",
  "pageId": "plan-selection",
  "targetMode": "ios-uikit-objective-c",
  "parentRunId": "20260907-140000-objc-010",
  "createdAt": "2026-09-07T15:00:00+08:00",
  "referenceBaseline": {"approved": "reference/approved.json", "sha256": "<dds-schema.json 哈希>"},
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
  "observations": [{"region": "title", "category": "geometry", "evidence": ["reference/dds-schema.json"]}],
  "hypotheses": ["safe-area 自动 inset 与 Lanhu underlap 重复计算"],
  "changes": [{"file": "testUIProject/SubscriptionPlanSelectionViewController.m", "reason": "关闭自动 content inset"}],
  "verification": {"build": "pass", "tests": "pass", "runtimeDevice": "runtime-device.json"},
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
    "source": "pass",
    "sourceAssets": "pass",
    "implementation": "pass",
    "build": "pass",
    "tests": "pass",
    "adaptiveAudit": "not-run"
  },
  "unsupported": {"count": 0, "reviewedCount": 0, "items": []},
  "deliveryReady": false,
  "blockingReasons": ["adaptiveAudit=not-run"]
}
```

每个状态取值：`pass` | `pass-with-review` | `fail` | `not-run`。

**`adaptiveAudit` 是条件必需的第七项**：`ui-implementation-plan.json` 声明了
`adaptiveLayout` 时，`status` 必须包含该键；未声明时不要求，写进去也必须取合法值。
它是**几何契约审计**，不做像素比对 —— 理由见
[adaptive-layout.md §7](adaptive-layout.md#7-验证adaptiveaudit-与为什么不做像素-diff)。

`deliveryReady` 为 `true` 的**充要条件**（校验脚本按此判定，不接受手写覆盖）：

1. **本次适用的全部闸门**为 `pass` —— 基础 6 项，加上声明了 `adaptiveLayout` 时的
   `adaptiveAudit`（第 7 项）；
2. `unsupported.count == unsupported.reviewedCount`（不存在未审查的降级项）；
3. `unsupported` 的两个计数必须是**可读的整数**。

第 3 条的意思是「推不出来就别推」：`unsupported` 对象缺失、或 `count` / `reviewedCount`
不是整数（例如写成字符串 `"2"`）时，`delivery-gate.json` 本身已经不合规，校验脚本会**跳过**
`deliveryReady` 的一致性核对并留下告警，由你去补齐结构，它不会替你补一个取值。特别地，
**不会**把它推导成 `true` —— 缺字段时按「复核完毕」算（`None == None`），等于让「没做人工
复核」成为放行理由，这是必须堵死的一条。

前两条不满足时 `deliveryReady` 必须为 `false`，并在 `blockingReasons` 中列出原因；
第 3 条不满足时先补齐结构，再谈 `deliveryReady`。

### `过程中页面分析表.md` 与 `最终页面分析表.md`

这两个是 run 级必产的人读追踪表（.md），是权威事实的**摊平/对照视图**，不是新权威：

- `过程中页面分析表.md`（第 2 步）——把 `dds-schema.json` 的几何（`nodes[].bounds`）与
  `inspect_design_region` 的 `raw_style`（样式）按 `parent_id` 摊到同一行的单元素视图。
  列：元素 / 层级 / bounds(x/y/w/h) / 语义尺寸 / 字号字重 / 字体族 / 颜色透明度 / 圆角 /
  描边 / 渐变阴影 / 资源切图 / overflow / z-index / 原生组件映射 / 交互状态 / 待确认。
- `最终页面分析表.md`（第 5 步）——关键元素实测渲染几何 vs 设计稿 `bounds` 的对照。
  列：元素 / 实测 y/x / 实测尺寸 / 设计稿比例值 y/x / 设计稿尺寸 / 偏差 / 状态 / 宽度档 / 备注证据。

**硬约束**：

1. 表内数值必须与权威来源逐字一致（几何照抄 `bounds`、样式照抄 `raw_style`），不得在整理时改值、
   不得编造缺失字段（缺失标 `—`）。表用于索引与排查，落码仍以权威源为准。
2. 两个文件都用**精确文件名**（中文），缺任一判 `缺少必需产物`（由 `validate_run.py` 执行）。
3. `最终页面分析表.md` 的「实测」由 Agent 采样自核，必须注明证据出处（哪份 `geometry-*.json`、
   哪张截图、哪行日志）；声明 `adaptiveLayout` 时「宽度档」列需覆盖各采样档。

### 布局关系与控件尺寸的约束口径（强制）

**设计稿尺寸是参考事实，运行时尺寸由约束闭合。** 判据是**「这个值由谁闭合」**，不是「这个值等于设计稿的几」。
每个尺寸必须声明它的闭合方式（尺寸轴：`fixed` / `intrinsic` / `bounded` / `aspect-ratio`；
关系轴：`pinned` / `proportional` / `equal` / `centered`），位置相对**直接父视图**表达 ——
贴边写约束闭合、居中写对齐锚点，**确属成比例关系时才用比例**。

两个错误方向要同时挡住：

1. **把整页当成一张图缩放**：等于把「设计稿恰好 393pt 宽」这个偶然事实提升成布局规则。
2. **把设计稿的每个 width/height 逐字写成固定约束**：这是旧契约的默认行为，也是最致命的缺点。
   `bounds.width = 220` 是「设计稿在这台设备上量到的 220」，不是「这个元素永远该是 220」。

`fixed` **不是默认值**，它只用于「固定性本身就是设计意图」的视觉常量：图标、装饰、边框、
明确固定高度的视觉控件。文本、按钮、容器和内容区域默认优先 `intrinsic` / `bounded`。

反过来那句同样成立：把位置写成某一台设备上量出来的绝对坐标（`lanhuY = 132` 换算成
`132 * 1.0229 = 135.02pt` 再敲进约束），等于把这个关系钉死在探针设备上。换一台设备，
`135.02` 就是错的 —— 而它「有出处、算过」，比一眼可疑的魔数更难被发现。

> 两轴各自的可选类别与逐类判据见 [sizing-and-positioning.md](sizing-and-positioning.md)
> §2 与 §3；iOS 侧的逐类 UIKit 写法、优先级策略与运行期验证见
> [ios-autolayout-practice.md](ios-autolayout-practice.md)。

#### 哪些量用哪一类关系

判据只有一个：**这个值由谁闭合？**

> **范围边界（重要）**：位置与尺寸**都要**按闭合方式声明，但两者的判据不同 ——
> 位置问「相对哪条父边/哪个兄弟」，尺寸问「由设计常量、内容、父约束还是比例决定」。
> **不存在「控件尺寸一律取设计值」这类豁免**：控件尺寸同样要按闭合方式判，
> 只有「视觉常量」这一小组才天然用 `fixed`。完整判据见
> [sizing-and-positioning.md](sizing-and-positioning.md) —— 该文是本节的权威展开，
> 下表与之冲突时以该文为准。

| 类别 | `kind` | 处理 | 例 |
|---|---|---|---|
| 视觉常量（图标、头像、装饰、边框、分隔线、字号、圆角、描边、触控下限） | `fixed`（触控下限用 `bounded >= `） | **固定设计值，不缩放**，须给 `why` | 图标 24pt、圆角 12pt、描边 1pt、正文 17pt |
| 文本、标签、按钮内容 | `intrinsic` | 按内容撑开，不给宽高约束，须给 `why` | 标签高度由字号与行高决定 |
| 内容列、卡片、按钮的宽高边界 | `bounded` | 给 `min` / `max` 至少一个 | 内容列 `maxWidth = 640`、按钮 `height >= 44` |
| 组件在主轴/次轴上的位置 | `pinned` | **相对直接父视图的约束**；确属成比例关系时才用比例 | 卡片内标题距卡片顶 24pt |
| **第一层子视图的位置**（直接父 = 页面） | `pinned` + 比例 | **按页面比例**：水平 `x = page.width × ratio`、垂直 `y = page.height × ratio`；**不得**写成绝对坐标 | 卡片挂在 page 下，`x = 0.0407`、`y = 0.1373`（相对 page） |
| 组件之间的间距 | `pinned` | **设计常量边距**（标准边距 4/8/16/24） | 卡片间距 16pt |
| 容器、装饰性区域、图片 frame 的尺寸 | `pinned` / `bounded` / `aspect-ratio` | 写成对父视图的约束（贴边、占满、等分）或比例约束，**不带无理由的比例系数** | hero 背景四边贴 0、全宽 CTA 左右各 16pt、封面图 16:9 |
| 确随父容器成比例变化的关系 | `proportional` | **比例**（基准是父视图，且须给理由） | 装饰区高度 = 父容器高度 × 0.155 |
| 多个兄弟要等宽/等高 | `equal` | 等值锚点，须给 `with`/`to` | 两个套餐卡等宽 |
| 居中或与兄弟对齐 | `centered` | `centerX` / `centerY` / `baseline` 相等 | 标题居中、图标与文字基线对齐 |

**「贴父」不等于「比例」。** 设计稿说「左右各 16pt」，正确写法是
`leading = parent.leading + 16` / `trailing = parent.trailing - 16`，这条关系已经闭合；
改写成 `width = parent.width * 0.9186` 在探针设备上同样「对得上」，但 430pt 宽的设备上
会得到 13.7pt 边距 —— 设计稿说的是 16pt。

**第一层子视图的位置特殊，尺寸不特殊。** 当设备尺寸 ≠ 设计稿尺寸时，直接挂在页面下
的第一层子视图若仍只「贴边/居中」，水平方向不会随新宽度重新分布——那不是「适配成功」的观感。
所以第一层**位置**（水平 + 垂直）按**页面比例**表达（相对 page 的 `multiplier`），写到
`relations[].forced = "first-level"`；而第一层的**尺寸**仍按 §2 的闭合判据选择
—— 容器/文本/按钮优先 `intrinsic` / `bounded` / `pinned`，只有视觉常量用 `fixed`。
第一层 → 第二层的**相对关系**仍固定（第二层的位置基准是它的直接父视图，不是页面）。
判定依据是 `parentIndex == page 外框 index`，权威展开见
[sizing-and-positioning.md](sizing-and-positioning.md) §3.1.1。

**禁止用比例去缩放字号和最小点击区。** 那会让 44pt 的点击区在小屏上缩成 40pt，
既违反平台规范，也让可访问性测试失败。**也要禁止反过来把 44 写成固定高度**：它是下限，
用 `>=` 表达，大字号下允许增高。

#### 平台惯用法

| 模式 | 比例的表达方式 |
|---|---|
| UIKit（Swift / Objective-C） | `NSLayoutConstraint` 的 `multiplier`、`UILayoutGuide` 占位 |
| SwiftUI | `GeometryReader` + 归一化计算、`.containerRelativeFrame` |
| Compose | `BoxWithConstraints` 的 `maxWidth` / `maxHeight` 派生比例、`weight` |
| Views / XML | `layout_constraintGuide_percent`、`layout_constraintHorizontal_bias`、`layout_constraintDimensionRatio`、LinearLayout 的 `layout_weight` |

#### `ui-implementation-plan.json` 的 `typeFacts`（样式恒量的事实溯源）

上一节管的是「位置与容器的闭合关系」，字号/字体/颜色/描边/圆角这些**样式恒量**不在它的
范围里 —— 它们既不随容器缩放，也不贴父闭合，而是「拿设计稿的封闭值写死」。这些值以前的
来源是 Agent 自觉，没有任何一道门核对「它是抄来的，还是拍脑袋编的」。这正是
「只读 design_document / 跳过权威来源也能过闸门」的漏洞所在。

**几何（位置/尺寸/父归属）的权威是 `bounds`，样式恒量的权威是 `inspect_design_region` 的 `raw_style`（主），
legacy 的官方 HTML/CSS 或渲染 DOM 的 `page-facts`（备用）。** `typeFacts` 是每项**样式恒量**的强制溯源：写计划时，每个区域的字号、
字体族、颜色、描边、圆角必须带一个指向权威来源的引用，证明这个值不是臆测。

```json
{
  "typeFacts": [
    {
      "region": "主标题",
      "elementIndex": 3,
      "fontSize": 24,
      "fontFamily": "Avenir Black",
      "color": "#1A1A1A",
      "borderWidth": 0,
      "borderColor": null,
      "borderRadius": 0,
      "kindSource": "page-facts"
    },
    {
      "region": "CTA 按钮",
      "elementIndex": 9,
      "fontSize": 14,
      "fontFamily": "Avenir-Medium",
      "color": "#FFFFFF",
      "borderWidth": 0.5,
      "borderColor": "rgba(0,0,0,1)",
      "borderRadius": 22,
      "kindSource": "page-facts"
    }
  ]
}
```

字段约定：

| 字段 | 含义 |
|---|---|
| `region` | 该样式恒量归属的具名区域（与 `layoutProportions.regions[].region` 对齐） |
| `elementIndex` | **整数**，指向溯源目标：`kindSource: "page-facts"` 时是 `page-facts.json` 的 `elements[]` 下标；`kindSource: "html-css"` 时是官方 CSS 里对应的选择器序号（`styleSourceIndex`） |
| `fontSize` / `fontFamily` / `color` | 从权威来源回填的字号/字体族/颜色（`page-facts` 的 `style` + `primaryFont.familyName`，或官方 CSS 的声明值） |
| `borderWidth` / `borderColor` / `borderRadius` | 从权威来源回填的描边与圆角（`page-facts` 的 `border` / `style.borderRadius`，或官方 CSS） |
| `kindSource` | **`"page-facts"`（样式来自渲染 DOM 实测）或 `"html-css"`（样式来自官方 HTML/CSS 声明值）**。这是「这个值有据可查」的显式断言，不是层级归属的 `kindSource: proposed` |

**规则：**

1. **每个「文字/带描边的区域」都必须有一条 `typeFacts` 记录。** 缺少记录（比如做了一个标题
   却没写它的字号来源）会被门 0 判 `fact-source-missing`。
2. **引用必须指向真实存在的来源**：`page-facts` 时该元素的可识别特征（有 `ownText`、
   或 `border.widthPx > 0`）与这条记录声明的样式类型一致；`html-css` 时选择器在官方 CSS 里真实存在。
3. **`kindSource` 只能是 `"page-facts"` 或 `"html-css"`。** 写成 `"agent-decided"` 或 `"proposed"`
   都等于承认「这个值不是从权威来源抄来的」，门 0 直接判违规。
4. 值是**引用**不是**新建权威**：`fontSize` 与来源值不一致时，说明抄错了，应由人核对 ——
   校验器只做「有没有引用、引用合不合法」，不做纯值相等比对
   （`primaryFont.familyName` 与 `style.fontFamily` 因别名/字重可能本就不逐字相等，见字体链一节）。

这条规则的判据是**可执行的**：`scripts/check_layout_proportions.py --plan-only` 会交叉核对
引用是否落在可溯源的范围内、`typeFacts` 覆盖的区域是否都有记录。
没有这份溯源，Agent 依旧可以编一个 `fontSize=14` 让四个门全绿 —— 有了它，「不读权威来源」在
门 0 就被拦死，而不是等到像素 diff 才露馅。

#### `ui-implementation-plan.json` 的 `runtimeRisks`

「只能在运行期暴露、但**在写计划时就能决策**」的风险必须写进计划。它们一旦漏到第 5 步
（编译 / 运行 / 截图）才发现，就要重走一次编译截图；而它们本来是一次决策就能定下来的。

```json
{
  "runtimeRisks": {
    "interactionCoverage": [
      {"view": "BrushOptionCardView.ringView", "covers": "整张卡片",
       "userInteractionEnabled": false,
       "reason": "覆盖式描边子视图，最后添加且铺满卡片；置 YES 会吞掉卡片手势，截图看不出来"}
    ],
    "scrollInset": {
      "contentInsetAdjustmentBehavior": "never",
      "reason": "页面坐标已含系统区域，自动注入 safe-area inset 会让整页下移",
      "explicitContentInset": {"top": 0, "bottom": 0}
    },
    "systemBars": {"policy": "underlap", "foregroundInset": {"top": 135.02},
                   "reason": "HTML 基准的背景延伸到状态栏下方，前景内容用显式 inset"},
    "fontAvailability": [
      {"family": "PingFangTC", "requestedWeight": "Semibold",
       "availableWeights": ["Medium", "Regular", "Light", "Thin"],
       "resolution": "同族其它字重（不会掉到系统 UI 字体）",
       "checkedVia": "PingFangUI.ttc 的 name 表"}
    ]
  }
}
```

四条各自的理由：

- `interactionCoverage` —— 覆盖式装饰子视图（描边环、蒙版、渐变层）**默认必须
  `userInteractionEnabled = NO`**，只有确实要接收点击时才 YES。这类故障**截图完全看不出来**，
  像素 diff 也证明不了点击可用，只能靠第 5 步的真机坐标点击 + 事件日志。
- `scrollInset` —— 页面坐标已含系统区域时，UIKit 自动注入的 safe-area content inset
  会让整页下移。必须设 `never` 并显式给 `contentInset`。
- `systemBars` —— `underlap` / `inset` / `mixed` 三选一，依据是「HTML 基准有没有绘制到顶部系统区域」。
- `fontAvailability` —— 目标平台上每个字族**实际存在**的字重。用 `.ttc` 的 name 表核对，
  **不要猜**：`PingFangUI.ttc` 里只有 `PingFangTC-Medium`，没有 `PingFangTC-Semibold`；
  `fontWithName:` 会落到同族其它字重（实测墨迹宽 264px vs 基准 265px），而不是掉到
  系统 UI 字体（那会是 237.7px）。这一条不影响布局闸门，但决定了「字体差异该不该被当缺陷修」。

#### `ui-implementation-plan.json` 的 `layoutProportions`

由 `scripts/layout_proportions.py` 从 `bounds`（`dds-schema.json` 几何事实）**辅助生成声明片段**，
Agent 负责合并进 plan 并逐条核对 `kind`/`basis`/`of`（脚本是辅助、不是「脚本生成 = 计划完成」）。
**字段以实际产物为准**，下面是
真实结构（数值取自 402×874 探针设备上的 Special Offer 页；原始素材在评测套件里，
路径 `evals/fixtures/device-derived-layout/` —— 那个目录不会装到被测工程上，
所以这里只写路径不做链接）：

```json
{
  "model": "closure-declared-parent-relative-position",
  "basis": "viewport",
  "axisPolicy": "per-axis",
  "basisSize": {"width": 402, "height": 874},
  "regions": [
    {
      "region": "hero",
      "index": 1,
      "parentIndex": 0,
      "parent": "page",
      "basis": "parent",
      "relations": [
        {"id": "hero.width", "axis": "width", "of": "page", "ofIndex": 0,
         "kind": "pinned", "edges": ["leading", "trailing"],
         "insets": {"leading": 0.0, "trailing": 0.0},
         "why": "主视觉四边铺满：宽度由父容器边距闭合，不是 393 这个字面量"},
        {"id": "hero.height", "axis": "height", "of": "page", "ofIndex": 0,
         "kind": "aspect-ratio", "ratio": 1.2243,
         "why": "主视觉是位图资源，比例由资源自身决定；393:321 = 1.2243，宽度贴父后高度随之求解"}
      ],
      "nativeIdiom": [
        "[hero] leadingAnchor.constraint(equalTo: page.leadingAnchor)",
        "[hero] trailingAnchor.constraint(equalTo: page.trailingAnchor)",
        "[hero] heightAnchor.constraint(equalTo: hero.widthAnchor, multiplier: 1.0/1.2243)"
      ]
    },
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
         "kind": "intrinsic", "minimum": 68.0,
         "why": "卡片内含标题与价格文本，支持动态字体与多语言换行：高度由内容撑开，68 只作为下限"}
      ],
      "nativeIdiom": [
        "[offers] leadingAnchor.constraint(equalTo: page.leadingAnchor, constant: 23)   // offers.x 贴边约束，不是比例",
        "[offers] centerYAnchor.constraint(equalTo: page.heightAnchor, multiplier: 0.580986)   // offers.y",
        "[offers] heightAnchor.constraint(greaterThanOrEqualToConstant: 68)   // offers.height 是下限，不是固定高度"
      ]
    },
    {
      "region": "cta",
      "index": 3,
      "parentIndex": 0,
      "parent": "page",
      "basis": "parent",
      "relations": [
        {"id": "cta.x", "axis": "x", "of": "page", "ofIndex": 0,
         "kind": "pinned", "edge": "leading", "inset": 25.0},
        {"id": "cta.width", "axis": "width", "of": "page", "ofIndex": 0,
         "kind": "pinned", "edges": ["leading", "trailing"],
         "insets": {"leading": 25.0, "trailing": 25.0}, "inset": 25.0,
         "why": "宽度由两侧各 25pt 内边距闭合。**一条关系只声明一个 kind**：「贴两侧」已经是这个宽度的闭合方式，不再另挂 bounded；「不能再宽下去」的上限是**另一件事**，写在 adaptiveLayout 的 maxContentWidth 里（见下文 `ui-implementation-plan.json` 的 adaptiveLayout）"},
        {"id": "cta.height", "axis": "height", "of": "page", "ofIndex": 0,
         "kind": "bounded", "min": 44.0,
         "why": "48 是设计稿的视觉高度，44 是平台触控下限：写成 >= 44，大字号下允许增高而不是被压扁"}
      ],
      "nativeIdiom": [
        "[cta] leadingAnchor.constraint(equalTo: page.leadingAnchor, constant: 25)   // cta.width 的贴边闭合",
        "[cta] trailingAnchor.constraint(equalTo: page.trailingAnchor, constant: -25)",
        "[cta] heightAnchor.constraint(greaterThanOrEqualToConstant: 44)   // 不是 equalToConstant: 48",
        "[cta] widthAnchor.constraint(lessThanOrEqualToConstant: 560)   // 上限来自 adaptiveLayout.maxContentWidth，不写在 relations 里"
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
         "why": "盒子子树含文本，判为文字块：宽度来自字体与换行，不写 232 这个字面量"},
        {"id": "legal.height", "axis": "height", "of": "page", "ofIndex": 0,
         "kind": "intrinsic",
         "why": "三行文本（Privacy / Terms / Restore），行数固定但行高随动态字体变化"}
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
    "note": "贴边内边距与视觉常量（圆角 12、发丝线 1、触控下限 44）都是应当写的设计值；把内边距填进 designConstants，视觉常量由 kind=fixed 的 value 自带"
  }
}
```

六条规则，每一条都对应一次踩坑：

1. **`relations[].kind` 必填，而且决定判据。** 尺寸轴四类 —— `fixed`（必须给 `value` 与 `why`：
   设计稿的封闭值，实现时**写字面量**，且理由必须是「固定性本身是设计意图」）、
   `intrinsic`（必须给 `why`，不给宽高约束）、`bounded`（必须给 `min`/`max` 至少一个）、
   `aspect-ratio`（必须给正数 `ratio`）；关系轴四类 —— `pinned`（必须给 `edges`：贴父边/占满/等分闭合，
   **不得带比例系数**）、`proportional`（必须给 `ratio` 与 `of`）、`equal`（必须给 `with`/`to`）、
   `centered`（对齐锚点）。`fixed` 带上 `ratio`、`pinned` 带上 `multiplier` 都是自相矛盾，
   校验器直接判死。**一条关系只声明一个 kind，它描述「这个量由谁闭合」。**
   这一点容易说反，所以写清楚：**不存在**「一条关系同时挂尺寸轴与关系轴」的嵌套写法
   —— 关系里**没有**内嵌的 `relations` 子数组，写进去不会有代码读它，校验器也**不会报错**，
   只会静默丢掉。宽度既要「贴父两侧」又要「不能再宽」时，前者是 `pinned` 关系
   （`edges` + `insets`），后者是 `adaptiveLayout` 的 `maxContentWidth` ——
   **两个机制、两处字段**，不要塞进同一条关系。
2. **`fixed` 不是默认值，而且必须给 `why`。** 设计稿的 `bounds.width/height` 是参考事实，
   不自动等于生产约束。`offers.height = 68`、`cta.height = 48` 在旧契约里被判成 `fixed`；
   新契约下它们分别是 `intrinsic`（含文本、会换行）与 `bounded >= 44`（48 是视觉高度、
   44 是触控下限）。**只有视觉常量**（图标尺寸、圆角、描边、发丝线、触控下限）才天然用 `fixed`。
3. **`basis` 与关系里的 `of` 必须指向直接父视图。** 事实表 v3 的 `parentIndex` 给出了层级：
   有父视图时 `basis` 就该是 `"parent"`、`of` 写父区域名；只有 `parentIndex` 为 `null`
   （直接父即整屏画布）才用 `of: "root"`。两者对不上会被判 `basis-mismatch` —— 单页单设备上
   两种写法给出的坐标**完全一样**，父容器一变尺寸就分道扬镳。
4. **`ratios` 同时给边缘与中心两套。** 实现侧两种锚点都会用到（`leading`/`top` 与
   `centerX`/`centerY`），只给中心比例会让「按左边缘对齐」这个最常见的写法没有可用的比例。
5. **`forbiddenLiterals` 只收 `proportional` 的关系。** `fixed` 的 `value` 与 `pinned` 的
   `inset` 都是**应当原样写进代码**的设计值，列进去等于要求实现者不要按设计稿做
   （校验器的 `forbidden-targets-non-proportional` 就是拦这个）。条目还必须**同量纲配对**：
   中心比例配中心点绝对值（`legal.centerX` → 0.506361），边缘比例配左/上边缘绝对值
   （`legal.leading` → 0.211196）。曾经把左边缘的绝对值（多为 0）配给中心比例，写成
   「0pt → 0.4888」—— 开发者照做会把元素放错半个身位，**这条「指导」本身就是错的**。
   `|pt| < 1` 的条目不入清单：`0` 在任何设备上都成立，列进去只会让每个 `0` 都报一次警。
6. **`designConstantCandidates` 是可复核的提示，`designConstants` 才是豁免。** 前者由生成端
   汇总贴边内边距（省得 Agent 去源码里翻），后者是计划里手写的数字数组，只能放数字
   （标准边距、圆角）。它不是「随手写个数字就放行」：豁免值会原样写进校验结果，审阅者看得到。

`rect` 的坐标空间由「`rectInReference == rect * devicePixelRatio`」**自动判定**，判不出来就
退出 2 并给出原因，绝不猜 —— 猜错会把 scale 乘两遍（`rect` 已经是设备点）。需要按 Lanhu 画布
空间算时用 `--rect-space lanhu` 显式指定，此时会告警提示与证据冲突。

校验走 `scripts/check_layout_proportions.py`，它**是计划驱动，不是正则扫描**：每一类关系都有
它自己的判据 —— `proportional` 要求比例原语，`fixed` 要求给出 `why`（说明「固定性本身是设计
意图」）并写字面量，`pinned` 要求贴边闭合且
不带系数，`intrinsic` 要求给出理由，`bounded` 要求出现 `>=` / `<=` 原语，
`equal` 要求出现等值锚点，`aspect-ratio` 要求出现比例约束。纯正则扫描做不到这件事：它会把合法的设计常量
（圆角 12、标准边距 16）一起误报，训练出「看到告警就忽略」的习惯。

判定分两档，理由是**闸门要准，不是要响**：

- `forbidden-literal-used`（违规）—— 数值 > 48pt，不可能是手选的设计常量（没人把 393pt 当圆角）；
- `ambiguous-literal`（待判，不计入违规）—— 数值 ≤ 48pt 时与常见设计常量无法区分，列出待人工确认。

注意 `48pt` 这条线是**量级**判据，与 `kind` 判据是两回事：一条被声明为 `proportional` 的
关系在探针设备上算出 25pt，那是它落进了「待判」而不是「违规」—— 因为 25pt 既可能是抄来的
设备值，也可能是设计常量。**闭合契约下更该信 `kind`**：计划说 `pinned`，那 25pt 就是应当写的
内边距；计划说 `proportional`，那个绝对值才是错的。

注释里的数字、`100%`、`colorWithRed:22 / 255.0` 这类非布局数字一律跳过。

#### `ui-implementation-plan.json` 的 `adaptiveLayout`

`layoutProportions` 管的是**两轴**（尺寸按闭合方式声明、位置相对直接父视图），它只保证
「换设备不崩」。它回答不了第三个问题：**父视图宽到 1024pt 时，内容怎么收敛？**
这一段就是那个缺失的宽度轴。完整规范见 [adaptive-layout.md](adaptive-layout.md)。

```json
{
  "adaptiveLayout": {
    "model": "continuous-window-width",
    "windowSamples": [
      {"id": "phone-compact", "widthClass": "compact", "width": 393, "height": 852, "required": true},
      {"id": "tablet-regular-portrait", "widthClass": "medium", "width": 1024, "height": 1366, "required": true},
      {"id": "tablet-regular-landscape", "widthClass": "expanded", "width": 1366, "height": 1024, "required": true},
      {"id": "phone-regular-landscape", "widthClass": "medium", "width": 852, "height": 393, "required": false}
    ],
    "regions": [
      {"region": "hero", "widthPolicy": "full-bleed",
       "reason": "HTML 事实为四边贴 0，背景与主视觉铺满"},
      {"region": "form", "widthPolicy": "max-content-width",
       "maxContentWidth": {"value": 600, "of": "root",
                           "reason": "单列表单在 1024pt 上拉满会破坏阅读节奏"},
       "columnCount": {"compact": 1, "medium": 1, "expanded": 1}}
    ],
    "axisSwitch": [{"region": "cardRow", "compact": "horizontal", "regular": "vertical"}],
    "navigation": {"compact": "tabbar", "regular": "sidebar"},
    "forbiddenAdaptations": ["uniform-scale", "stretch-full-width", "font-scale"],
    "sizeVariants": [
      {"region": "continueCta",
       "basis": "目的 + 目的-iPad 双稿（iPad 稿 image_id=…）",
       "values": {"phone-compact": {"width": 68, "height": 22},
                  "tablet-regular-portrait": {"width": 141, "height": 28}},
       "why": "目的-iPad 稿中该按钮宽高为 141×28，照 iPad 稿取值，与目的稿无派生关系（字号跨稿差异走 typeFacts 溯源，不进本条目）"}
    ]
  }
}
```

字段约束：

| 字段 | 类型 | 约束 |
|---|---|---|
| `model` | string | 固定 `continuous-window-width`。它不是装饰：值不同说明用的是旧的两断点口径 |
| `windowSamples` | array | **非空**。每项必须有 `id` / `widthClass`（`compact` / `medium` / `expanded`）/ `width`；`required` 缺省为 `true` |
| `windowSamples[].id` | string | 采样标识，只用于证据索引。**不得**出现在生产代码里 |
| `windowSamples[].deviceClass` | string | **可选**。设备平台：`phone` / `tablet`。与 `widthClass`（窗口宽度档）**正交**——前者回答「照哪套稿的尺寸/字号」，后者回答「宽度怎么收敛」。缺省由 `id` 前缀（`phone-*` / `tablet-*`）或 `device` 机型名推断。声明 `sizeVariants` 时必须 phone 与 tablet 两档都有采样覆盖 |
| `regions[].widthPolicy` | string | `full-bleed` / `max-content-width` / `centered-column` / `grid` / `pane` / `stacked` 之一。**`stretch-full-width` 不在枚举内** —— 单列拉满是本契约要拦的头号问题 |
| `regions[].maxContentWidth` | object | `widthPolicy` 为 `max-content-width` / `centered-column` 时**必需**，含 `value`（>0 的设计常量）、`of`、`reason` |
| `regions[].columnCount` | object | `widthPolicy` 为 `grid` 时必需，含 `compact` / `medium` / `expanded` 三个正整数且**单调不减** |
| `axisSwitch` | array | 需要切主轴的区域。每项含 `region` 与至少一对档位映射 |
| `forbiddenAdaptations` | array | **非空**，至少含 `uniform-scale` / `stretch-full-width` / `font-scale` |
| `firstLevelWidthClass` | string | 缺省 `compact`。限定 [sizing-and-positioning.md §3.1.1](sizing-and-positioning.md#311-第一层子视图位置按页面比例重排设备尺寸--设计稿尺寸时的适配核心) 的「第一层位置按页面比例」**只在哪一档生效** —— 见下 |
| `sizeVariants` | array | **可选**。多设备稿照稿还原的**几何尺寸**分档白名单，见下 |

**`firstLevelWidthClass` 是必需的收口，不是可选开关。** 第一层位置比例规则在
`393×852 → 402×874` 上成立（差 2.3%），推到 1024pt 就出事：位置按比例 ×2.6、
而尺寸由各自的闭合方式决定（视觉常量不变、`bounded` 在边界内触顶即停），
于是卡片左起 33pt 变 86pt、宽度仍被封在 `max` 内、右侧空出大片空白、
卡片间距从 13pt 被拉成 285pt。所以该规则必须被显式限定在 `compact` 档；
regular / medium / expanded 档下第一层位置改由 `widthPolicy` 重排。

**`sizeVariants` 是几何尺寸分档的唯一合法出口（可选，不用就不声明）。** 视觉常量（`kind: fixed`）
的**点值不缩放**是默认，且它的作用域是**设备平台**：`audit_adaptive.py` 的 `sizeInvariance`
要求未声明分档的同一 `fixed` 元素在**同一设备**（phone / tablet）的全部采样上点值逐字相等，
**这条连 `sizeVariants` 也不能豁免**——同设备的两个宽度档之间尺寸变了，判 `size-not-invariant-within-device`。
注意 `sizeInvariance` 只审计 `fixed` 元素：`intrinsic` / `bounded` / `pinned` 的尺寸本来就
应当在采样间变化（这正是新契约的要求），它们的变化不是违规。
只有当同一设计在 Lanhu 里同时有 `xx` 与 `xx-iPad` 两份稿、跨设备（phone vs tablet）的宽高照
各自稿取值时，才走 `sizeVariants` 分档：这两份稿是**两套并列的独立参考**，iPad 组件的宽、高
照 `xx-iPad` 稿自身取值，与 `xx` 稿**没有派生关系**，因此不存在「把手机稿等比放大到 iPad」
这回事。每项约束：

| 字段 | 约束 |
|---|---|
| `region` | 元素 id / region 名，与 `layoutProportions.regions[].region` 或几何转储的 `id` 对齐 |
| `basis` | **必填**。指向哪份稿（报 design 名 + image_id） |
| `values` | **必填**。`{<windowSample.id>: {width?, height?}}`，至少两个采样档，值与稿一致 |
| `why` | **必填**。说明为什么这一档尺寸不同（照稿还原，非缩放） |

三项缺一（尤其 `basis`/`why`）的项，`sizeInvariance` 不当它进白名单 —— 尺寸跨采样变化
仍判 `size-not-invariant`。**`sizeVariants` 只对几何尺寸（宽/高）分档**——`sizeInvariance` 只审计
`fixed` 元素的几何尺寸。**字号、圆角、描边不经 `sizeVariants` / `sizeInvariance`**：它们是样式恒量（`typeFacts`），
各自照稿溯源；**iPhone 与 iPad 的字号可以相同，也可以不同**，二者没有强关联。唯一不随稿动的
是**平台硬下限**（最小点击区 ≥44pt / 48dp），那是可访问性规范，不是设计值。

**设备维度与宽度档正交。** 声明 `sizeVariants` 时，`windowSamples` 必须覆盖 `phone` 与 `tablet`
两个设备平台（由 `deviceClass` / id 前缀 / 机型名推断），否则「跨平台分档」无可指认的两个平台，
也无法判定「同设备内是否仍然不变」—— `check_adaptive_layout.py` 判
`size-variants-without-device-coverage`。

判定分两档，与 `layoutProportions` 同形：**计划怎么声明，源码就得怎么实现**。
声明 `max-content-width` 的区域源码里没有封顶原语、声明 `grid` 的区域写了固定列数、
声明里出现 `stretch-full-width`、`forbiddenAdaptations` 为空、`columnCount` 非单调 ——
都由 `scripts/check_adaptive_layout.py` 拦下。源码侧另查四类禁止模式
（`UIScreen.main.bounds` / `DisplayMetrics.widthPixels` 参与布局、方向锁定、
`UIRequiresFullScreen`、把设计常量乘屏幕系数的表达式）。

### `adaptive-targets.json`

声明了 `adaptiveLayout` 的计划，必须把「宽度档采样」落成可执行的目标清单。
它是 `runtime-device.json` 的**复数扩展**，不是替代：`runtime-device.json` 仍然是
像素基准所在的探针设备，`adaptive-targets.json` 列出全部必须取几何证据的采样。

```json
{
  "schemaVersion": 1,
  "platform": "iOS Simulator",
  "deviceFamily": "1,2",
  "samples": [
    {"id": "phone-compact", "required": true, "device": "iPhone 17",
     "windowBoundsPoints": {"width": 402, "height": 874},
     "screenshotScale": 3,
     "source": "runtime NSLog of view.bounds",
     "geometry": "actual/geometry-phone-compact.json"},
    {"id": "tablet-regular-portrait", "required": true, "device": "iPad Pro 13-inch (M4)",
     "windowBoundsPoints": {"width": 1024, "height": 1366},
     "screenshotScale": 2,
     "source": "runtime NSLog of view.bounds",
     "geometry": "actual/geometry-tablet-regular-portrait.json"}
  ]
}
```

`windowBoundsPoints` 必须来自运行时 API（`view.bounds` / `WindowMetricsCalculator`），
**禁止**由设备型号推断 —— 分屏与自由窗口下型号不变而窗口宽度变了。
`deviceFamily` 对 iOS 记录 `TARGETED_DEVICE_FAMILY`，Android 记录 `sw600dp` 资源目录是否存在。

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
  "evidence": "actual/runtime.log"
}
```

`screenBoundsPoints` 必须来自运行时 API，禁止由设备型号推断；它是布局契约里
「第一层位置按页面比例重排」的参考要素（见 `SKILL.md` 的尺寸与定位契约）。

## 已废弃字段与文件

| 旧产物 | 现状 | 取代者 |
|---|---|---|
| `visual-review.json` | 废弃 | `review.json` 的观察/验证字段 |
| `manifest.json` | 废弃 | `run.json` |
| run 级 `assets/` | 废弃 | `resource-policy.json` + 页面 `source/assets-manifest.json` |
| `page-facts.json` / `browser-meta.json` | 整体删除（渲染链撤裁） | `reference/dds-schema.json`（bounds 几何） |
| `canvas-transform.json` / `canvasTransform` | 整体删除（渲染链撤裁） | 布局契约内化的 `fit` 闭合（`SKILL.md` 尺寸与定位契约） |
| `diff/` 目录 | 整体删除（像素 diff 撤裁） | 「布局契约静态门 + 编译通过」 |

历史 run 不需要迁移：在 `run.json` 中标记 `"legacy": true` 后，校验脚本跳过上述必需项，
但**不得**据此把页面判为 `ready`。

## 禁止事项

- 禁止把多个页面或多个目标模式的产物放在同一 run 目录。
- 禁止用 `latest.json` 或文件修改时间猜「最新 run」，一律按 run ID 读取。
- 禁止删除历史 run 来「清理」失败证据；只能把页面状态改为 `archived`。
- 禁止让脚本生成或覆盖生产源码：`.ihereforUI` 只保存事实、证据、计划和索引。
