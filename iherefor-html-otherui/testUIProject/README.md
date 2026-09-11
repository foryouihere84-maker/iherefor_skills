# testUIProject

本目录**不是交付物**，而是 iherefor-html-otherui 的回归样例工程：一个最小的 Objective-C
UIKit 工程 + 一份 Lanhu 页面落地结果，用来验证 skill 的强制流程确实可执行。

## 内容

| 路径 | 说明 |
|---|---|
| `testUIProject.xcodeproj` | Xcode 工程入口，供 `scripts/discover_xcode_environment.py` 探测 |
| `testUIProject/SubscriptionPlanSelectionViewController.m` 等 | 由 skill 生成的生产源码样例（分层的 VC / View / Style / Resources） |
| `testUIProject/plan_selection_*.png` | 语义命名的资源样例，来自 Lanhu 的 `img_*` |
| `testUIProjectTests` / `testUIProjectUITests` | 单元与 UI 测试冒烟样例 |
| `.ihereforUI/` | 运行产物（事实、截图、diff、run 记录），**已被 git 忽略** |

## 不变量

1. `.ihereforUI/` 是中间产物，不参与版本控制；需要长期留存的证据必须复制到
   `scripts/tests/fixtures/` 或 `evals/fixtures/`。
2. 生产源码必须保留在 `testUIProject/` 内，`.ihereforUI/` 只放事实与证据，不得出现第二份
   可编辑源码。
3. 资源文件名使用 `<screen>_<region>_<role>` 语义命名，禁止改回 `img_0.png` 之类的来源编号。

## 已知的历史产物

`.ihereforUI/pages/plan-selection/runs/` 下有 10 个历史 run（2026-09-07，Objective-C 目标模式），
记录了一次完整的「基准 → 实现 → 编译截图 → 用户否决 → 迭代」闭环。它们**早于产物契约**，
已在各自 `run.json` 中标记 `"legacy": true`，原始文件备份在同级 `.legacy-originals/`。
其中的 `changedRatio=0.375 却判定 pass` 正是被修复的比较器缺陷，事故样本已固化到
`scripts/tests/fixtures/`。
