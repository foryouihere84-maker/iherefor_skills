# `.ihereforUI` 多页面项目管理

`.ihereforUI` 是 iherefor-html-otherui 的唯一中间产物根目录。不要把多个页面的 facts、截图、diff 或计划混放在工程根目录，也不要用 `latest.json` 覆盖历史运行。

**字段级契约以 [artifact-contract.md](artifact-contract.md) 为准**；本文件只描述目录生命周期、索引与查找规则。机器校验：`python3 scripts/validate_run.py --run <run-dir>`。

## 目录契约

```text
.ihereforUI/
├── project.json                 # 项目索引、输入根目录、目标模式、当前页面
├── integration/
│   ├── project-audit.json       # 既有项目只读审计
│   └── integration-plan.json    # 项目级接入计划
├── pages/
│   └── <page-id>/
│       ├── page.json             # 页面元数据、HTML 入口、implementationPaths、状态
│       ├── source/               # HTML/CSS/JS/资源的只读快照
│       │   ├── manifest.json      # 文件清单、sha256、image_id、版本、来源 URL
│       │   └── assets-manifest.json
│       ├── reference/            # 当前「已批准」的冻结基准
│       │   ├── reference.png
│       │   ├── page-facts.json
│       │   ├── browser-meta.json
│       │   └── approved.json
│       ├── plans/                # 页面实现计划、接入计划、unsupported 清单
│       │   ├── ui-implementation-plan.json
│       │   └── integration-plan.json
│       ├── runs/
│       │   └── <run-id>/         # 不可变的一次执行
│       │       ├── run.json
│       │       ├── review.json
│       │       ├── delivery-gate.json
│       │       ├── ui-implementation-plan.json
│       │       ├── resource-policy.json
│       │       ├── runtime-device.json
│       │       ├── ios-environment.json   # 仅 iOS 目标模式
│       │       ├── actual/       # 各目标模式截图和日志
│       │       └── diff/         # 整页/区域 diff 与摘要
│       └── status.json           # 页面级交付状态
├── reports/
│   ├── project-status.json       # 跨页面汇总
│   └── delivery-gate.json        # 项目级交付闸门
└── index.json                    # 可选机器索引；由管理脚本更新
```

`<page-id>` 使用稳定的 kebab-case 标识，不使用标题、时间戳或随机 UUID 作为唯一页面名。页面重命名必须在 `page.json` 中保留 `aliases`，不能移动后丢失历史。

## 生命周期

1. **注册页面**：为每个 Lanhu HTML 入口创建 `pages/<page-id>/page.json`，记录 source path、reference viewport、页面顺序和目标模式。
2. **冻结基准**：在该页面的 `reference/` 生成 screenshot、`page-facts.json`、`browser-meta.json`。只有明确批准后，才更新 `reference/approved.json`；重新渲染不能自动替换批准基准。
3. **建立计划**：把页面按 hero、标题/说明、每张卡片、CTA、页脚等区域写入 `plans/ui-implementation-plan.json`，每个区域引用 source selector 和事实来源。
4. **创建运行**：每次生成或修复创建新的 `<run-id>`，例如 `20260906-133147-objc-001`。run 目录只追加产物，不覆盖旧 run；`run.json` 记录 git revision、target mode、设备、坐标变换和输入基准哈希。
5. **页面审查**：在 `review.json` 记录每轮 before/after、diff 数值、受影响区域、事实来源和下一步动作。上下文压缩或换手后先读 `project.json`、当前页 `status.json` 和最新 run 的 `run.json`/`review.json`。
6. **页面交付**：页面只有在自身 build/test/visual diff/unsupported 闸门通过后才标记 `ready`。单页失败不能污染其他页面状态。
7. **项目汇总**：管理脚本读取所有 `status.json` 生成 `reports/project-status.json` 和 `reports/delivery-gate.json`。项目只有所有选定页面和目标模式均 ready 才能 `deliveryReady=true`。

## 页面与代码的边界

- `.ihereforUI` 保存事实、证据、计划和索引；生产 Swift/Objective-C/Kotlin/Java/XML 仍维护在目标工程的 canonical source 中。
- `page.json` 的 `implementationPaths` 指向生产代码，禁止复制出第二份可编辑源码导致漂移。
- 资源必须在页面级 `source/assets-manifest.json` 建立 URL→原生资源的映射；共享资源可在项目级登记，但页面仍记录引用。
- Lanhu MCP 下载的 HTML/CSS/JS/资源必须进入页面级 `source/`，并由 `source/manifest.json` 记录 image_id、版本、来源 URL、文件清单和哈希。
- 同一页面的不同目标模式必须使用不同 run ID；不能把 iOS 截图或 diff 当作 Android 的通过证据。

## 推荐最小 schema

项目索引：

```json
{
  "schemaVersion": 1,
  "projectId": "subscription-ui",
  "inputRoot": "/path/to/lanhu/design-code",
  "targetModes": ["ios-uikit-objective-c"],
  "currentPage": "plan-selection",
  "pages": [{"id": "plan-selection", "path": "pages/plan-selection", "status": "needs-review"}]
}
```

页面索引：

```json
{
  "schemaVersion": 1,
  "id": "plan-selection",
  "source": {"entry": ".../index.html", "styles": [], "scripts": [], "assets": []},
  "referenceViewport": {"width": 393, "height": 852, "devicePixelRatio": 2},
  "implementationPaths": {"ios-uikit-objective-c": ["testUIProject/THOExampleViewController.m"]},
  "runs": [{"id": "20260906-133147-objc-001", "status": "needs-review"}],
  "status": "needs-review"
}
```

## 查找规则

- 看项目：读 `.ihereforUI/project.json`，再读 `.ihereforUI/reports/project-status.json`。
- 校验一次 run：`python3 scripts/validate_run.py --run <run-dir>`；不合规的 run 不得参与交付判定，`deliveryReady` 不得手写覆盖。
- 看单页：只读该页 `page.json`、`status.json`、`reference/approved.json` 和最新 run 的 `run.json`、`review.json`。
- 看历史：按 run ID 进入 `runs/<run-id>/`，禁止依赖文件修改时间猜“最新”。
- 删除或重做页面：只能把页面状态改为 `archived`；不要删除 runs，除非用户明确要求清理历史。
