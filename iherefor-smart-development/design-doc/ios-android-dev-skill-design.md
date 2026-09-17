# iOS/Android 跨端开发 Skill —— 设计文档（定稿）

> 状态：方案已与用户逐轮对齐并确认。本文档是后续落地 skill 的唯一事实源。
> 定位：一个**编排器（orchestrator）skill**，不是自包含 skill，也不是视觉还原 skill。

---

## 0. 一句话定位

面向 iOS / Android **功能开发**（非 Lanhu 视觉还原），一个**总入口编排 skill**，在六阶段闭环的每个节点「点名」调用已有的 Matt Pocock 等 skill，四道人工闸门把关，web 可信源白名单驱动方案层，共享层贯穿两端。

---

## 1. 关键决策（已确认，勿再议）

| 编号 | 决策点 | 结论 |
|---|---|---|
| D1 | 与 `iherefor-html-otherui` 的关系 | **功能开发型（B）**。视觉还原仍走 `iherefor-html-otherui`，本 skill 处理业务逻辑+架构+测试 |
| D2 | 端覆盖 | **可一端、可两端**；两端时「共享需求+架构、落地分叉」 |
| D3 | web 搜索定位 | **输入/事实层**，与「多套方案」是**前后关系**；每轮方案设计前都跑一次 |
| D4 | 可信源 | **白名单配置化**（官方文档+高质量教学站，按平台/主题分级），不是散在 prompt 里 |
| D5 | 人工审核闸门 | **a / b / c / d 四道全卡** |
| D6 | 共享层 | 跨端共享「需求 / 领域模型 / 模块划分 / 数据契约」，仅落地层分叉 |
| D7 | skill 形态 | **编排器**，通过 Skill 工具点名调用已有 skill，不复制规则 |
| D8 | TDD 约定 | **合理默认 + 可配置** |
| D9 | 安装位置 | **用户级** `~/.workbuddy-ai/skills/` |
| D10 | 前置依赖 | **阶段 0 硬闸**：被点名 skill 缺失先经 `install-local-skill` 装（作者核对+安全审计），不内联绕过 |

---

## 2. 六阶段闭环（骨架）

```
[0 前置依赖检查] ──▶ [1 需求理清] ──🔒a──▶ [2 架构设计] ──🔒b(最重)──▶ [3 工程落地计划] ──🔒c──▶ [4 TDD 落地] ──🔒d──▶ [5 编译·测试·审查·交付] ──▶ [6 反馈闭环 → 回跳]
                          ▲                                    ▲
                    web白名单→research→design-it-twice      共享层贯穿 1~4
```

### 阶段 0 — 前置依赖检查（硬闸）

> 编排器缺什么 skill 必须先装好，否则闭环第一脚就踏空。

- 读 `config/dependencies.json`（required / optional 两类 + 各负责的阶段）。
- 逐个检查被点名 skill 是否已安装；**required 缺失 → 暂停，先走 `install-local-skill` 安装**（含作者核对、安全审计、批量安装、验证），默认用户级。
- 绝不「内联缺失 skill 的规则」来绕过；Matt Pocock 整套可批量装齐后跑 `setup-matt-pocock-skills` 生成项目侧 `docs/agents/*.md` / `CONTEXT.md` / `docs/adr/`。
- optional 缺失不阻塞，到该阶段前仍缺则明确告知「跳过/降级」，不静默。

### 阶段 1 — 需求理清
- **点名**：`grilling`（追问到共享理解）、`to-questionnaire`（跨角色拉缺口）、`domain-modeling`（沉淀领域术语进 CONTEXT.md）
- **产出**：确认后的需求 + 领域模型 + 用户故事
- 🔒 **闸门 a**：确认「需求理解正确」→ 轻量确认

### 阶段 2 — 架构设计（本 skill 的增值核心）
- **第 1 步 · web 白名单搜索**：派 `research` 子 agent，**约束在 D4 白名单内**搜「该功能在 iOS/Android 的最佳实践/官方推荐写法」，产出一份带「一手来源引用」的事实纪要
- **第 2 步 · 多套方案并行**：基于事实纪要，用 `codebase-design` 的 **DESIGN-IT-TWICE** 模式派 3+ 子 agent 各出一套**截然不同**的接口/模块设计，再对比择优（按 depth / locality / seam placement）
- **跨端共享层**：两端都要时，先定共享层（领域模型、数据契约），再各自设计落地层
- 🔒 **闸门 b（最重）**：方案/落地方案草案**必须人工确认**，不通过回到本阶段重搜/重设计

### 阶段 3 — 工程落地计划
- **点名**：`improve-codebase-architecture`（扫描既有架构摩擦）、结合 `research` 审计现有工程
- **产出**：变更清单（要动哪些文件、加哪些依赖、改哪些签名/导航/资源、回滚方式）
- 🔒 **闸门 c**：变更清单**批准后才能写生产代码**（动既有工程是高风险操作）

### 阶段 4 — TDD 落地
- **点名**：`tdd`（red→green）、`implement`（按 spec/ticket 实现）、`prototype`（状态模型拿不准时先跑丢代码原型）
- **本 skill 内置「移动端 TDD 约定」**（见 §4）
- 🔒 **闸门 d**：实现符合预期确认 → 进编译/测试闸门

