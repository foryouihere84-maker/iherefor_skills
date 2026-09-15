# 用户判定“不合格”后的修复闭环

用户在 diff 查看器（skill 根目录的 [index.html](../index.html)，浏览器直接打开即可）中判定不合格后，任务进入 `修复迭代`，不能直接在原 run 上覆盖截图、JSON 或代码。每次迭代都必须可追溯、可恢复。

## 验证阶段的三段门（与修复闭环的关系）

门的定义、位置与各自判什么，见 [SKILL.md 的「强制 Agent loop」](../SKILL.md#强制-agent-loop)。
本节只讲它与**修复闭环轮次**的关系。

**门 1 的迭代不计入本文件的「轮次」。** `scripts/check_layout_proportions.py` 只读计划与
源码文本，不编译、不起浏览器，所以「改源码 → 重跑门 1」是秒级动作，和「改源码 → 编译 →
装机 → 截图 → 比对」完全不是一个量级。把门 1 的迭代当成一轮，会让下面「连续两轮同一区域
无改善」这条停止条件提前触发，把本来能在秒级收敛的布局问题误判成死循环。

**门 2 只应发生一次。** 若在门 2 才发现布局类违规，说明门 1 没跑或没跑全 —— 补跑门 1，
而不是继续在编译截图里试错。门 1 能吸收的是**可预测的实现错误**（坐标换算系统偏移、
布局口径违规、图片未按 mapper 缩放、层级挂错父视图）；它吸收不掉**不可预测的运行时事实**
（能否编译、`contentInsetAdjustmentBehavior` 自动注入的 inset、覆盖式装饰子视图吞掉点击、
目标平台字体的实际解析结果），那些仍然只能在门 2 观测。

### 这条链路的成本结构（实测，决定该往哪里优化）

把一次真实 run（140 条关系 / 47 个源码文件）的产物时间戳切开：

| 项 | 实测 |
|---|---|
| 门 0 | 0.12 s |
| 门 1 | 0.14 s（比门 2 快约 **70 倍**） |
| 门 2 一轮 = 构建 2.3 + 装机 5.5 + 启动 1.6 + 截图 0.5 | 9.9 s |
| **验证阶段墙钟**（计划落盘 → review 完成） | **29 分 26 秒** |
| 该窗口内可测的机器操作（3 轮构建 + 装机 + 启动 + 截图） | **约 30 秒** |

⇒ **机器只占约 2%，其余约 98% 是「看截图 → 形成假设 → 改码 → 重跑」的 Agent 循环。**

所以前移门 1 的收益**不是省下那 10 秒构建**，而是**避免让 Agent 经历一次完整的截图诊断
循环**：读一张整页截图、形成假设、改码、重跑，那是分钟级，而且可能建立在错误假设上。
门 1 用 0.14 s 直接给出 `文件:行号` 与规则名，把「看图猜」换成「读一条定位精确的告警」。

**优化方向由此确定：盯「Agent 需要经历几轮推断」，不要盯「构建快几秒」。** 任何新增的检查，
先问它能否把某一类问题从「需要截图诊断」降级为「静态告警并给出位置」。同理，本文件下面
那些停止条件的作用不只是「防止瞎改」，更是**及时切断一轮注定无效的 Agent 推断**。

## 标准线路

1. **接收反馈**：把用户原话和选中的 run 写入新的 `runs/<run-id>/review.json` 的 `feedback` 字段。若反馈只说“不一致”，先要求用户指出页面区域或由 Agent 根据 diff 热点定位，不能凭猜测大范围重写。
2. **恢复上下文**：读取项目 `project.json`、页面 `status.json`、批准基准 `reference/approved.json`、上一 run 的 `run.json`、`review.json`、`diff/`，以及该页面的 `page-facts.json` 和 `ui-implementation-plan.json`。禁止仅依赖聊天上下文。
3. **分类差异**：将反馈归类为 `geometry`（位置/尺寸/缩放）、`system-bars`（安全区/状态栏）、`asset`（资源/裁剪）、`typography`、`color-effect`、`layering`、`interaction`、`environment` 或 `unsupported`，并关联具体区域、元素 selector、原生 view 和证据文件。

   在动手改代码之前，先用证据把 `geometry` 与 `typography`/`color-effect` 分开：

   ```bash
   python3 scripts/compare_reference.py --reference <page>/reference/reference.png \
       --actual <run>/actual/app.png --page-facts <page>/reference/page-facts.json \
       --plan <run>/ui-implementation-plan.json --output <run>/diff/comparison.json
   python3 scripts/audit_alignment.py --reference <page>/reference/reference.png \
       --actual <run>/actual/app.png --page-facts <page>/reference/page-facts.json \
       --runtime-device <run>/runtime-device.json --output <run>/diff/alignment.json
   ```

   比较器的 `structuralRatio` 高 ⇒ 几何问题（边在两张图里对不上）；`fillRatio` 高 ⇒
   颜色问题（平坦区颜色不同）；只有 `textureRatio` 高 ⇒ 栅格化噪点，**不要**改代码去
   「修」它。`regions` 会指出差在哪一带，以及偏差是否随 y 递增 —— 单调递增的纵向梯度
   说明是整体映射问题，不是某个控件写错，此时改单个控件只会白费一轮。

   但 `regions` 是网格切块，说不出「差在哪个控件」。定位靠 `attribution`：它按**最小包含
   元素优先**把差异像素互斥归属到具名区域，并给出 `declaredUnsupported` 与 `residual`。
   **`residual`（扣除已声明差异后的剩余值）才是 `review.json` 该引用的数字** —— 整页比值里
   混着已声明为 `unsupported` 的差异（系统状态栏、无法等价映射的 CSS 特性），不扣除就说不清
   「还剩多少是真缺陷」。`attribution.status` 为 `insufficient-evidence` / `not-run` 时，
   先把 `--page-facts`（需 `rectInReference`）补上再谈归因，不要拿网格结论当控件级结论。

4. **先判「基准可不可信」，再决定改哪一侧**。`diff/alignment.json` 的两个比较需要**相反的动作**，搞反了会照着错误的基准把 App 改坏：

   | 比较 | 不符的含义 | 该做什么 |
   |---|---|---|
   | `domVsReference` | 基准图本身不可信（渲染 viewport/scale 与采集事实表时不一致） | 先重修基准并重新批准，**不要**动 App 代码 |
   | `referenceVsActual` | 基准可信，App 实现不符 | 按区域改 App 代码 |

   只有当 `domVsReference` 为 `aligned` 时，`referenceVsActual` 的结论才是关于 App 的。
   若审计退出码为 2（证据不足），先补齐 `page-facts.json` / `runtime-device.json`，
   不得凭整页比例继续。

5. **形成修复计划**：在新 run 的 `review.json` 写入 `observations`、`hypotheses`、`changes` 和验收阈值。一次迭代优先处理同一根因，避免同时修改无关区域；若需要改变页面接入方式或资源策略，先更新 integration/page plan。
6. **修改 canonical 源码**：只修改目标工程中登记在 `implementationPaths` 的生产代码和必要资源；不修改历史 run，不把截图作为 UI 覆盖层，不让脚本生成/覆盖生产源码。所有按钮点击函数保持可用。
7. **重新验证**：**先跑门 1**，再进编译：

   ```bash
   python3 scripts/check_layout_proportions.py --plan <run>/ui-implementation-plan.json \
       --source <原生源码根>
   ```

   `violations == 0` 之后才重新 build、test、运行目标设备（通过运行时 API 读取真实 bounds）、
   截图，并生成新的 diff 与新的对齐审计。门 1 是秒级的、不编译，所以这一档可以反复重跑，
   **不计入轮次**；门 2（编译/装机/截图）只应发生一次。失败时保留完整日志，状态为 `fail`
   或 `not-run`，不能伪造通过。
8. **记录证据**：新 run 必须保存 before/after、diff summary（含 `structuralRatio` 与 `regions`）、alignment、runtime-device、修改原因、实际修改文件和下一步动作。`review.json` 要有 `parentRunId`，形成迭代链。
9. **回归检查**：修复局部区域后，仍需检查整页、顶部/底部系统区域、图片映射和至少一个文本/容器区域，防止局部修复破坏其他区域。
10. **重新交付判断**：写入本轮 `delivery-gate.json` 后运行 `scripts/validate_run.py --run <run-dir>`；只有**本次适用的全部闸门**为 `pass`（基础 7 项，计划声明了 `adaptiveLayout` 时再加 `adaptiveAudit`）且 `unsupported.count == reviewedCount` 才可将页面状态设为 `ready`，否则保持 `needs-review`。`deliveryReady` 由契约推导，不得手写覆盖。`visualDiff` 的取值约束（含 `pass-with-review` 升格为 `pass` 的唯一例外）见 [SKILL.md 的「交付闸门」](../SKILL.md#7-交付闸门)，本文件不另立口径。用户再次判定不合格时，从第 1 步创建下一 run，永远不覆盖历史证据。

## `review.json` 最小结构

```json
{
  "schemaVersion": 1,
  "runId": "20260907-120000-objc-006",
  "parentRunId": "20260907-104000-objc-005",
  "decision": "rejected",
  "feedback": [{"text": "标题和卡片整体偏下", "source": "user", "at": "2026-09-07T12:00:00+08:00"}],
  "observations": [{"region": "title", "category": "geometry", "evidence": ["diff/comparison.json", "diff/alignment.json", "reference/page-facts.json"]}],
  "hypotheses": ["safe-area 自动 inset 与 Lanhu underlap 重复计算"],
  "changes": [{"file": "testUIProject/SubscriptionPlanSelectionViewController.m", "reason": "关闭自动 content inset"}],
  "verification": {"build": "pass", "tests": "pass", "visualDiff": "pass-with-review", "runtimeDevice": "runtime-device.json", "alignment": "diff/alignment.json"},
  "nextAction": "等待用户复核"
}
```

## 停止条件

- 连续两轮同一区域无改善：暂停自动修改，展示证据并请求用户确认根因。
- 缺少 reference、设备运行时尺寸或可复现截图：标记 `not-run`，先补齐证据。
- `diff/alignment.json` 未跑或退出码为 2：这是**证据不足**，不得直接进入修复 —— 先补 `page-facts.json` / `runtime-device.json` 再判。整页 `changedRatio` 在容差内不能替代元素级结论。
- `domVsReference` 判 `needs-review`：**先修基准**，禁止在此状态下按 `referenceVsActual` 的差调 App 代码。基准错了，越改越偏。**但修之前必须做一次交叉复核** —— `alignment.json` 会带 `crossCheckRequired: true` 与 `crossCheck`，照它的 `how` 换硬边高对比特征做亮度扫描 + 线性拟合，看偏差是**常量偏置**（= 探测器偏置）还是**随坐标增长**（才是真实比例误差）。本审计用墨迹质心，对框内近乎空白的图片/容器元素会伪造比例信号（见 `coverage.excludedLowCoverage`）；直接照 `nextAction` 重渲染基准可能白干一轮，还会改坏本来正确的基准。契约禁止手写覆盖工具结论：保留 `alignment.json` 原样，另写独立证据文件并在 `review.json` 里说明异议。
- `alignment.json` 的 `coverage.excludedLowCoverage.count` 很大：说明相当一部分图片/容器探针框内近乎空白、已被排除在位移与比例拟合之外。此时 `offsetFit` 的杠杆比看上去小，比例结论要更保守 —— 不要仅凭它改 `canvasTransform`。
- 只有 `textureRatio` 高（`structuralRatio` 与 `fillRatio` 都在容差内）：这是栅格化噪点，不是缺陷，不要为它改代码。
- `structuralRatio` 高于上限但**在计划声明的 `gateReachability.expectedStructuralFloor` 之内**、且 `fillRatio` 在容差内：这是文字密集页的**物理下界**，**不可能降到 0**。此时停止修改、记 `pass-with-review` + 量化归因，不要再为它开一轮编译截图 —— 反复逼近 0 只会白烧轮次，而且会诱使你去缩放字号凑闸门（契约明令禁止）。放行条件与 `visualDiff` 的升格口径**以 [SKILL.md 的「交付闸门」](../SKILL.md#7-交付闸门) 为唯一出处**：计划必须真的声明 `gateReachability`（含 `unavoidable[].cause` 与 `measuredShare`），否则校验器会判「以声明下界放行，但计划没有 gateReachability」；反之，声明了下界却把下界内的值判 `fail`，同样是错。
- 偏差随 y 单调递增：这是坐标系/比例不一致，必须回到 `canvasTransform.policy` 与 `coordinateMapper` 层面核对（`scripts/canvas_map.py`），不要逐控件微调位置。
- 任一图片只验证了容器 frame、没有验证内容绘制 frame，或使用 intrinsic/natural size：视为 `asset/geometry` 失败，必须先修复统一图片 mapper。
- 图片出现一侧留白但 `alphaBounds` 显示资源本身有透明边界：先按 `alphaBounds` 与 HTML 裁剪规则核对，不要直接改 frame 去凑视觉。
- diff 的输入不是「页面级已批准基准 + 本次 run 的原始截图」，或出现降采样/裁剪派生图（如 `*-reference-size.png`）：证据无效，判 `fail` 并重跑同源渲染，禁止用派生图凑尺寸。
- 发现图片右侧/底部留白时，修复目标必须是图片绘制 bounds 和 scale policy；不得把它当作普通间距问题处理。
- 需要改变产品行为、导航、依赖或资源目录：停止视觉修复，先走既有项目接入计划审批。
