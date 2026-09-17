# iOS / Android 智能开发编排

面向 iOS / Android **功能开发**的总入口：一条从「需求」到「交付」的闭环，多道人工审核闸门把关，跨端共享层贯穿两端。  
本 skill 是**编排器**——只负责路由、闸门判据与状态管理，在节点上**通过 Skill 工具点名调用**已有 skill，  
被点名 skill 的规则以其自身 SKILL.md 为准，本 skill 不复制、不改写任何被点名 skill 的正文。

分层对齐 Spec Kit 五层模型（Constitution → Spec → Plan → Tasks → Implementation），每层向下移交前都需上一层人工确认。

**分级（tier）**：按需求规模分 `full`（标准）与 `lite`（轻量）两档，判据与闸门收缩在 `config/tier.json`——lite 档把 c1/c2 合并进 b，仅保留 a/b/d + 交付门，少出部分产物。默认 full、按需 lite，见「阶段 0」。

## 何时使用

- 用户要在 iOS 或 Android（或两端同时）工程里**做一个功能**（登录、分页、支付接入、列表、状态管理重构等）。
- 用户明确说「开发 / 实现 / 做一个功能 / TDD 开发」且目标是 iOS/Android 原生工程。

## 硬约束（违反即停）

1. **前置依赖未就绪，不得开始**：进入六阶段闭环前，必须先跑「阶段 0 — 前置依赖检查」，  
   确认被点名 skill 已安装（见 `config/dependencies.json`）；缺失则先安装。  
   未落地不得开工。只有到某个阶段时才被用到的依赖，可以推迟到该阶段前再检查，但**该阶段开始前必须已就绪**。
2. **多道闸门全卡、且卡在写生产代码之前**：闸门 a（Spec 需求）、b（Plan 方案，最重）、c1（Plan 变更清单）、  
   c2（Tasks 拆分）、d（Implementation 实现），任一道未获用户明确确认，**不得**越过进入下一阶段。
3. **web 搜索优先读取白名单内的地址**：读 `config/trusted-sources.json`，子 agent 只允许搜 L1（官方文档）+ L2（教学站）；  
   L3（社区帖）仅用于查 bug 反例，禁止作为架构决策依据。结论必须附「一手来源引用」。
4. **跨端两端都要时，共享层先行**：先定共享层（需求 / 领域模型 / 数据契约），再各自分叉落地层。  
   不得两端各自独立开发、互不引用。
5. **编译是硬门槛**：iOS（Xcode）与 Android（Gradle）**分别编译通过**，不得用一端通过推断另一端。编译 0 error 才可交付。
6. **移动端 TDD 约定**以 `config/mobile-tdd.json` 与 `references/ios-tdd.md` / `references/android-tdd.md` 为准，  
   不得沿用语言无关的测试假设（如 Node/TS 生态的默认）。

## 阶段 0 — 前置依赖检查（进入闭环前的硬闸）

本 skill 是编排器，依赖一批被点名的 skill。**开始任何开发前，先核对依赖清单是否落地，并加载全局约束。**

1. **先读 `references/constitution.md`**：这是全局工程约束层（Constitution），所有后续决策都回到它；  
   它承载「原则」，可配置值仍以 `config/` 下 json 为准。
2. 读 `config/dependencies.json`，得到「必需 / 可选」两类被点名 skill 清单，以及每个 skill 负责的阶段。
3. 逐个检查是否已安装（Skill 工具的可用 skill 列表中有该 `name`；或检查 `~/.workbuddy-ai/skills/<name>/SKILL.md` 存在）。
4. **缺失的「必需」skill → 暂停，先安装**：用 Skill 工具点名 `install-local-skill`（它能处理作者核对、安全审计、  
   批量安装、端到端验证）；安装级别默认用户级。**不得内联缺失 skill 的规则来「绕过」。**
   - 属于 Matt Pocock 那套的（grilling / to-questionnaire / domain-modeling / to-spec / to-tickets / tdd /  
     implement / code-review / handoff / setup-matt-pocock-skills / improve-codebase-architecture / codebase-design /  
     research / prototype 等），通常整套来自同一作者仓库，可用 `install-local-skill` 的批量安装一次装齐，  
     并跑 `setup-matt-pocock-skills` 在目标项目里生成 `docs/agents/*.md`、`CONTEXT.md`、`docs/adr/`。
