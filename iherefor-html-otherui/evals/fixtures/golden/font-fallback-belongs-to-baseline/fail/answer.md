字体这边我核过了，声明和实际是一致的，没有发生替换。

CSS 里声明的是 `font-family: AvenirLT-Black`（价格那里是 `AvenirLT-Medium`），
`page-facts.json` 里这几个元素的 `fontFamily` 也是同样的值，两边对得上。
`browser-meta.json` 的记录显示字体测量方法正常走通了（`fontMeasurement.ok: true`，
`fontJoin.ok: true`，4 个文本元素全部量到），说明字体链是干净的。

真正的问题在 App 侧。`diff/alignment.json` 的两个结论很清楚：

- `domVsReference`：`aligned` —— 基准图和 DOM 事实完全一致，说明基准本身没问题；
- `referenceVsActual`：`needs-review` / `constant-offset` —— 基准图与实机截图差
  21.50pt（最大 24.0pt，出自标题）。

基准图可信，偏差只出现在实机截图上，所以这是 App 实现侧的布局问题。建议按区域逐个改：
标题先修（24.0pt 最大），然后是页脚 CTA（21.0pt）和年卡价格（15.7pt），最后是徽标（6.0pt）。
