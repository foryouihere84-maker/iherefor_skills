# 既有项目接入与二次开发计划

当目标目录已有应用工程、模块或页面时，必须先完成接入审计，再生成或修改生产代码。新增页面和二次开发都适用；不能把页面当成独立 demo 直接塞进项目。

## 接入审计

在当前项目 `.ihereforUI/integration/` 保存只读审计结果，至少检查：

- 工程入口：`.xcworkspace/.xcodeproj`、Gradle settings、workspace/module
- target、scheme、构建 configuration、部署版本和签名/包名
- App 启动入口、导航方式（UIKit/SwiftUI/Coordinator/Navigation/Router）
- 现有页面目录、模块边界、公共 UI 组件、主题/Design System
- 资源模块、字体、颜色、尺寸、国际化、本地化和图片加载方式
- 依赖管理（CocoaPods/SPM/Gradle/version catalog）及新增依赖是否必要
- 状态管理、网络/持久化边界、埋点和权限要求
- 测试目标、UI test 启动路径、截图基准和 CI 命令

## 计划文件

审计完成后必须写入：

```text
.ihereforUI/integration/project-audit.json
.ihereforUI/integration/integration-plan.json
.ihereforUI/pages/<page-id>/plans/integration-plan.json
```

计划至少包含：

```json
{
  "projectEntry": {"type":"workspace","path":"...","scheme":"App"},
  "integrationPoint": {"module":"FeatureSubscription","route":"SubscriptionRoute","parent":"MainCoordinator"},
  "filesToAdd": [],
  "filesToModify": [],
  "resources": {"reuse": [], "add": []},
  "dependencies": {"add": [], "reuse": []},
  "navigation": {"entryAction":"didTapOpenSubscription","backAction":"didTapCloseSubscription"},
  "stateAndEvents": [],
  "tests": {"unit": [], "ui": [], "visual": []},
  "rollback": {"safeToRevert": true, "steps": []},
  "approval": {"status":"planned"}
}
```

`filesToAdd` 的文件名必须由 Agent 根据页面语义、现有目录和模块命名推导，并在计划中先列出；禁止先创建固定命名文件再补计划。若会修改启动入口、Podfile、Package.swift、Gradle 配置或公共组件，必须明确理由、影响范围和回滚步骤。

## 执行闸门

在 `integration-plan.json` 获得用户确认或项目约定批准前，只允许审计、读取和生成计划，不得写入生产代码或修改依赖。计划批准后，按 `filesToAdd/filesToModify` 执行，并在 run 中记录实际偏差；偏差必须回写计划和 review。
