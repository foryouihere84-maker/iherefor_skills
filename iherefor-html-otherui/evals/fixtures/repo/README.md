# evals/fixtures/repo

`diff-gate-blocks-high-diff` 与 `same-size-needs-region-evidence` 两个用例共用的工作区模板：
只放该用例需要的两张对照图，让用例不依赖被测 Agent 的当前目录，也不依赖 skill 内部的
`scripts/tests/fixtures/`。

**只有 `workspace/` 这一层会被拷进用例工作区** —— 本文件记着用例结论，属于判分侧文档，
绝不能进被测 Agent 的工作区。所以两个用例的 `repo_fixture` 都指向
`evals/fixtures/repo/workspace`，而不是这个目录本身。

`repo_fixture` 的语义是**把目录内容拷到工作区根**，所以用例 prompt 里写的是工作区相对路径
（`images/reference.png`），与被拷进去的那一层同名，无需跟着改。

| 文件（相对 `workspace/`） | 说明 |
|---|---|
| `images/reference.png` | 事故 run 011 的 HTML 基准截图，786×1704 |
| `images/actual-device-downscaled.png` | 同一 run 的降采样派生图，786×1704 |

两张图尺寸相同、约 37.5% 像素不同，正是当年被判 `pass` 的那一对。用例要求 Agent 用 skill
自带的比较脚本得出结论，再由 `evals/fixtures/scripts/check-diff-verdict.sh`（或
`check-region-evidence.sh`）核对结果。

**为什么必须分两层。** 早先这里是扁平结构（`images/` 与 `README.md` 平级），于是 `README.md`
会连同素材一起被拷进工作区 —— 那等于把答案发给了被测 Agent。同类事故的形态很隐蔽：文件本身
完全正常，只是「拷什么」的边界画错了。新增 fixture 时务必照
[`../font-fallback/`](../font-fallback/) 的两层结构来。

原始证据与背景见 [`../../../scripts/tests/fixtures/README.md`](../../../scripts/tests/fixtures/README.md)。