5. **缺失的「可选」skill → 不阻塞**，但到该阶段前若仍缺，明确告知用户「此环节跳过 / 降级」，不静默。
6. 按阶段惰性检查亦可：某阶段真正开始前，其依赖必须已就绪；不必一次性装完全部。
7. 装完后**重启会话/重新加载 skill 列表**才可被识别。
8. **读 `config/tier.json` 并判定分级**：用需求「第一眼可判」的信号把本功能划入 `full` 或 `lite`，并向用户确认。
   - **判据**：见 `tier.json` 的 `triggers`。单一改动点/有现成参照/无新依赖/不涉跨端共享层 → 倾向 `lite`；  
     新领域/跨端共享层/架构方向不明/涉及迁移/新增依赖 → `full`。默认 `full`，不确定就 full。
   - **lite 档的收缩**：闸门只剩 a / b / d / 交付门（c1、c2 合并进 b）；产物跳过 `tier.json` 的 `skip_artifacts` 清单；  
     阶段 2 不做 DESIGN-IT-TWICE 三案，仅在有 L1 官方参照需查证时做一次白名单搜索。
   - 阶段 1 结束时允许升/降级一次（`escalate_rule`），变更记入 `run-log.jsonl` 的 `tier_change` 事件。
   - 分级确定后，后续每个闸门、每份产物都按该档位执行；校验器 `scan-artifacts.py --tier <full|lite>` 据此核验。

## 五层闭环

```
[Constitution 全局约束] ─▶ [1 Spec 需求理清] --🔒a--> [2 Plan 架构设计] --🔒b(最重)--> [3 Plan 变更清单] --🔒c1--> [Tasks 拆分] --🔒c2-->
                                                                                                                        [4 TDD 落地] --🔒d--> [5 交付] --> [6 反馈 → 回跳]
```

> **满配链路（full 档）如上**。`lite` 档把 `--🔒c1-->`、`--🔒c2-->` 两步合并进 `🔒b`：proposal-draft 内同载「变更清单 + 执行步骤」，  
> 只做一次合并确认，不单独拆 tickets；闸门序列变为 `a → b → d → 交付门`。

> **阶段内部不是黑箱**：每层拆成多个明确任务，任务级契约（做什么 / 输入 / 产出物路径 / 可机检 DoD / 点名 skill）  
> 全部定义在 `references/task-breakdown.md`，本 SKILL.md 只保留层骨架与闸门。  
> 产出物统一落到目标工程 `docs/<feature>/`，按「分类目录 + 入口导航」组织（见 `templates/README.md`），  
> 每个产物**照 `templates/` 同名模板填空**，可用 `scripts/scan-artifacts.py` 机器核验章节闭环。  
> `Plan`（怎么做）与 `Tasks`（分几步做）是两个独立闸门 c1 / c2——对齐 Spec Kit 的「第三个必须停下点」。

### 阶段 1 — 需求理清（Spec）

> 任务级契约见 `references/task-breakdown.md` 阶段 1（1.1~1.5）。完成前先读，按「产出物 + 可机检 DoD」逐项执行。

- 用 Skill 工具点名 `grilling`：追问到共享理解；需求模糊就 grill，知识在他人手上就点名 `to-questionnaire`。
- 领域术语固化时点名 `domain-modeling`，沉淀进项目 `CONTEXT.md`。
- 产出：确认后的需求 + 领域模型 + 用户故事；**重点补 Out of Scope 与边界案例**（防 Agent 擅自扩范围）。
- 🔒 **闸门 a**：向用户确认「需求理解正确」，获明确 positive 回复才继续。

### 阶段 2 — 架构设计（Plan，本 skill 的增值核心）

> 任务级契约见 `references/task-breakdown.md` 阶段 2（2.1~2.7）。

**先搜事实、再并出多案，两步是前后关系，每轮方案设计前都要跑一次搜索。**

