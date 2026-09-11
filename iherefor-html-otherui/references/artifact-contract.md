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
    ├── page-facts.json          # 页面事实表（bounding box / computed style / 资源）
    ├── browser-meta.json        # 浏览器版本、viewport、字体、注入记录、加载错误
    └── approved.json            # 批准记录：sha256、批准时间、批准人
```

事实表与浏览器元数据属于**基准**，因此放在页面级而不是 run 级：重新渲染不会自动替换
已批准基准，只有显式批准才写入 `approved.json`。

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
| `diff/` | always | 整页与区域差异摘要（含阈值与输入尺寸） |

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

`deliveryReady` 为 `true` 的**充要条件**（校验脚本按此判定，不接受手写覆盖）：

1. 上述 7 项全部为 `pass`；
2. `unsupported.count == unsupported.reviewedCount`（不存在未审查的降级项）。

任一条件不满足时 `deliveryReady` 必须为 `false`，并在 `blockingReasons` 中列出原因。

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
