# 旧代码 × 最新 iherefor-html-otherui skill 合规差距报告

- 项目：`testUIProject`（`ios-uikit-objective-c`）
- 对照版本：`~/.workbuddy-ai/skills/iherefor-html-otherui/SKILL.md`（含 `references/`、`scripts/`）
- 核查方式：读源码 + 实跑 skill 自带校验脚本（非印象判断）
- 结论：**当前代码不能通过门 0 / 门 1，产物不能通过 `validate_run.py`；`delivery-gate.json` 里的 `deliveryReady: true` 是手写的，与脚本推导结果矛盾。**

---

## 0. 实测结果（一次跑出来的事实）

| 校验 | 命令 | 结果 |
|---|---|---|
| 门 0 计划自检（splash） | `check_layout_proportions.py --plan .../splash/plans/...json --plan-only` | **违规 9 项** |
| 门 1 层级+布局（splash） | 同上 `--source testUIProject` | **违规 9 项** |
| 宽度轴门 0（splash） | `check_adaptive_layout.py --plan ... --plan-only` | **fail，违规 22 项** |
| 宽度轴门 1（splash） | 同上 `--source testUIProject` | **fail，违规 22 项** |
| 门 0 计划自检（subscription） | `check_layout_proportions.py --plan ... --plan-only` | **违规 3 项**（`fixed-missing-why`） |
| run 产物契约（splash） | `validate_run.py --run .../20260916-161500-objc-001 --source testUIProject` | **`ok: false`**，12 项违规 |

---

## 1. 宽度轴口径整个用错了（最高优先级）

**规则**：布局是窗口宽度的连续函数；按 `compact / medium / expanded` 宽度档决策，档位之间任意宽度不得崩；窗口 ≠ 屏幕。

**现状**：全部页面用 `userInterfaceIdiom` 做「手机 / 平板」两个断点 —— 这正是检查器判 `adaptive-model-mismatch` 的旧口径（缺 `adaptiveLayout.model: "continuous-window-width"`）。

- `SplashViewController.m:78`（`isPad`）、`:115`（`applyTraits`）
- `WelcomeViewController.m:70`
- `OnboardingBaseViewController.m:130` + `:69`（`applyTraits` 全量切分档）
- 各子页（`StyleOnboardingViewController.m:42` 等）同样按 `isPad` 切列数与尺寸

**后果（可复现）**：`StyleOnboardingViewController.m:21` 内容列写死 640（iPad 3 列）；`OnboardingBaseViewController.m:251` 内容列 `width == 481`；两者都是 `constraintEqualToConstant`。Slide Over / 分屏宽 ~320pt 时，481 与 640 都大于窗口宽，且以 `centerX` 居中 → **两侧同时溢出，无任何约束可收敛**。

**要改**：把 `isPad` 换成基于窗口宽度的宽度档判定（`view.bounds` / `windowScene`，不用 `UIScreen.mainScreen`），并让每档的 `widthPolicy` 真正落到约束上。

---

## 2. 第一层子视图没有按页面比例重排（门 1 直接判错）

**规则**：`compact` 档下，第一层子视图水平位置 `x = page.width × ratio`、垂直位置 `y = page.height × ratio`，写成比例原语（`multiplier`），标 `forced: "first-level"`；不得写成探针设备绝对坐标。

**现状**：源码里 `multiplier:` 命中 **0 处**，`UILayoutGuide` 命中 **0 处**。

- `SplashViewController.m:203`：`centerYAnchor ... constant:-40.0` —— 这个 `-40` 既不在计划里，也不是任何设计常量，是为了把「组中心」挪到视觉重心而凑出来的**探针设备推导值**。
- `OnboardingBaseViewController.m:197-201`：顶部栏全部锚在 `safeAreaLayoutGuide` + 绝对常量。
- `SubscriptionPaywallViewController.m:9` 的头注释写着「位置轴：第一层子视图位置按 page 比例（multiplier）」，但**源码里一个 `multiplier` 都没有** —— 声明与实现不符。实际是 `contentColumn.top == heroView.bottom + 常量`（`:198`）+ `centerX`（`:199`）。

**计划侧连带错**：`splash/plans/ui-implementation-plan.json` 里 4 处 `"basis": "root"` / `"basis": "splash_logo_container"` 却配 `"parentIndex": null` → 门 0 判 `basis-mismatch`（有父视图时 `basis` 应为 `parent`，父为整屏画布时才是 `viewport`）。层级要么补齐、要么改口径。

---

## 3. 尺寸闭合方式违规：>48pt 设计常量当固定值用

**规则**：`fixed` 不是默认值，只用于图标、装饰、边框、明确固定高度的视觉控件；容器、文本、按钮默认优先 `intrinsic` / `bounded` / `pinned`。数值 **> 48pt** 的字面量判违规（≤48pt 只进 `ambiguousLiterals` 待确认）。

**超过 48pt 的固定字面量（判违规）**：

