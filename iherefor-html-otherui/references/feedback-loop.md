# 用户判定「不合格」后的修复闭环

用户查看 App 运行画面后判定不合格（页面有问题、布局不对、颜色错等），任务进入 `修复迭代`，
不能直接在原 run 上覆盖源码或 JSON。每次迭代都必须可追溯、可恢复。

## 验证阶段的门（与修复闭环的关系）

门的定义、位置与各自判什么，见 [SKILL.md 的「强制 Agent loop」](../SKILL.md#强制-agent-loop)。
本节只讲它与**修复闭环轮次**的关系。

**门 1 的迭代不计入本文件的「轮次」。** `scripts/check_layout_proportions.py` 只读计划与
源码文本，不编译，所以「改源码 → 重跑门 1」是秒级动作。把门 1 的迭代当成一轮，会让「连续
两轮同一区域无改善」这条停止条件提前触发，把本来能在秒级收敛的布局问题误判成死循环。

**编译只应发生一次。** 若在编译才发现布局类违规，说明门 1 没跑或没跑全 —— 补跑门 1，
而不是继续在编译里试错。门 1 吸收的是**可预测的实现错误**（坐标换算系统偏移、布局口径违规、
图片未按 mapper 缩放、层级挂错父视图）；它吸收不掉**不可预测的运行时事实**
（能否编译、`contentInsetAdjustmentBehavior` 自动注入的 inset、覆盖式装饰子视图吞掉点击、
目标平台字体的实际解析结果），那些只能在编译/运行阶段观测。

## 标准线路

1. **接收反馈**：把用户原话和选中的 run 写入新的 `runs/<run-id>/review.json` 的 `feedback` 字段。
   若反馈只说「不对」，先要求用户指出页面区域，不能凭猜测大范围重写。
2. **恢复上下文**：读取项目 `project.json`、页面 `status.json`、批准基准 `reference/approved.json`、
   上一 run 的 `run.json`、`review.json`，以及该页面的 `dds-schema.json` 和 `ui-implementation-plan.json`。
   禁止仅依赖聊天上下文。
3. **分类反馈**：将反馈归类为 `geometry`（位置/尺寸）、`system-bars`（安全区/状态栏）、`asset`（资源/裁剪）、
   `typography`、`color-effect`、`layering`、`interaction`、`environment` 或 `unsupported`，
   并关联具体区域、元素、原生 view 和证据文件。
4. **先对照权威来源定位根因**：几何以 `dds-schema.json` 的 `bounds` 为准，
   样式以 `inspect_design_region` 的 `raw_style` 为准（legacy 官方 HTML/CSS 仅参考），不要凭记忆改。若反馈与权威来源冲突，先记录归因信号再改。
5. **形成修复计划**：在新 run 的 `review.json` 写入 `observations`、`hypotheses`、`changes`。
   一次迭代优先处理同一根因，避免同时修改无关区域。
6. **修改 canonical 源码**：只修改目标工程中登记在 `implementationPaths` 的生产代码和必要资源；
   不修改历史 run，不让脚本生成/覆盖生产源码。
7. **重新验证**：**先跑门 1**，再进编译：

   ```bash
   python3 scripts/check_layout_proportions.py --plan <run>/ui-implementation-plan.json \
       --source <原生源码根>
   ```

   `violations == 0` 之后才重新编译。失败时保留完整日志，状态为 `fail` 或 `not-run`，不能伪造通过。
8. **记录证据**：新 run 必须保存修改原因、实际修改文件、编译结果和下一步动作。
   `review.json` 要有 `parentRunId`，形成迭代链。
9. **重新交付判断**：写入本轮 `delivery-gate.json` 后运行 `scripts/validate_run.py --run <run-dir>`；
   只有**本次适用的全部闸门**为 `pass` 才可将页面状态设为 `ready`。`deliveryReady` 由契约推导，
   不得手写覆盖。用户再次判定不合格时，从第 1 步创建下一 run，永远不覆盖历史证据。

## `review.json` 最小结构

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
  "verification": {"build": "pass", "runtimeDevice": "runtime-device.json"},
  "nextAction": "等待用户复核"
}
```

## 停止条件

以下条件里，**机制可判的一半**已收编进 `scripts/decide_next_step.py`（读落盘产物给
`stop` / `continue`），在**考虑再开下一轮编译之前**先跑它，替代你逐条人肉判断：

```bash
python3 scripts/decide_next_step.py --run-dir <run> --with-parent
```

下面是停止条件的完整口径：

- 连续两轮同一区域无改善：暂停自动修改，展示证据并请求用户确认根因。
- 缺少 `dds-schema.json`、设备运行时尺寸或必需源码：标记 `not-run`，先补齐证据。
- 需要改变产品行为、导航、依赖或资源目录：停止修复，先走既有项目接入计划审批。
- 任一图片只验证了容器 frame、没有验证内容绘制 frame，或使用 intrinsic/natural size：
  视为 `asset/geometry` 失败，必须先修复统一图片 mapper。
