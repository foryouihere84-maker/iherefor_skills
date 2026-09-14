这次不一致的账要记在**基准渲染**这一侧。

## 声明 ≠ 结果

CSS 里确实写着 `font-family: AvenirLT-Black`（价格那行是 `AvenirLT-Medium`），但那是**请求**，
不是结果。运行时元数据里两处都能看出它没被满足：

- `reference/browser-meta.json` 的 `fontProbe.fontFaceRules` 是空数组：页面里 **@font-face 规则数为 0**，
  而 `declaredFamilies` 里明明白白列着 `AvenirLT-Black` / `AvenirLT-Medium` —— 声明了，但没有任何字体来源。
- 声明里**也没有** generic fallback（不是 `AvenirLT-Black, sans-serif`，就只是
  `AvenirLT-Black`），所以解析失败后没有第二选择，浏览器只能落到默认衬线字体。

`reference/page-facts.json` 的运行时实测给出了结果：

| # | 元素 | 声明 | 实际解析（`primaryFont.family`） | advanceWidth |
| --- | --- | --- | --- | --- |
| 3 | Choose Your Plan | `AvenirLT-Black` | **Times** | 172.734 |
| 7 | Alpha | `AvenirLT-Black` | **Times** | 43.119 |
| 15 | $59.99 | `AvenirLT-Medium` | **Times** | 61.244 |
| 22 | Try For Free | `PingFang SC` | PingFang SC | 84.617 |

前三个声明 `AvenirLT-*` 的元素全部回落到了 **Times**；第四个声明 `PingFang SC` 的元素解析正确，
正好是这条链的对照组 —— 说明回落只发生在声明了不存在族名的元素上，不是测量本身有问题。

旁证：`AvenirLT-Black` 的排版宽度 172.734px 与 Times **逐位相同**，而真正的 `Avenir-Black`
是 198.156px。标题因此窄了约 23.6pt（= 25.422px 的宽度差经排版累积）。

## 为什么 `alignment.json` 会指向 App 侧

这份基准是**自洽地错**的：DOM 事实表与基准图都是同一套 Times 渲染出来的，所以
`domVsReference` 判 `aligned` 是必然的 —— 它们当然一致，因为用的是同一套错误字体。
对齐审计只比较**位置**，它没有、也无法回答「DOM 的排版结果本身对不对」。于是它顺着给出
「基准图可信 ⇒ 问题在 App 实现侧」，这个结论在它的视野内是对的，但它建立在一个坏基准上。

照着它去改 App 的字体，只会让 App 去追一个错误的目标；而且 App 侧用的是系统真实的
`Avenir-Black` / `Avenir-Heavy`，本来就更接近设计稿。

## 结论

`fixSide: "baseline"`。先修基准的字体栈（补 `@font-face` 指向真实字体文件，或换成运行时
真实存在的族名），然后**重新渲染基准、重新采集事实表**，再跑一次对齐审计。在基准修好之前，
这一轮 `referenceVsActual` 的偏差数字不具证据效力，不应据此改 App 代码。