1. **web 白名单搜索**（调研取证）：点名 `research` 派子 agent，**约束在 `config/trusted-sources.json` 的 L1+L2 内**，  
   搜「该功能在 iOS/Android 的最佳实践 / 官方推荐写法」，产出一份带一手来源引用的**事实纪要**。
2. **并行多案择优**（设计决策）：基于事实纪要，用 `codebase-design` 的 **DESIGN-IT-TWICE** 模式派 3+ 子 agent  
   各出一套**截然不同**的接口/模块设计，再按 depth / locality / seam placement 对比，给出带立场的推荐（可给混合方案）。
3. **跨端共享层**：两端都要时，先在此阶段定共享层（领域模型、数据契约、不变量），落地层才分叉。

- 🔒 **闸门 b（最重）**：落地方案草案**必须人工确认**。不通过 → 回到本阶段重搜 / 重设计，不得进入阶段 3。

> **lite 档**：跳过 2.4~~2.5 的 DESIGN-IT-TWICE 三案；仅在有 L1 官方参照需查证时做一次 2.1~~2.2 搜索，否则直接进 2.7 出方案草案；  
> 不产出 `design-options.md` / `comparison.md` / `shared-layer.md`（见 `tier.json` 的 `skip_artifacts`）。

### 阶段 3 — 工程落地计划（Plan 变更清单 → Tasks）

> 任务级契约见 `references/task-breakdown.md` 阶段 3（3.1~3.4）。

- 点名 `improve-codebase-architecture` 扫描既有架构摩擦；结合 `research` 审计现有工程（导航 / 依赖 / 资源 / 状态 / 测试）。
- 产出**变更清单**：动哪些文件、加哪些依赖、改哪些签名/导航/资源、回滚方式。
- 🔒 **闸门 c1（Plan 变更清单）**：变更清单**批准后**才可拆 Tasks。
- 从变更清单切出**可独立执行的 tickets**。
- 🔒 **闸门 c2（Tasks 拆分）**：确认 tickets 覆盖了 Spec 的边界案例、无遗漏，才进入实现。

> **lite 档**：c1、c2 合并进闸门 b——`proposal-draft.md` 内同载「变更清单 + 执行步骤」，只做一次合并确认；  
> 不单独产出 `change-list.md` 的独立审批、不产出 `tickets.md` / `architecture-audit.md`（见 `tier.json`）。

### 阶段 4 — TDD 落地

> 任务级契约见 `references/task-breakdown.md` 阶段 4（4.1~4.4）。

- 读 `config/mobile-tdd.json` 定测试栈与 seam 深度；细则读 `references/ios-tdd.md` / `android-tdd.md`。
- 用 Skill 工具点名 `tdd`（red→green 循环）、`implement`（按 spec/ticket 实现）、`prototype`（状态模型拿不准时先跑丢代码原型）。
- **改代码 = 回写文档**：实现中每改一处代码，按 `references/code-doc-sync.md` 第 2 节映射表回写对应文档章节，  
  不允许只改代码不改文档。这一条是硬纪律。
- 🔒 **闸门 d**：实现符合预期确认后，才进编译/测试闸门。

### 阶段 5 — 编译 · 测试 · 审查 · 交付

> 任务级契约见 `references/task-breakdown.md` 阶段 5（5.1~5.3）。

- **硬门槛**：两端分别编译通过；iOS 探测 `.xcworkspace/.xcodeproj`+scheme+destination（可参考 `iherefor-html-otherui` 的 `references/ios-environment.md`），Android 用 `./gradlew test`。
- 用 Skill 工具点名 `code-review`：Standards × Spec 双轴并行子 agent。
- **代码↔文档对账（交付门前必做）**：按 `references/code-doc-sync.md` 逐项核「文档宣称 ↔ 代码实现」，  
  产出 `05-交付/一致性对账.md`；漂移项要么回写文档、要么回退代码，**不允许带漂移交付**。
- 产出交付报告。

#### code-review 的前提与降级（实测坑，必读）

`code-review` 依赖 `git diff <fixed-point>...HEAD`，**需要 git 历史与可解析的 diff 基线**。以下场景不适用，应降级：

