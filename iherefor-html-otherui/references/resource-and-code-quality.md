# 资源治理与企业级代码结构

## 资源目录决策（强制）

生成代码前必须扫描目标工程现有资源，并在页面 run 中保存 `resource-policy.json`：

1. iOS 先查 `.xcassets`、已有 `Resources/Assets/Images` 目录、`Contents.json` 的命名和渲染规则；Android 先查 `res/drawable*`、`mipmap*`、`res/font` 以及项目的资源前缀约定。
2. 若工程已有资源体系，复用其目录、命名、scale/density、渲染模式和模块归属；禁止另建平行 `assets` 目录或把 Lanhu 原名直接复制进生产工程。
3. **切图归位是硬禁令，不可例外**（与 `SKILL.md`「资源归位硬约束」同步）：切图/位图/SVG **严禁散落在项目根目录、源码目录或任意 `*.m/*.swift/*.kt/*.java` 同级**。iOS 一律进目标模块 `Assets.xcassets`，按业务域分组为 `Assets.xcassets/<业务域>/<语义名>.imageset/`，每个 imageset 内放 `Contents.json` 与 `1x/2x/3x` 三张资源；Android 一律进 `res/drawable(-density)*`。即使只有一张也必须入 imageset，不得平铺。
4. 命名必须表达使用场景，而非 `img_0.png`、`image1.png` 等来源编号。推荐 `<screen>_<region>_<role>`，例如 `plan_selection_hero_collage`、`plan_selection_close_icon`；imageset 目录名与资源语义一致。
5. 资源映射写入页面 `source/assets-manifest.json` 和目标 run 的 `resource-policy.json`，包含来源、目标路径、语义名、scale/density 和是否复用。
6. 复制/转换到目标工程后才标记 `verified=true`；缺失、重复或命名冲突阻塞交付。

### iOS imageset 标准结构（参考 `ColorfulPaint` 工程）

```
Assets.xcassets/
  guide/                          # 业务域分组
    guide_img_1.imageset/
      Contents.json               # { "images": [
                                  #   { "filename": "guide_img_1.png",  "scale": "1x" },
                                  #   { "filename": "guide_img_1@2x.png", "scale": "2x" },
                                  #   { "filename": "guide_img_1@3x.png", "scale": "3x" } ] }
      guide_img_1.png
      guide_img_1@2x.png
      guide_img_1@3x.png
```

每个 imageset 的 `Contents.json` 必须显式声明 `1x/2x/3x` 三档 filename 与 scale；缺 `Contents.json` 或 scale 声明不全会导致 Xcode 无法识别该资源。业务域分组用语义词（如 `guide`、`paywall`、`onboarding`）而非页面 id 或随机编号。

### 切图倍率的真相与正确获取（强制，极易踩坑）

MCP（`lanhu-mcp`）**拿不到无损的 1x/2x/3x 三套切图**，它只有「一张原图 + 一组在线缩放 URL」：

- 蓝湖切图**只存一张图**：`stored = logical × sliceScale`（通常 `sliceScale = 2`，即原图就是 2x）。这张原图是唯一无损像素源。
- `lanhu_get_design_slices` 返回的 `scale_urls`（`1x/2x/3x`/`ios_*`/`android_*`）**全部是 OSS `x-oss-process=image/resize` 在线缩放拼出来的 URL，不是预先生成的无损三套文件**。
- 其中 `2x` 是原图本身（真高清）；`1x` 是下采样（无损收容，安全）；**`3x` 是从 2x 上采样插值放大（信息量 = 2x，会糊）——这是假高清**。

**正确主张（务必遵守）**：

1. **禁止用 `scale_urls` 的上采样结果去凑 imageset 的 `3x` 坑位**。上采样不增加信息，Retina 屏放大后反而暴露糊边。
2. `1x` 可由原图安全下采样；`2x` 直接取原图；**`3x` 只能来自两条路之一**：
   - 设计师在蓝湖按 `3x` 重新导出（服务端真的生成 3x 原图）；或
   - **矢量 SVG**（`is_vector` 资源 `resolution_limited` 恒为 `false`，任意倍率无损，是真正的"任意倍率高清"）。
3. 需要真 3x 时优先拿 SVG；只有必须用栅格 3x 且蓝湖确已按 3x 导出时，才用栅格。**不要用 MCP 或本地工具对 2x 做放大来伪造 3x。**
4. 若只有一张原图、无 SVG、也无 3x 原图，则 imageset 里只放 `@2x` 一张（`Contents.json` 仅声明 `2x`），并把「缺 3x」写入 `unsupported` 说明原因，**不得**用假 3x 冒充。

资源接入还必须验证显示 frame 来自页面 `canvasTransform.coordinateMapper`。图片 frame、`contentMode`/`scaleType`/`ContentScale` 与 alpha 内容 bounds 的硬约束以 `SKILL.md` 的「图片缩放硬约束」一节为准，本文件不再重复；每张图片仍必须在 `resource-policy.json` 中记录 Lanhu frame、目标 mapped frame、scaleX/scaleY 与最终截图 frame。

## 生产文件命名（强制）

文件名不得由 skill 固定。Agent 必须先理解页面语义（页面职责、区域、交互和领域对象），再结合目标工程的目录和命名惯例提出候选，并在页面 `plans/integration-plan.json` 的 `filesToAdd` 中登记。命名应让维护者仅凭文件名即可判断职责，例如 `SubscriptionPlanSelectionViewController`、`PlanOptionCardView`、`SubscriptionPlanStyle`；若工程已有 `Paywall*` 术语则必须复用该术语。创建前检查同名文件、模块可见性和类名冲突；冲突时改用更准确的语义名，不能追加 `New`、`Copy` 或随机数字。

## 企业级代码结构（强制）

生成 UI 不得集中在一个巨大控制器或 `viewDidLoad`。Objective-C/UIKit 按语义化的 ViewController、View/Section、Style/Constants、Resources 分层；SwiftUI、Swift/UIKit 和 Android 分别采用对应的 Screen、区域组件、Model/Theme/Dimens、Resources 分层。具体文件名由页面内容和既有工程约定决定，每个文件只承担一个清晰职责，页面专属组件不污染全局组件库。

## 点击事件空函数（强制）

所有可点击元素必须连接到命名明确的处理函数，即使业务尚未实现：Objective-C 使用 `- (void)didTapTryForFree:(id)sender`、`- (void)didTapRestore:(id)sender`，Swift/Android 使用对应命名 handler。实现中保留 `TODO: connect business action` 或埋点占位，不得使用无名 inline block 或静默 return。事件映射写入 `interactionCandidates`，测试验证控件可找到且 handler 已连接。
