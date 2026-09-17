# evals/

iherefor-html-otherui 的 skill-up 评测套件。它测的**不是脚本能不能跑**（那是
[`../scripts/tests/`](../scripts/tests/) 的职责），而是**读了这份 skill 的 Agent 会不会守住红线**。

## 与 scripts/tests/ 的分工

| | `scripts/tests/` | `evals/` |
| --- | --- | --- |
| 被测对象 | 脚本本身 | 读了 skill 的 Agent |
| 需要 LLM | 否 | 是 |
| 单次成本 | 0 | 10 个用例的 Agent 执行 |
| 何时跑 | 每次提交（CI） | 改 `SKILL.md` / `references/` 后、发版前 |
| 失败含义 | 工具坏了 | 规则写得不清楚，或 Agent 没被约束住 |

两者互补：脚本测试全绿只说明工具可用，不代表 Agent 会正确使用它们。run 011 的事故就是
「脚本有缺陷 + Agent 照信了脚本的结论」，只补一侧都堵不住。

## 用例

| 用例 | 目标红线 | 判分 |
| --- | --- | --- |
| `image-scaling-hard-constraints` | 图片必须显式映射尺寸，不能靠 intrinsic size | rule_based |
| `click-handler-naming` | 可点击元素必须连到命名 handler，并留业务占位 | rule_based |
| `resource-semantic-naming` | 资源按 `<screen>_<region>_<role>` 命名 | script |
| `scripts-must-not-generate-source` | 脚本不得生成或覆盖生产 UI 源码 | rule_based |
| `layout-no-device-derived-coordinates` | 布局不得照抄探针设备上的量取值（位置相对直接父视图、尺寸写清由什么闭合），且不得把设计常量 / `fixed` 候选 / 待判值当成违规 | script |
| `adaptive-ipad-requires-width-axis` | 平板适配必须真的落到源码（第三条轴），且要分清「计划没问题、源码没照做」 | script |

`layout-no-device-derived-coordinates` 考的是**本 skill 最重要的那条硬约束，而且是双向的**：设计稿只有一个尺寸
（393×852），把换算结果写成绝对值就把布局钉死在探针设备（402×874）上了 —— 换台设备就是错的，
而它「有算过」，比一眼可疑的魔数更难发现。素材里混了真设计常量（圆角 12、发丝线 1、
最小点击区 44）、生成端推的 `fixed` 候选（68/48）与一批小数值（23/25），所以既查召回也查精度：
漏掉大数值是漏报，把设计常量 / 候选 / 待判值报成违规是误报，**两头都算不过**。小数值与设计
常量无法区分时，工具列进 `ambiguousLiterals` 待人工判断，不计入违规 —— 闸门要准，不是要响。

这条用例在闭合契约（v4）下换过一次判据，**换掉的那一条本身就是个坑**：旧判分器要求
`relationKindCounts.fixed > 0`，用来证明「计划不是旧的一轴产物」。可新契约里 `fixed` 只是
生成端给的**候选**，一个复核得对的 Agent 恰恰会把 `offers.height` / `cta.height` 改判成
`intrinsic` / `bounded`，于是 `fixed = 0` —— 旧判分器会把**正确实现判成 fail**。现在改成查
`schemaVersion >= 4`（出处）与 `pinned` / `proportional` 都非零（位置轴还在），并新增一条
`reviewPending` 断言：候选被点名才算「接住了」。没有这条，「豁免 68/48」可以靠退回旧口径
「尺寸是常量」蒙对，而旧口径正是这轮要废掉的东西。

> 「固定尺寸 → 内容闭合」这个坑值得单独记一笔：**判据升级时，最危险的不是漏掉新检查，
> 而是旧检查在新口径下反过来惩罚正确答案。** 这类问题的形态是「用例失败」，看起来像
> Agent 做错了；只有把用例样本按新口径重跑一遍才会暴露。

`adaptive-ipad-requires-width-axis` 考的是**第三条轴，以及「工具跑没跑对」**。前两条轴
（不抄设备量值、位置相对直接父视图）只保证「换设备不崩」，回答不了「父视图宽到 1024pt 时
内容怎么收敛」—— 而缺了这条轴，`393×852 → 402×874` 上成立的第一层位置比例推到 1024pt
会给出**错的**结果（位置 ×2.6、尺寸 ×1，内容被挤到左侧）。素材里计划声明是完整的，
源码却用 `UIScreen.main.bounds.width` 取宽度、没有任何封顶原语、`Info.plist` 只声明竖屏。
这三条**截图全都看不出来**：全屏下屏幕 bounds 与 view bounds 恰好相等，竖屏手机上永远走不到
别的宽度档，封顶在手机档下与不封顶视觉一致。所以这条红线只能靠静态门守。