1. **绿地工程（无 commit 基线 / 全新未 git 跟踪的目录）**：`git rev-parse` 无基线、diff 为空。→ 降级为**轻量 Standards 轴人工审查**（直接读领域代码，按 Fowler 代码味道 + 本 skill 的移动端约定评估），不做 Spec 轴（spec 即 shared-layer.md，作者本人刚实现，偏离自查即可）。
2. **共享大仓库 + 不属本功能的改动混杂**（如上层仓库里夹着别的 skill 的 testUIProject 改动）：commit 会污染他人仓库。→ 不做 git commit，直接人工审查。
3. **绿地小代码 + 作者本人刚 TDD 写完**：code-review 边际价值低。→ 可跳过，但必须在交付报告里说明"跳过 code-review 及原因"。

**降级不是省略**：降级时仍要列出发现的问题（若有一并写进交付报告），只是不依赖 git diff 与双子 agent。判断是否降级由编排器看场景决定，并向用户说明。

### 阶段 6 — 反馈闭环

- 编译失败 / 测试失败 / 任一闸门驳回 → **回到对应阶段重跑**，不要从头来。

## 与已有 skill 的点名契约

| 阶段 | 点名 skill                                            | 触发时机                                                |
| -- | --------------------------------------------------- | --------------------------------------------------- |
| 0  | `install-local-skill` / `setup-matt-pocock-skills`  | 依赖核对 + 安装                                           |
| 1  | `grilling` / `to-questionnaire` / `domain-modeling` | 需求模糊→grill；知识在他人→questionnaire；术语固化→domain-modeling |
| 2  | `research` + `codebase-design`(DESIGN-IT-TWICE)     | 白名单搜事实 → 并出多案                                       |
| 3  | `improve-codebase-architecture` / `to-tickets`      | 既有工程先审计 / 拆 tickets（c2 前）                           |
| 4  | `tdd` / `implement` / `prototype`                   | red→green 循环                                        |
| 5  | `code-review`                                       | Standards+Spec 双轴                                   |
| 换手 | `handoff`                                           | 上下文压缩/多 session                                     |

> 只点名、不复制。被点名 skill 缺失时，走「阶段 0」安装流程（`install-local-skill`），而非内联其规则。

## 参考文件索引（按需读取，勿凭记忆）

- `references/constitution.md` — **全局工程约束层（Constitution）**，阶段 0 必读；承载原则，可配置值以 config/ 为准
- `references/task-breakdown.md` — **五层任务级拆解**（每任务的目标/输入/产出物/可机检 DoD/点名 skill），阶段开始时必读
- `templates/README.md` — **文档模板体系总则**（分类目录 + 每个产物模板清单 + 校验规则）
- `templates/` — 每个阶段产物的 `.md` 模板，生成产物时照模板填空
- `config/dependencies.json` — 被点名 skill 依赖清单（必需/可选 + 负责阶段），阶段 0 开始前必读
- `config/tier.json` — **功能分级定义**（full/lite 判据 + 闸门收缩 + 可跳过产物），阶段 0 判定分级时必读
- `config/trusted-sources.json` — web 可信源白名单（L1 官方 / L2 教学站 / L3 社区佐证），搜索前必读
- `config/mobile-tdd.json` — 移动端测试栈 + seam 深度默认值（可覆盖），阶段 4 前必读
- `references/ios-tdd.md` — iOS XCTest / Swift Testing 的 seam 与测试约定
- `references/android-tdd.md` — Android JUnit / MockK / Turbine 的 seam 与测试约定
- `references/code-doc-sync.md` — **代码 ↔ 文档同步契约**（同步点映射 + 交付门对账），实现阶段与交付门前必读
- `references/cross-platform-sharing.md` — 跨端共享层规范（需求/领域/契约如何共享、落地如何分叉）
- `references/example-project-scaffold.md` — 实例工程脚手架（xcodegen / Gradle 自举 / AndroidX 与镜像坑）
- `scripts/scan-artifacts.py` — 闭环校验器，扫描 `<工程>/docs/<feature>/` 按模板必填章节核验产物四态并出 HTML 报告（`python3 scan-artifacts.py <工程根> [--tier <full|lite>]`）