| 值 | 位置 | 本应是什么 |
|---|---|---|
| 232.0 进度条宽 | `OnboardingBaseViewController.m:200` | `pinned`（相对父列的等分/贴边）或 `bounded` |
| 347 / 480 CTA 宽 | `:282`、`OnboardingStyle` | `pinned`（贴内容列两侧）或 `bounded` |
| 353 / 481 内容列宽 | `:251`、`StyleOnboardingViewController.m:21` | `bounded`（有上限、随窗口收缩） |
| 640 风格网格总宽 | `StyleOnboardingViewController.m:21` | `pinned + grid`（列数随宽度档变） |
| 321 / 365 / 396 背景图高 | `SubscriptionPaywallViewController.m`、`OnboardingBaseViewController.m:144` | 装饰图可 `fixed`，但需写 `why` |
| 56 / 66 / 80 / 68 卡片与标签高 | `OnboardingDoneViewController.m:54-55`、`StyleOnboardingViewController.m:45` | 文本行应 `intrinsic` |
| 44 触控下限 | `backButtonSizeIpad` | 应写 `>= 44` 表达下限，而非写死 44 |

**另外三项连带**：

- **无 Dynamic Type**：`adjustsFontForContentSizeCategory` / `UIFontMetrics` / `preferredFontForTextStyle` 命中 **0 处**。
- **`forbiddenLiterals` 三个计划全是 `[]`**：门 0/门 1 因此永远给 warn「无法核对设备推导值」。要用 `scripts/layout_proportions.py` 生成，再人工逐条核对。
- **`sizeVariants` 结构不合规**（splash 计划 5 条全部）：每条缺 `region`（指认哪个元素分档）与 `values`（至少两个采样档的宽/高）。
- **`fixed` 缺 `why`**（subscription 计划 3 条）：`why` 不能写「设计稿就写了这个数」。

---

## 4. systemBars / 安全区：把探针设备状态栏高当常量

**现状**（`OnboardingStyle.h:75-80`）：`topBarTopInsetPhone = 8`、`topBarTopInsetIpad = 28`，注释明说是为了「照搬稿里返回按钮离画布顶 52」：手机假设状态栏 44pt → `44+8=52`；iPad 假设 24pt → `24+28=52`。

**问题**：这是把「某台设备的状态栏高度」提升成布局规则 —— 正是 skill 禁止的「直接复制另一设备的绝对像素坐标」。
- iPhone 17（`runtime-device.json` 记录窗口 402×874）安全区顶为 59pt → 实际得到 **67**，与稿 52 差 15pt；
- iPhone SE 状态栏 20pt → 会得到 28。
同一份代码在三台设备上给出三个不同偏差，却没有任何记录说明它「应该」是 52 还是别的。

**要改**：先按稿确认页面是否绘制到顶部系统区域，记录 `systemBars` 策略（`underlap` / `inset` / `mixed`），再表达为显式 inset；不要用「状态栏高度 + 补偿量」凑坐标。**onboarding 页目前没有 `ui-implementation-plan.json`，连 `systemBars` 决策都没有落盘。**

---

## 5. 产物契约缺失（`validate_run.py` 实测 `ok: false`）

### 5.1 覆盖度：10 个页面只有 3 个有计划

