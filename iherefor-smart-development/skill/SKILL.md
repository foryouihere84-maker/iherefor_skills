---
name: iherefor-smart-development
description: 面向 iOS / Android 功能开发（非 Lanhu 视觉还原）的总入口编排 skill。当用户要在 iOS 或 Android（或两端）工程里做功能开发时使用——从需求理清、架构设计（web 可信源白名单搜索 + 并行多方案择优）、工程落地计划、TDD 落地，到编译·测试·审查·交付的六阶段闭环，四道人工审核闸门把关，跨端共享层贯穿。只做「路由 + 闸门 + 状态管理」，在节点上点名调用已有 skill（grilling / codebase-design / research / improve-codebase-architecture / tdd / implement / code-review / handoff 等），不复制它们的规则。
agent_created: true
disable-model-invocation: true
---

# iOS / Android 智能开发编排

面向 iOS / Android **功能开发**的总入口：一条从「需求」到「交付」的六阶段闭环，四道人工审核闸门把关，
跨端共享层贯穿两端。本 skill 是**编排器**——只负责路由、闸门判据与状态管理，在节点上**通过 Skill 工具
点名调用**已有 skill，被点名 skill 的规则以其自身 SKILL.md 为准，本 skill 不复制、不改写任何被点名 skill 的正文。

## 何时使用

- 用户要在 iOS 或 Android（或两端同时）工程里**做一个功能**（登录、分页、支付接入、列表、状态管理重构等），
  而不是「把 Lanhu 设计稿还原成 UI」。
- 用户明确说「开发 / 实现 / 做一个功能 / TDD 开发」且目标是 iOS/Android 原生工程。
- 用户说「帮我建一个实例/demo 工程」要验证本 skill 或起步 → 先读 `references/example-project-scaffold.md`。
- **若是 Lanhu 设计稿视觉还原，转交 `iherefor-html-otherui`，本 skill 不处理。**

## 硬约束（违反即停）

1. **前置依赖未就绪，不得开始**：进入六阶段闭环前，必须先跑「阶段 0 — 前置依赖检查」，
   确认被点名 skill 已安装（见 `config/dependencies.json`）；缺失先装（走 `install-local-skill`），
   未落地不得开工。依赖只有在真正的阶段才被用到的，可以推迟到该阶段前再检查，但**该阶段开始前必须已就绪**。
2. **四道闸门全卡、且卡在写生产代码之前**：闸门 a（需求）、b（方案，最重）、c（变更清单）、d（实现），
   任一道未获用户明确确认，**不得**越过进入下一阶段。
3. **web 搜索必须约束在白名单内**：读 `config/trusted-sources.json`，子 agent 只允许搜 L1（官方文档）+ L2（教学站）；
   L3（社区帖）仅用于查 bug 反例，禁止作为架构决策依据。结论必须附「一手来源引用」。
4. **跨端两端都要时，共享层先行**：先定共享层（需求 / 领域模型 / 数据契约），再各自分叉落地层。
   不得两端各自独立开发、互不引用。
5. **编译是硬门槛**：iOS（Xcode）与 Android（Gradle）**分别编译通过**，不得用一端通过推断另一端。编译 0 error 才可交付。
6. **移动端 TDD 约定**以 `config/mobile-tdd.json` 与 `references/ios-tdd.md` / `references/android-tdd.md` 为准，
   不得沿用语言无关的测试假设（如 Node/TS 生态的默认）。

## 阶段 0 — 前置依赖检查（进入闭环前的硬闸）

本 skill 是编排器，依赖一批被点名的 skill。**开始任何开发前，先核对依赖清单是否落地。**

1. 读 `config/dependencies.json`，得到「必需 / 可选」两类被点名 skill 清单，以及每个 skill 负责的阶段。
2. 逐个检查是否已安装（Skill 工具的可用 skill 列表中有该 `name`；或检查 `~/.workbuddy-ai/skills/<name>/SKILL.md` 存在）。
3. **缺失的「必需」skill → 暂停，先安装**：用 Skill 工具点名 `install-local-skill`（它能处理作者核对、安全审计、
   批量安装、端到端验证）；安装级别默认用户级。**不得内联缺失 skill 的规则来「绕过」。**
   - 属于 Matt Pocock 那套的（grilling / to-questionnaire / domain-modeling / to-spec / to-tickets / tdd /
     implement / code-review / handoff / setup-matt-pocock-skills / improve-codebase-architecture / codebase-design /
     research / prototype 等），通常整套来自同一作者仓库，可用 `install-local-skill` 的批量安装一次装齐，
     并跑 `setup-matt-pocock-skills` 在目标项目里生成 `docs/agents/*.md`、`CONTEXT.md`、`docs/adr/`。
4. **缺失的「可选」skill → 不阻塞**，但到该阶段前若仍缺，明确告知用户「此环节跳过 / 降级」，不静默。
5. 按阶段惰性检查亦可：某阶段真正开始前，其依赖必须已就绪；不必一次性装完全部。
6. 装完后**重启会话/重新加载 skill 列表**才可被识别（见 `install-local-skill` 的说明）。

