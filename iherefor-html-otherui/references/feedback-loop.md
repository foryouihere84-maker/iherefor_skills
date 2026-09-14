# 用户判定“不合格”后的修复闭环

用户在 diff 查看器（skill 根目录的 [index.html](../index.html)，浏览器直接打开即可）中判定不合格后，任务进入 `修复迭代`，不能直接在原 run 上覆盖截图、JSON 或代码。每次迭代都必须可追溯、可恢复。

## 标准线路

1. **接收反馈**：把用户原话和选中的 run 写入新的 `runs/<run-id>/review.json` 的 `feedback` 字段。若反馈只说“不一致”，先要求用户指出页面区域或由 Agent 根据 diff 热点定位，不能凭猜测大范围重写。
2. **恢复上下文**：读取项目 `project.json`、页面 `status.json`、批准基准 `reference/approved.json`、上一 run 的 `run.json`、`review.json`、`diff/`，以及该页面的 `page-facts.json` 和 `ui-implementation-plan.json`。禁止仅依赖聊天上下文。
3. **分类差异**：将反馈归类为 `geometry`（位置/尺寸/缩放）、`system-bars`（安全区/状态栏）、`asset`（资源/裁剪）、`typography`、`color-effect`、`layering`、`interaction`、`environment` 或 `unsupported`，并关联具体区域、元素 selector、原生 view 和证据文件。

   在动手改代码之前，先用证据把 `geometry` 与 `typography`/`color-effect` 分开：

   ```bash
   python3 scripts/compare_reference.py --reference <page>/reference/reference.png \
       --actual <run>/actual/app.png --output <run>/diff/comparison.json
   python3 scripts/audit_alignment.py --reference <page>/reference/reference.png \
       --actual <run>/actual/app.png --page-facts <page>/reference/page-facts.json \
       --runtime-device <run>/runtime-device.json --output <run>/diff/alignment.json
   ```

   比较器的 `structuralRatio` 高 ⇒ 几何问题（边在两张图里对不上）；`fillRatio` 高 ⇒
   颜色问题（平坦区颜色不同）；只有 `textureRatio` 高 ⇒ 栅格化噪点，**不要**改代码去
   「修」它。`regions` 会指出差在哪一带，以及偏差是否随 y 递增 —— 单调递增的纵向梯度
   说明是整体映射问题，不是某个控件写错，此时改单个控件只会白费一轮。

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
7. **重新验证**：重新 build、test、运行目标设备（通过运行时 API 读取真实 bounds）、截图，并生成新的 diff 与新的对齐审计。失败时保留完整日志，状态为 `fail` 或 `not-run`，不能伪造通过。
8. **记录证据**：新 run 必须保存 before/after、diff summary（含 `structuralRatio` 与 `regions`）、alignment、runtime-device、修改原因、实际修改文件和下一步动作。`review.json` 要有 `parentRunId`，形成迭代链。
9. **回归检查**：修复局部区域后，仍需检查整页、顶部/底部系统区域、图片映射和至少一个文本/容器区域，防止局部修复破坏其他区域。
10. **重新交付判断**：写入本轮 `delivery-gate.json` 后运行 `scripts/validate_run.py --run <run-dir>`；只有 7 项闸门全部为 `pass` 且 `unsupported.count == reviewedCount` 才可将页面状态设为 `ready`，否则保持 `needs-review`。`deliveryReady` 由契约推导，不得手写覆盖。注意 `visualDiff` 不能在 `diff/alignment.json` 判 `needs-review` 时为 `pass` —— 校验脚本会拦住这种自相矛盾。用户再次判定不合格时，从第 1 步创建下一 run，永远不覆盖历史证据。

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
- `domVsReference` 判 `needs-review`：**先修基准**，禁止在此状态下按 `referenceVsActual` 的差调 App 代码。基准错了，越改越偏。
- 只有 `textureRatio` 高（`structuralRatio` 与 `fillRatio` 都在容差内）：这是栅格化噪点，不是缺陷，不要为它改代码。
- 偏差随 y 单调递增：这是坐标系/比例不一致，必须回到 `canvasTransform.policy` 与 `coordinateMapper` 层面核对（`scripts/canvas_map.py`），不要逐控件微调位置。
- 任一图片只验证了容器 frame、没有验证内容绘制 frame，或使用 intrinsic/natural size：视为 `asset/geometry` 失败，必须先修复统一图片 mapper。
- 图片出现一侧留白但 `alphaBounds` 显示资源本身有透明边界：先按 `alphaBounds` 与 HTML 裁剪规则核对，不要直接改 frame 去凑视觉。
- diff 的输入不是「页面级已批准基准 + 本次 run 的原始截图」，或出现降采样/裁剪派生图（如 `*-reference-size.png`）：证据无效，判 `fail` 并重跑同源渲染，禁止用派生图凑尺寸。
- 发现图片右侧/底部留白时，修复目标必须是图片绘制 bounds 和 scale policy；不得把它当作普通间距问题处理。
- 需要改变产品行为、导航、依赖或资源目录：停止视觉修复，先走既有项目接入计划审批。
