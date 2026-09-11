# 资源治理与企业级代码结构

## 资源目录决策（强制）

生成代码前必须扫描目标工程现有资源，并在页面 run 中保存 `resource-policy.json`：

1. iOS 先查 `.xcassets`、已有 `Resources/Assets/Images` 目录、`Contents.json` 的命名和渲染规则；Android 先查 `res/drawable*`、`mipmap*`、`res/font` 以及项目的资源前缀约定。
2. 若工程已有资源体系，复用其目录、命名、scale/density、渲染模式和模块归属；禁止另建平行 `assets` 目录或把 Lanhu 原名直接复制进生产工程。
3. 若工程没有约定，采用平台默认最佳实践：iOS 使用目标模块 `.xcassets`，Android 使用 `res/drawable-nodpi` 或对应 density 目录。
4. 命名必须表达使用场景，而非 `img_0.png`、`image1.png` 等来源编号。推荐 `<screen>_<region>_<role>`，例如 `plan_selection_hero_collage`、`plan_selection_close_icon`。
5. 资源映射写入页面 `source/assets-manifest.json` 和目标 run 的 `resource-policy.json`，包含来源、目标路径、语义名、scale/density 和是否复用。
6. 复制/转换到目标工程后才标记 `verified=true`；缺失、重复或命名冲突阻塞交付。

资源接入还必须验证显示 frame 来自页面 `canvasTransform.coordinateMapper`。图片 frame、`contentMode`/`scaleType`/`ContentScale` 与 alpha 内容 bounds 的硬约束以 `SKILL.md` 的「图片缩放硬约束」一节为准，本文件不再重复；每张图片仍必须在 `resource-policy.json` 中记录 Lanhu frame、目标 mapped frame、scaleX/scaleY 与最终截图 frame。

## 生产文件命名（强制）

文件名不得由 skill 固定。Agent 必须先理解页面语义（页面职责、区域、交互和领域对象），再结合目标工程的目录和命名惯例提出候选，并在页面 `plans/integration-plan.json` 的 `filesToAdd` 中登记。命名应让维护者仅凭文件名即可判断职责，例如 `SubscriptionPlanSelectionViewController`、`PlanOptionCardView`、`SubscriptionPlanStyle`；若工程已有 `Paywall*` 术语则必须复用该术语。创建前检查同名文件、模块可见性和类名冲突；冲突时改用更准确的语义名，不能追加 `New`、`Copy` 或随机数字。

## 企业级代码结构（强制）

生成 UI 不得集中在一个巨大控制器或 `viewDidLoad`。Objective-C/UIKit 按语义化的 ViewController、View/Section、Style/Constants、Resources 分层；SwiftUI、Swift/UIKit 和 Android 分别采用对应的 Screen、区域组件、Model/Theme/Dimens、Resources 分层。具体文件名由页面内容和既有工程约定决定，每个文件只承担一个清晰职责，页面专属组件不污染全局组件库。

## 点击事件空函数（强制）

所有可点击元素必须连接到命名明确的处理函数，即使业务尚未实现：Objective-C 使用 `- (void)didTapTryForFree:(id)sender`、`- (void)didTapRestore:(id)sender`，Swift/Android 使用对应命名 handler。实现中保留 `TODO: connect business action` 或埋点占位，不得使用无名 inline block 或静默 return。事件映射写入 `interactionCandidates`，测试验证控件可找到且 handler 已连接。