### 阶段 5 — 编译 · 测试 · 审查 · 交付
- **硬门槛**：iOS（Xcode）与 Android（Gradle）**分别编译通过**，不能一端推断另一端
- **点名**：`code-review`（Standards × Spec 双轴并行子 agent）
- **产物**：交付报告

### 阶段 6 — 反馈闭环
- 编译/测试/任一闸门不通过 → **回到对应阶段重跑**（不是从头来）

---

## 3. 与已有 skill 的「点名」契约

| 阶段 | 点名 skill | 何时/如何触发 |
|---|---|---|
| 1 | `grilling` / `to-questionnaire` / `domain-modeling` | 需求模糊→grill；知识在他人→questionnaire；术语固化→domain-modeling |
| 2 | `research` + `codebase-design`(DESIGN-IT-TWICE) | 白名单搜事实→并出多案 |
| 3 | `improve-codebase-architecture` | 既有工程先审计 |
| 4 | `tdd` / `implement` / `prototype` | 循环 red→green |
| 5 | `code-review` | Standards+Spec 双轴 |
| 换手 | `handoff` | 上下文压缩/多 session 时 |

> 编排器只做「路由 + 闸门把关 + 状态管理」，不复制任何被点名 skill 的规则正文。被点名 skill 的规则以其自身 SKILL.md 为准。

---

## 4. 移动端 TDD 约定（内置默认，可配置）

**分两档，不一刀切：**

| 层 | 是否默认必测 | 说明 |
|---|---|---|
| 领域层 / 用例 / ViewModel | **必测** | seam 测在公开接口，mock 外部依赖 |
| Repository / 数据映射 | 视情况 | 有真实数据源的逻辑必测 |
| UI 层 | 默认不测 / 视情况 | 默认跳过快照与 UI test，除非需求明确要求 |

**iOS 默认栈**：XCTest（优先 Swift Testing）、测领域/ViewModel 层、`xcodebuild test -workspace <w> -scheme <s> -destination <d>`
**Android 默认栈**：JUnit + MockK + Turbine（Flow）、测 ViewModel/Repository、`./gradlew test`
**贯穿原则**（继承自 `tdd` skill）：只测外部行为不测实现细节；seam 预确认；red 先于 green；垂直切片不水平铺开。

> 所有默认值可在 skill 根 `config/` 下覆盖（用户自己的团队测试规范 → D8-B，可整体替换）。

---

## 5. Web 可信源白名单（D4 落地）

做成 skill 内**持久化配置** `config/trusted-sources.json`，按「平台 × 等级」分级：

- **L1 官方权威**（只读事实来源）：Apple Developer、developer.android.com、Kotlin 官方、Swift.org、Jetpack 官方
- **L2 高质量教学站**（一手教程）：Hacking with Swift、Swift by Sundell、Ray Wenderlich / Kodeco、Antonio Leiva（Kotlin）、Philipp Lackner
- **L3 社区参考**（仅交叉佐证，不作决策依据）：Stack Overflow、GitHub issue、官方博客之外的二手帖

**硬约束**：子 agent 的 web 搜索**必须约束在 L1+L2**；结论必须附「一手来源引用」；L3 只允许用于查 bug 反例，禁止作为架构决策依据。

---

## 6. 目录结构（拟）

```
~/.workbuddy-ai/skills/iherefor-smart-development/
├── SKILL.md                      # 编排器主流程 + 闸门判据 + 点名契约 + 阶段 0 依赖检查
├── config/
│   ├── dependencies.json         # 被点名 skill 依赖清单（required/optional + 负责阶段）
│   ├── trusted-sources.json      # web 白名单（L1/L2/L3 分级）
│   └── mobile-tdd.json           # 移动端测试栈默认值（可覆盖）
└── references/
    ├── ios-tdd.md                # iOS XCTest/Swift Testing seam 约定
    ├── android-tdd.md            # Android JUnit/MockK/Robolectric 约定
    └── cross-platform-sharing.md # 跨端共享层规范（需求/领域/契约如何共享、落地如何分叉）
```

---

## 7. 命名（待最终确认）

目录名建议 `ios-android-dev`（或 `mobile-dev-orchestrator`）。触发词覆盖：iOS 开发、安卓开发、Android 开发、移动端功能开发、跨端开发等。

---

## 8. 待办（落地顺序）

1. ~~确认本文档 + 命名~~ → 已定名 `iherefor-smart-development`
2. ~~SKILL.md 骨架~~ → 已写（含阶段 0 前置依赖检查）
3. ~~白名单 config~~ → 已写 `config/trusted-sources.json`
4. ~~依赖清单 config~~ → 已写 `config/dependencies.json`
5. ~~ios/android TDD references~~ → 已写
6. ~~共享层 spec~~ → 已写
7. 装到用户级 → 已装入 `~/.workbuddy-ai/skills/iherefor-smart-development/`
8. 端到端拿一个真实功能验证闭环（未做）