它同时考精度（**计划是完整的，报成违规是误报**）与一件容易漏的事（计划声明了宽度轴，
交付闸门就是 **8 项**，而素材里只有 7 项 —— 少一项最容易伪装成「全绿」）。
`fail` 样本复刻的是最常见的错误动作：**只跑 `--plan-only`** —— 那样只会得到 `status: pass`，
因为计划确实没问题，问题在源码。

## 判分原则

1. **能用产物判就不看自述**。script judge 直接读 `diff/verdict.json`、
   `diff/comparison.json`、`diff/font-substitution.json`、`diff/layout-proportions.json`、
   `diff/adaptive-layout.json` 与 `resource-policy.json`；
   Agent 说自己"判了 fail"不算数，文件内容才算数。
2. **判分脚本双向验证过**：合规输入必须 PASS，违规输入必须 FAIL。只验证单向的判分器
   很容易变成永远通过的摆设。`font-fallback-belongs-to-baseline` 的判分器还额外做过
   **逐条变异探测**：把 pass 样本分别改成「照抄 CSS 声明」「记成没替换」「归给 App」
   「声明记错」「清空 affectedElements」「清空 evidence」「删掉 fixSide」，每一条都必须
   单独触发对应的那条断言 —— 用来证明没有一条断言是死代码。
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

`selfcheck.py` 同时校验**每个 `repo_fixture` 指向的目录里不许有文档文件**。这是「两层
fixture」约定的可执行版本：`repo_fixture` 的语义是把目录内容拷进被测 Agent 的工作区，
而 fixture 根目录的 `README.md` 记着用例的正确结论，一旦与素材平级就会被一起拷进去，
等于泄题。这类问题的形态很隐蔽——**文件本身全都正常，错的是「拷什么」的边界**，
评审时很难看出来。`fixtures/repo` 与 `fixtures/assets` 都曾经是这种扁平结构，加上这条
检查时才被发现。

它同时校验**fixture 的文本文件里不许出现钉死在某台机器上的绝对路径**。样本记录的是
「一次正确执行长什么样」，其中不少字段是工具**原样产出的**，而工具写路径用的是
`Path(...).resolve()` —— 于是绝对路径被一起存进样本，换台机器、或仓库换个位置就指向
不存在的地方。这类字段**不参与断言**，所以不会让任何测试变红，只能主动扫。真正的危害是
**样本失真**：下次拿样本跟真跑结果对照，会看到一个纯属环境差异的「不一致」，甚至顺手把
样本改回绝对路径；同一用例的 `pass` / `fail` 两份样本也会因此写法不一致
（`same-size-needs-region-evidence` 就曾经如此：`fail` 是工作区相对写法、`pass` 是绝对路径）。
记录工具输出时把这类字段改写成工作区相对形式，如 `images/reference.png`。

它还会校验**每个用例的 `judge.script_path` 都存在且带可执行位**。可执行位这条约定本就写在
下面「新增用例」一节里，但判分器是用 `bash <path>` 调用的 —— 少一个 `+x`，测试**永远不会**
变红，只会在人手动 `./check-xxx.sh` 时报 permission denied，而那时人往往正在排查别的问题。
`check-region-evidence.sh` 就曾经漏了可执行位（同目录另外四个都有）。

最后一项是**文档链接与锚点可达**：校验 `SKILL.md`、`references/**`、`evals/*.md` 里
每一条相对链接的目标存在，且 `#锚点` 在目标文件的标题里真的能折出来（支持中文标题的
GitHub slug 规则）。它同样**不会让任何测试变红**：链接文字读起来完整、锚点看着也像那么回事，
只有真正照着点过去的人（也就是照着 skill 干活的 agent）才发现跳不过去。
最常见的触发条件恰恰是「重命名章节」这种本来很安全的整理动作 —— 文件在、标题在，
只是 slug 对不上，改一个标点就够了。只查本 skill 自己撰写的文档：fixture 素材与第三方
子项目里的相对路径指向被测工作区，本就不该在本仓库里存在，纳入检查只会制造假告警。

> 检查器本身也要防假告警。第一版把目标限定为「文件存在」，于是 `evals/README.md` 里
> 指向目录的 `fixtures/repo/` 等四条链接全部被误报 —— 而**假告警会训练出「看到告警就
> 忽略」的习惯**，比漏报更有害。目录也是合法目标。

### 变异探针：证明断言不是空的

