# 导出 JSON 合同与示例

## 必填字段（Contract）

- `topic`: string，原始主题。
- `topicSlug`: string，路径安全主题标识（用于文件名）。
- `date`: string，`YYYY-MM-DD`。
- `time`: string，`HHMMSS`（24 小时制，用于文件名去冲突）。
- `exportVersion`: string，固定 `v2-table`。
- `knowledgeResult`: object，必须包含：
  - `coreCard`: object|string（未进入知识分支时用说明字符串）
  - `deepDive`: array（无数据时 `[]`）
  - `revisionTrail`: array（无数据时 `[]`）
- `interactionTable`: array，按时间顺序；每项必须包含：
  - `index`: number
  - `stage`: `intent_check | clarify | core_card | deep_dive | revision | export`
  - `userSummary`: string
  - `assistantSummary`: string
  - `delta`: string（本行相对上一行新增或修订点）
  - `time`: ISO 8601 / RFC 3339（含时区）
- `interactionLogOmitted`: boolean，固定 `true`。

## 导出写入规则

- 始终写入 Markdown 文件：`exports/YYYY-MM-DD-HHMMSS-<topicSlug>-study.md`
- 若用户明确请求 JSON（`导出 json` / `export json`），额外同时写入 JSON 文件：`exports/YYYY-MM-DD-HHMMSS-<topicSlug>-study.json`

## topicSlug 规则

1. 小写化
2. 空白/分隔符转 `-`
3. 仅保留 `[a-z0-9-]`
4. 压缩连续 `-` 并去首尾 `-`
5. 最长 48 字符
6. 结果为空时兜底固定字面量 `untitled`（不是原始 `topic` 文本）

## JSON 示例

```json
{
  "topic": "Zero Trust Architecture",
  "topicSlug": "zero-trust-architecture",
  "date": "2026-07-21",
  "time": "142530",
  "exportVersion": "v2-table",
  "knowledgeResult": {
    "coreCard": {
      "domainPositioning": "...",
      "existenceReason": "...",
      "problemSolved": "...",
      "drawbacksAndBoundaries": "...",
      "classicScenarios": ["...", "..."],
      "memoryAnchor": "..."
    },
    "deepDive": [
      {
        "module": "详细案例拆解",
        "content": "..."
      }
    ],
    "revisionTrail": [
      {
        "updatedConclusion": "...",
        "reason": "...",
        "turnIndex": 4
      }
    ]
  },
  "interactionTable": [
    {
      "index": 1,
      "stage": "core_card",
      "userSummary": "用户请求解释零信任架构",
      "assistantSummary": "给出首屏 6 段核心卡",
      "delta": "建立定义、收益、边界与场景",
      "time": "2026-07-21T14:25:30+08:00"
    },
    {
      "index": 2,
      "stage": "deep_dive",
      "userSummary": "用户选择模块 2",
      "assistantSummary": "补充详细案例拆解",
      "delta": "新增落地步骤与常见误区",
      "time": "2026-07-21T14:27:05+08:00"
    }
  ],
  "interactionLogOmitted": true
}
```

## 空值约定

- 无深挖：`knowledgeResult.deepDive = []`
- 无修订：`knowledgeResult.revisionTrail = []`
- 无摘要行：`interactionTable = []`