| 页面 | page.json | plans/*.json | reference/dds-schema.json | adopted 状态 |
|---|---|---|---|---|
| splash | ✓ | ✓ | ✓ | 有 run |
| welcome | ✓ | ✓ | ✓ | 有 run |
| subscription-no-trial | ✓ | ✓ | ✓ | 有 run |
| **onboarding** | ✗ | **✗** | **✗** | **只有 run/截图** |
| purpose / gender / age / style / brush / color / done | ✗ | ✗ | ✗ | 无目录 |

最复杂的代码（`OnboardingBaseViewController.m` 336 行 + 6 个子类）恰好完全没有计划与事实表 —— 属于「先写码、后补文档」的倒退。

### 5.2 splash run 缺的必需产物

`ui-implementation-plan.json`、`ios-environment.json`、`reference/approved.json`、`过程中页面分析表.md`、`最终页面分析表.md`。

同时 `run.json` 缺字段：`pageId`、`referenceBaseline`。

### 5.3 `delivery-gate.json` 结构整体不合规

现在写的是 `gates: {...}` + 手写 `deliveryReady: true`。契约要求的是：

- `status` 下必须有 `source` / `sourceAssets` / `implementation` / `build` / `tests` 五项（现在一个都没有）；
- `unsupported.reviewedCount` 必须是整数（现在没有）；
- **`deliveryReady` 只能由闸门脚本推导，不得手写** —— 而实测门 0/门 1/宽度轴全 fail、`validate_run` `ok: false`，所以这个 `true` 是错的；
- `adaptiveAudit: "not-applicable-simple-centered-layout-completed"` 不是合法枚举值（计划已声明 `adaptiveLayout` → 该项必跑，档位是 `pass` / `fail` / `not-run`）。

### 5.4 目录与索引

- `.ios-environment.json` 带点前缀放在**项目根**；应为 run 内的 `ios-environment.json`（只有 `subscription-no-trial` 那个 run 放对了）。
- run 里混进了 `DerivedData/`（`splash/runs/20260916-000000-objc-001/DerivedData`）→ 契约外，应跑 `scripts/cleanup_run.py` 回收。
- 缺 `.ihereforUI/project.json` 与 `status.json` 根索引 → 换手/恢复「按 run ID 定位」的链路失效。
- 计划文件位置不统一：splash 只在 `plans/`，subscription 在 `plans/` 与 `runs/` 各一份。
- 非契约目录仍在项目根：`data/design_context`、`data/lanhu_designs`、`data/messages`、`.mcp-resources/`、`subscription-no-trial/source/{assets_exported,assets_render,top}`。

---

## 6. 资源归位与命名

- **`Assets.xcassets/paywall_paint_icon.imageset` 直接挂在 xcassets 根** → 违反「一律进 `Assets.xcassets/<业务域>/<name>.imageset/`」，应移入 `paywall/`。
- 注释与实际资源不符：`OnboardingBaseViewController.m:275` 注释写 `paint_icon_close`，代码实际用 `onboarding_cta_arrow`。
- 倍率：splash 资产是按 4x 原图**下采样**得到 1x/2x/3x（`review.json` 已记），方向上合规（不是 2x 上采样凑 3x），但应在 `resource-policy.json` 留证，便于复核。
- `contentMode = ScaleToFill` 用于 guide 切图与顶部装饰图（`OnboardingBaseViewController.m:137`、`StyleOnboardingViewController.m:82`、`ColorOnboardingViewController`）→ 会拉伸变形，应按 `aspect-ratio` / `aspectFill` 处理。

---

## 7. 代码质量与一致性

- **对外声明失真**：`SubscriptionPaywallViewController.m:9` 头注释声称位置走 `multiplier` 比例，实现里没有。
- **命名失真**：`contentMaxWidthConstraint`（`:44`）名字是「封顶」，实现是 `constraintEqualToConstant:347/480`（`:196`、`:89`）—— 是硬固定宽，不是上限。
- **常量收敛不一致**：`OnboardingStyle` 收敛了大部分 token，但 gap 值仍散在源码行内：`StyleOnboardingViewController.m:45-47`（`80.0` / `68.0` / `13.0` / `20.0`）、`GenderOnboardingViewController.m:56`（`10.0`）、`ColorOnboardingViewController.m:48`（`14.0`）、`StyleOnboardingViewController.m:89`（`optionFontOfSize:20.0` 而非取 Style）。
- **选项选择态偏弱**：选中只切 `layer.borderWidth`，对外只有布尔 `hasSelection`，没有暴露选中索引 → 交互状态无法被验收或恢复。
- 点击元素均接入了命名处理函数（`didTapBack:` / `didTapSkip:` / `didTapContinue:` / `didTapClose:`）—— 这条合规。

---

## 8. 建议的修复顺序

1. **补 onboarding 页的计划与事实表**（`page.json` + `ui-implementation-plan.json` + `reference/dds-schema.json` + `过程中页面分析表.md`），并给 6 个子页各建 page 目录 —— 没有计划，后面所有门都无从跑。
2. **三个已有计划全部补齐字段**：`model: "continuous-window-width"`、`windowSamples[].widthClass`（覆盖 compact/medium/expanded）、`forbiddenAdaptations` 补 `uniform-scale` / `stretch-full-width` / `font-scale`、`sizeVariants[].region/values`、`maxContentWidth.of/reason`、`typeFacts[].region`、`pinned.edges`、`fixed.value` + `why`、`basis` 与 `parentIndex` 对齐、用 `layout_proportions.py` 生成 `forbiddenLiterals`。
3. **改源码**：`isPad` → 窗口宽度档；第一层子视图改比例原语；把 232/347/480/353/481/640 从 `fixed` 改成 `pinned`/`bounded`；加封顶原语与 Dynamic Type；去掉 splash 的 `-40` 魔数；修 paywall 的注释与命名。
4. **修 systemBars**：按稿确认策略并落盘，去掉「状态栏高 + 补偿量」凑坐标的写法。
5. **收拾产物**：`ios-environment.json` 归位到 run、跑 `cleanup_run.py` 清 DerivedData、`delivery-gate.json` 改为脚本推导结构、建根索引、清理 `data/` 与 `.mcp-resources` 等契约外目录。
6. **资源**：`paywall_paint_icon.imageset` 移入 `paywall/`；`ScaleToFill` 改 `aspectFill`。
7. **重跑**：门 0 → 门 1 → 宽度轴门 0/1 → 编译 → `audit_adaptive.py` → `validate_run.py`，全部零违规后才重新写 `deliveryReady`。
