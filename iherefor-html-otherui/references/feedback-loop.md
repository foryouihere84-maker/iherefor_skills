# 用户判定“不合格”后的修复闭环

用户在 diff 查看器中判定不合格后，任务进入 `修复迭代`，不能直接在原 run 上覆盖截图、JSON 或代码。每次迭代都必须可追溯、可恢复。

## 标准线路

1. **接收反馈**：把用户原话和选中的 run 写入新的 `runs/<run-id>/review.json` 的 `feedback` 字段。若反馈只说“不一致”，先要求用户指出页面区域或由 Agent 根据 diff 热点定位，不能凭猜测大范围重写。
2. **恢复上下文**：读取项目 `project.json`、页面 `status.json`、批准基准 `reference/approved.json`、上一 run 的 `run.json`、`review.json`、`diff/`，以及该页面的 `page-facts.json` 和 `ui-implementation-plan.json`。禁止仅依赖聊天上下文。
3. **分类差异**：将反馈归类为 `geometry`（位置/尺寸/缩放）、`system-bars`（安全区/状态栏）、`asset`（资源/裁剪）、`typography`、`color-effect`、`layering`、`interaction`、`environment` 或 `unsupported`，并关联具体区域、元素 selector、原生 view 和证据文件。
4. **形成修复计划**：在新 run 的 `review.json` 写入 `observations`、`hypotheses`、`changes` 和验收阈值。一次迭代优先处理同一根因，避免同时修改无关区域；若需要改变页面接入方式或资源策略，先更新 integration/page plan。
5. **修改 canonical 源码**：只修改目标工程中登记在 `implementationPaths` 的生产代码和必要资源；不修改历史 run，不把截图作为 UI 覆盖层，不让脚本生成/覆盖生产源码。所有按钮点击函数保持可用。
6. **重新验证**：重新 build、test、运行目标设备（通过运行时 API 读取真实 bounds）、截图，并生成新的 diff。失败时保留完整日志，状态为 `fail` 或 `not-run`，不能伪造通过。
7. **记录证据**：新 run 必须保存 before/after、diff summary（整页和受影响区域）、runtime-device、修改原因、实际修改文件和下一步动作。`review.json` 要有 `parentRunId`，形成迭代链。
8. **回归检查**：修复局部区域后，仍需检查整页、顶部/底部系统区域、图片映射和至少一个文本/容器区域，防止局部修复破坏其他区域。
9. **重新交付判断**：写入本轮 `delivery-gate.json` 后运行 `scripts/validate_run.py --run <run-dir>`；只有 7 项闸门全部为 `pass` 且 `unsupported.count == reviewedCount` 才可将页面状态设为 `ready`，否则保持 `needs-review`。`deliveryReady` 由契约推导，不得手写覆盖。用户再次判定不合格时，从第 1 步创建下一 run，永远不覆盖历史证据。

## `review.json` 最小结构

```json
{
  "schemaVersion": 1,
  "runId": "20260907-120000-objc-006",
  "parentRunId": "20260907-104000-objc-005",
  "decision": "rejected",
  "feedback": [{"text": "标题和卡片整体偏下", "source": "user", "at": "2026-09-07T12:00:00+08:00"}],
  "observations": [{"region": "title", "category": "geometry", "evidence": ["diff/full-page.json", "reference/page-facts.json"]}],
  "hypotheses": ["safe-area 自动 inset 与 Lanhu underlap 重复计算"],
  "changes": [{"file": "testUIProject/SubscriptionPlanSelectionViewController.m", "reason": "关闭自动 content inset"}],
  "verification": {"build": "pass", "tests": "pass", "visualDiff": "pass-with-review", "runtimeDevice": "runtime-device.json"},
  "nextAction": "等待用户复核"
}
```

## 停止条件

- 连续两轮同一区域无改善：暂停自动修改，展示证据并请求用户确认根因。
- 缺少 reference、设备运行时尺寸或可复现截图：标记 `not-run`，先补齐证据。
- 任一图片只验证了容器 frame、没有验证内容绘制 frame，或使用 intrinsic/natural size：视为 `asset/geometry` 失败，必须先修复统一图片 mapper。
- 发现图片右侧/底部留白时，修复目标必须是图片绘制 bounds 和 scale policy；不得把它当作普通间距问题处理。
- 需要改变产品行为、导航、依赖或资源目录：停止视觉修复，先走既有项目接入计划审批。
