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

套件分两层，**下面那层完全不需要 Agent Engine 凭据**：

```bash
# 第 1 层：判分器自检（零凭据、零 LLM，已接入 scripts/tests/run_all.sh 与 CI）
python3 evals/harness/selfcheck.py

# 第 2 层：真实 Agent 执行（需要引擎凭据）
skill-up validate evals/eval.yaml          # 校验配置，不需要凭据
skill-up run evals/eval.yaml --dry-run     # 看会跑哪些用例，不需要凭据
skill-up run evals/eval.yaml               # 真跑，需要引擎凭据
```

第 1 层用每个用例自带的两份样本（`fixtures/golden/<case-id>/{pass,fail}/`）验证判分器本身：
`pass` 样本必须判过、`fail` 样本必须判挂。它保证的是**判分逻辑有效**——一个永远返回 PASS 的
判分器，或者一条谁都满足不了的断言，在这里会立刻暴露。没有这层，判分器的错误只能等到花额度
真跑时才发现，而那时看到的"用例失败"分不清是 Agent 做错了还是判分写错了。

也可以单独判任意一次执行结果：

```bash
python3 evals/harness/run_case.py --case evals/cases/<id>.yaml \
    --workspace <工作区> --message <最终回答文件>
```

第 2 层跑之前先用 `--include-case-name <id>` 跑单例确认链路，再全量——避免判分脚本或工作区
语义跟预期不一致时一次性烧掉全部额度。

## 先排练，再花额度

改完用例之后，可以先用一个本地 Agent 把单个用例手工走一遍，全程零成本：

1. 把 skill 复制到临时目录，**务必排除 `evals/`**——否则被测 Agent 能看到判分脚本，等于泄题
   （`skill-up` 自己在安装时也是强制排除 `evals/` 的）。
2. 把 `context.repo_fixture` 指向的目录内容拷进一个独立工作区。
3. 把用例的 `input.prompt` 原样发给它，只补充「skill 在哪、工作区在哪」。
4. 拿判分脚本对着产出的工作区判一次。

这能在花额度之前抓出三类问题：用例路径写错、判分脚本对着真实产物误判、Agent 根本没有
可用的运行环境。**它不能替代 `skill-up run`**：同一个模型自测不是独立评测，只能证明
「规则写得能被读懂」，证明不了「换一个模型也守得住」。

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
3. **必须同时补一对样本**：`fixtures/golden/<id>/pass/` 与 `fixtures/golden/<id>/fail/`，
   各放一个 `answer.md` 和该场景需要的工作区文件。缺样本会被 `selfcheck.py` 直接判失败，
   这样新用例不会带着未验证的判分器进仓库。
4. 判分脚本放 [`fixtures/scripts/`](fixtures/scripts/)，必须可执行（`chmod +x`），
   退出码 `0` = PASS；CI 会校验语法与可执行位。
5. 跑 `python3 evals/harness/selfcheck.py`，确认新用例的 pass 样本判过、fail 样本判挂。
6. 最后再跑一次 `skill-up validate` 与 `--dry-run`。
