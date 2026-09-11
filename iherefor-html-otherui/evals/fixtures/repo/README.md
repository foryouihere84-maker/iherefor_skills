# evals/fixtures/repo

`diff-gate-blocks-high-diff` 用例的工作区模板：只放该用例需要的两张对照图，让用例不依赖
被测 Agent 的当前目录，也不依赖 skill 内部的 `scripts/tests/fixtures/`。

| 文件 | 说明 |
|---|---|
| `images/reference.png` | 事故 run 011 的 HTML 基准截图，786×1704 |
| `images/actual-device-downscaled.png` | 同一 run 的降采样派生图，786×1704 |

两张图尺寸相同、约 37.5% 像素不同，正是当年被判 `pass` 的那一对。用例要求 Agent 用 skill
自带的比较脚本得出结论，再由 `evals/fixtures/scripts/check-diff-verdict.sh` 核对结果。

原始证据与背景见 [`../../../scripts/tests/fixtures/README.md`](../../../scripts/tests/fixtures/README.md)。