## 六阶段闭环

```
[1 需求理清] --🔒a--> [2 架构设计] --🔒b(最重)--> [3 工程落地计划] --🔒c--> [4 TDD 落地] --🔒d--> [5 编译·测试·审查·交付] --> [6 反馈闭环 → 回跳]
                          ▲
                    web白名单→research→并出多案      共享层(需求/领域/契约) 贯穿 1~4
```

### 阶段 1 — 需求理清

- 用 Skill 工具点名 `grilling`：追问到共享理解；需求模糊就 grill，知识在他人手上就点名 `to-questionnaire`。
- 领域术语固化时点名 `domain-modeling`，沉淀进项目 `CONTEXT.md`。
- 产出：确认后的需求 + 领域模型 + 用户故事。
- 🔒 **闸门 a**：向用户确认「需求理解正确」，获明确 positive 回复才继续。

### 阶段 2 — 架构设计（本 skill 的增值核心）

**先搜事实、再并出多案，两步是前后关系，每轮方案设计前都要跑一次搜索。**

1. **web 白名单搜索**：点名 `research` 派子 agent，**约束在 `config/trusted-sources.json` 的 L1+L2 内**，
   搜「该功能在 iOS/Android 的最佳实践 / 官方推荐写法」，产出一份带一手来源引用的**事实纪要**。
2. **并行多案择优**：基于事实纪要，用 `codebase-design` 的 **DESIGN-IT-TWICE** 模式派 3+ 子 agent
   各出一套**截然不同**的接口/模块设计，再按 depth / locality / seam placement 对比，给出带立场的推荐（可给混合方案）。
3. **跨端共享层**：两端都要时，先在此阶段定共享层（领域模型、数据契约、模块划分），落地层才分叉。
- 🔒 **闸门 b（最重）**：落地方案草案**必须人工确认**。不通过 → 回到本阶段重搜 / 重设计，不得进入阶段 3。

### 阶段 3 — 工程落地计划

- 点名 `improve-codebase-architecture` 扫描既有架构摩擦；结合 `research` 审计现有工程（导航 / 依赖 / 资源 / 状态 / 测试）。
- 产出**变更清单**：动哪些文件、加哪些依赖、改哪些签名/导航/资源、回滚方式。
- 🔒 **闸门 c**：变更清单**批准后**才可写生产代码。动既有工程是高危操作。

### 阶段 4 — TDD 落地

- 读 `config/mobile-tdd.json` 定测试栈与 seam 深度；细则读 `references/ios-tdd.md` / `android-tdd.md`。
- 用 Skill 工具点名 `tdd`（red→green 循环）、`implement`（按 spec/ticket 实现）、`prototype`（状态模型拿不准时先跑丢代码原型）。
- 🔒 **闸门 d**：实现符合预期确认后，才进编译/测试闸门。

### 阶段 5 — 编译 · 测试 · 审查 · 交付

- **硬门槛**：两端分别编译通过；iOS 探测 `.xcworkspace/.xcodeproj`+scheme+destination（可参考 `iherefor-html-otherui` 的 `references/ios-environment.md`），Android 用 `./gradlew test`。
- 用 Skill 工具点名 `code-review`：Standards × Spec 双轴并行子 agent。
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

| 阶段 | 点名 skill | 触发时机 |
|---|---|---|
| 1 | `grilling` / `to-questionnaire` / `domain-modeling` | 需求模糊→grill；知识在他人→questionnaire；术语固化→domain-modeling |
| 2 | `research` + `codebase-design`(DESIGN-IT-TWICE) | 白名单搜事实 → 并出多案 |
| 3 | `improve-codebase-architecture` | 既有工程先审计 |
| 4 | `tdd` / `implement` / `prototype` | red→green 循环 |
| 5 | `code-review` | Standards+Spec 双轴 |
| 换手 | `handoff` | 上下文压缩/多 session |

> 只点名、不复制。被点名 skill 缺失时，走「阶段 0」安装流程（`install-local-skill`），而非内联其规则。

## 参考文件索引（按需读取，勿凭记忆）

- `config/dependencies.json` — 被点名 skill 依赖清单（必需/可选 + 负责阶段），阶段 0 开始前必读
- `config/trusted-sources.json` — web 可信源白名单（L1 官方 / L2 教学站 / L3 社区佐证），搜索前必读
- `config/mobile-tdd.json` — 移动端测试栈 + seam 深度默认值（可覆盖），阶段 4 前必读
- `references/ios-tdd.md` — iOS XCTest / Swift Testing 的 seam 与测试约定
- `references/android-tdd.md` — Android JUnit / MockK / Turbine 的 seam 与测试约定
- `references/cross-platform-sharing.md` — 跨端共享层规范（需求/领域/契约如何共享、落地如何分叉）
- `references/example-project-scaffold.md` — 实例工程脚手架（xcodegen / Gradle 自举 / AndroidX 与镜像坑）
