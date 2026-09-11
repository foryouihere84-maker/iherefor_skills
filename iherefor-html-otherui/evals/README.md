# evals/

iherefor-html-otherui 的 skill-up 评测套件。它测的**不是脚本能不能跑**（那是
[`../scripts/tests/`](../scripts/tests/) 的职责），而是**读了这份 skill 的 Agent 会不会守住红线**。

## 与 scripts/tests/ 的分工

| | `scripts/tests/` | `evals/` |
| --- | --- | --- |
| 被测对象 | 脚本本身 | 读了 skill 的 Agent |
| 需要 LLM | 否 | 是 |
| 单次成本 | 0 | 6 个用例的 Agent 执行 |
| 何时跑 | 每次提交（CI） | 改 `SKILL.md` / `references/` 后、发版前 |
| 失败含义 | 工具坏了 | 规则写得不清楚，或 Agent 没被约束住 |

两者互补：脚本测试全绿只说明工具可用，不代表 Agent 会正确使用它们。run 011 的事故就是
「脚本有缺陷 + Agent 照信了脚本的结论」，只补一侧都堵不住。

## 用例

| 用例 | 目标红线 | 判分 |
| --- | --- | --- |
| `diff-gate-blocks-high-diff` | 高像素差异不得被放行（run 011 事故样本） | script |
| `reference-must-share-device-canvas` | 基准图必须与设备截图同源 | rule_based |
| `image-scaling-hard-constraints` | 图片必须显式映射尺寸，不能靠 intrinsic size | rule_based |
| `click-handler-naming` | 可点击元素必须连到命名 handler，并留业务占位 | rule_based |
| `resource-semantic-naming` | 资源按 `<screen>_<region>_<role>` 命名 | script |
| `scripts-must-not-generate-source` | 脚本不得生成或覆盖生产 UI 源码 | rule_based |

## 判分原则

1. **能用产物判就不看自述**。两个 script judge 直接读 `diff/verdict.json` 与
   `resource-policy.json`；Agent 说自己"判了 fail"不算数，文件内容才算数。
2. **判分脚本双向验证过**：合规输入必须 PASS，违规输入必须 FAIL。只验证单向的判分器
   很容易变成永远通过的摆设。
3. **不用 agent_judge**。本 suite 的每条红线都能落成确定性断言，没必要为一句话的语义
   判断付 LLM 的钱。真正需要语义评估时再加。

## 运行

```bash
skill-up validate evals/eval.yaml          # 校验配置，不需要凭据
skill-up run evals/eval.yaml --dry-run     # 看会跑哪些用例，不需要凭据
skill-up run evals/eval.yaml               # 真跑，需要引擎凭据
```

先用 `--include-case-name <id>` 跑单例确认链路，再全量——避免判分脚本或工作区语义跟预期
不一致时一次性烧掉全部额度。

## 环境假设

- `environment.type: none`：这些用例只做文本与文件断言，不启动浏览器、不访问 Lanhu，
  因此不需要 MCP 凭据。
- 两个 script judge 需要在工作区里跑通 `compare_reference.py`，即 Python 有 Pillow。
  skill 安装保留了 `.runtime/`，`requirements.txt` 里有 `Pillow`。
- `evals/` 由 skill-up **强制排除**，被测 Agent 看不到判分脚本与用例定义。
- `diff-gate-blocks-high-diff` 用 `context.repo_fixture` 把对照图拷进工作区，
  fixture 在 [`fixtures/repo/`](fixtures/repo/)：`repo_fixture` 的语义是**拷贝内容到工作区根**，
  所以用例里的路径都是工作区相对路径，不是 skill 相对路径。

## 新增用例

1. 写 `evals/cases/<id>.yaml`，**文件名即用例 ID**，别忘了把它加进 `eval.yaml` 的 `cases.files`。
2. 优先用 `expect`（零成本门槛）挡一道，再用 `judge` 判质量。
3. 判分脚本放 [`fixtures/scripts/`](fixtures/scripts/)，必须可执行（`chmod +x`），
   退出码 `0` = PASS；CI 会校验语法与可执行位。
4. 加完至少跑一次 `skill-up validate` 与 `--dry-run`。
5. 判分脚本写完先用手工构造的合规/违规输入各跑一遍。