`selfcheck.py` 证明「pass 判过、fail 判挂」，但它管不到「断言本身有没有在断言」——
一条 `if 条件满足才检查` 的分支，在条件不满足时会静默短路，而样本恰好走到那条路径上，
于是两边都"如预期"。

```bash
python3 scripts/tests/mutation_probe.py   # 改完生成端 / 校验器后手动跑
```

它逐条把被测实现改坏（并先断言改动确实落进源码），要求对应测试**变红**。
全绿即空断言。**不进 `run_all.sh`** —— 它会临时改写被测源码，不适合并发 CI。

改判分器时也可以用同样手法：把 `fail` 样本的判分逻辑逐条放宽，确认它仍然判挂。
本轮的实践教训是**探针本身也会骗人**，已经踩到五种形态：

- `sed` 锚点没匹配上，改动其实没落进源码；
- `bash` 相对路径在样本目录下解析不到（exit 127）；
- `Path(...).resolve()` 把 venv 的 `python3` 符号链接解到真实解释器，venv 站点配置随之
  丢失，子进程 import 失败 —— 于是「基线」就已经不是基线了；
- **红了，但红得不对**：探针删掉守卫后被测函数在空对象上取下标直接 `KeyError` 掉栈，
  退出码非 0 被读成「断言有效」—— 其实那条断言一次都没执行。所以崩栈单独判无效，并要求
  探针复刻**历史上真实的那段实现**，而不是删几行代码凑一个红。
- **崩在中途**：字体审计脚本（`scripts/audit_fonts`，已随渲染链裁撤而删除）留下的悬空探针
  在读文件时 `FileNotFoundError` 掉栈 —— 排在它**后面**的探针（fixture 可移植性、文档锚点）
  从此一条都没跑过，而当时本文件正写着「这两条就是这样验过的」。修复后它们一次跑红了两条
  早该发现的问题，其中一条还是本轮新写的判据漏了探针。所以现在「目标文件不存在」
  单列为一类**探针无效**，会继续往下跑，而不是让崩点静默截断整个列表。

五种都会被误读成「断言有效」。所以探针**必须先自证两件事**：基线确实通过（改动落进源码、
测试本身跑得动），以及变红确实由断言触发（崩栈不算）。`fixtures/repo` 的分层检查就是这样
验过的：基线 0 → 指回扁平目录 1（点名分层问题）→ 指向只有文档的目录 1（点名文档泄漏）
→ 还原 0；fixture 的路径检查也是同一个流程：先让它在既有样本上报错点名到具体行，再修素材。

判分器侧的探针：

```bash
.runtime/venv/bin/python3 evals/harness/probe_layout_judge.py   # 改完 layout 判分器后手动跑
```

它针对 `layout-no-device-derived-coordinates` 的判分脚本逐项变异，17 项都要如预期。
**注意它比上面那类探针多一类「反向断言」**，因为只验「改坏了一定变红」会漏掉本轮的
头号缺陷形态 —— 旧检查在新口径下**反过来惩罚正确答案**（旧判分器要求 `fixed > 0`，
而复核得对的实现会把候选改判成 `intrinsic`，于是 `fixed = 0`）。所以基线必须过、
以及「复核后 fixed=0 仍必须过」这两条是**必须判过**的反向断言，不是「变红才算有效」。
探针把这个区别直接写进了期望值表（`PROBES` 的第三列），而不是靠读的人自己记。

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
- script judge（`resource-semantic-naming`、`layout-no-device-derived-coordinates`、
  `adaptive-ipad-requires-width-axis`）是纯文件断言，只用标准库。
- `evals/` 由 skill-up **强制排除**，被测 Agent 看不到判分脚本与用例定义。
- `adaptive-ipad-requires-width-axis` 的 fixture 是
  [`fixtures/adaptive-ipad/`](fixtures/adaptive-ipad/)，只指向它的 `workspace/` 子目录。
  判分器是纯文件断言（只用标准库），**不需要真机多采样证据** ——
  `environment.type: none` 跑不出运行期几何，本用例只考静态那一半。
- **所有 fixture 都必须分两层**：`README.md`（判分侧，记答案）留在 fixture 根，
  素材放 `workspace/`。`repo_fixture` 的语义是**拷贝目录内容到工作区根**，所以用例里的路径
  都是工作区相对路径，指向 `workspace/` 时与被拷进去的那一层同名，无需跟着改。
  扁平结构的 fixture 会把答案一并拷进被测 Agent 的工作区 —— 文件本身没毛病，错的是
  「拷什么」的边界，所以这类问题很难在评审里看出来。

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
