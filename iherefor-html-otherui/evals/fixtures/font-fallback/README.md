# 字体链用例的素材（font-fallback）

这是 `evals/cases/font-fallback-belongs-to-baseline.yaml` 的 `context.repo_fixture`。

**只有 `workspace/` 这一层会被拷进用例工作区** —— 本文件记着正确结论，属于判分侧文档，
绝不能进被测 Agent 的工作区。所以 `repo_fixture` 指向的是
`evals/fixtures/font-fallback/workspace`，不是这个目录本身。

## 场景

Lanhu 导出页的 CSS 里写着 `font-family: AvenirLT-Black` / `AvenirLT-Medium`，但：

- 页面里 `@font-face` 规则数为 **0**（`fontProbe.fontFaceRules = []`）；
- 没有任何字体文件被加载；
- 声明里**也没有** generic fallback（没有 `sans-serif`）。

Chromium 于是静默回落到默认衬线字体 **Times**。`page-facts.json` 里三个声明 AvenirLT-*
的元素，`primaryFont.family` 全是 `Times`；只有第四个元素（声明 `PingFang SC`）解析正确，
它就是这条用例的**对照组**。

## 为什么这份基准「自洽地错」

`alignment.json` 的两个结论要分开读：

| 比较 | 结论 | 含义 |
| --- | --- | --- |
| `domVsReference` | `aligned` | DOM 事实表与基准图一致——**因为两者都是同一套回落字体渲染出来的** |
| `referenceVsActual` | `needs-review` / `constant-offset` | 基准图与实机截图差 21.5pt（最大 24.0pt，出自标题） |

对齐审计只能比较**位置**，它给出「基准图可信 ⇒ 问题在 App 实现侧」是它视野内的正确结论。
但这份基准图的排版结果本身就是用错字体排出来的：工具不会去问「DOM 的排版结果对不对」，
所以这条结论掩盖了真正的根因。条目 `verdict` 里那句「问题在 App 实现侧」是**故意保留的**
诱导项——照着它去改 App 的字体，只会离设计稿越来越远。

## 正确的结论

基准这一侧的字体链断了，该改的是**基准的字体栈**（补 `@font-face` 或换成运行时真实存在的
族），改完重新渲染基准、重新测量，再判断 App 侧还有没有残余差异。

实测旁证：`AvenirLT-Black` 的排版宽度 172.734px 与 Times **逐位相同**，而真正的
`Avenir-Black` 是 198.156px —— 标题因此窄了约 23.6pt。

## 关于 `reference/page-facts.json` 的形状

这份事实表是**手工摘录**：只留了 4 个文本元素（3 个断链 + 1 个对照组），
`schemaVersion` 停在 **2**。它不是任何一次真实渲染的产物，也不需要是 —— 本用例读的是
字体链（`fontFamily` / `fontsResolved` / `primaryFont` / `textMetrics.advanceWidth`），
而 `scripts/audit_fonts.py` 读这些字段时**不依赖**层级字段（`parentIndex` 等 v3 新增项）。

所以：**不要**把它「升级」到 v3。真实渲染器现在产出的是 v3（元素齐、带层级），
往这份摘录上盖章只会让它声称一些它没有的东西。

需要 v3 事实表做布局核对的场景，见 [`../device-derived-layout/`](../device-derived-layout/)。

