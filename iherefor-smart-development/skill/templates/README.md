# 文档模板体系（移动端版）

> 本文档定义 `iherefor-smart-development` 的产物文档模板规范。它采用**文档驱动开发**的做法：
> 把大型开发流程拆成「固定结构的文档产物」，每个产物有明确必填章节，可被脚本机器核验——将这套
> 通用方法论适配成 **iOS / Android 移动端**语义。
> 每个阶段的每个产出物都对应 `templates/` 下的一份 `.md` 模板；模型生成产物时**照模板填空**，
> 校验器 `scripts/scan-artifacts.py` 按模板的「必填章节」核验字段齐全。

---

## 0. 文档驱动要素的映射

文档驱动开发的核心是「固定结构 + 可机检 + 双向索引」。下表给出各要素在**通用后端服务开发**与本
skill（移动端）之间的语义对应，说明本 skill 如何把结果/产物组织成可核验的文档：

| 通用要素（后端服务开发的典型产物） | 本 skill（iOS/Android 移动端） | 说明 |
|---|---|---|
| 业务目标 / 业务边界 | 业务目标 / 边界 | 保持 |
| BDD 交互流程（Given/When/Then） | **用户故事 + 验收场景**（GWT 同构） | 移动端更强调"用户可见行为" |
| 接口（路径/请求/响应/错误码） | **领域模型 + 数据契约（跨端共享）** | 移动端无 HTTP 接口，核心是领域语义 |
| 元数据（表结构/缓存 Key/枚举） | **状态模型 + 持久化契约（本地存储 schema）** | 表→本地存储/DB schema |
| 服务实现（Controller/Service/Mapper） | **模块划分 + seam 位置（可测性）** | 移动端核心是可测 seam |
| 兼容策略 | 兼容策略（平台版本/schema 迁移） | 保持 |
| 单元测试（shouldXxx 用例表） | **测试计划（should 用例 + seam/Mock/断言）** | 保持 should 命名 |
| 完成标准 | 完成标准（DoD） | 保持 |

> 结论：保留文档驱动开发的**机制**（固定结构 + 可机检 + 双向索引），**内容**换成移动端领域语义。

---

## 1. 统一目录规范（分类目录 + 入口导航）

```
docs/<feature>/
├── 00-入口/
│   └── 文档导航.md          # 唯一读取入口：读取顺序 + 冲突优先级 + 子 agent 分派口径
├── 01-需求/
│   ├── requirements.md      # 需求理清
│   ├── domain-model.md      # 领域模型（术语表 + 实体）
│   ├── user-stories.md      # 用户故事（含验收场景）
│   └── shared-requirements.md  # 跨端共享需求（两端都要时才产出）
├── 02-架构/
│   ├── search-questions.md  # 待查证技术问题清单
│   ├── facts.md             # 白名单搜索事实纪要（带一手引用）
│   ├── constraints.md       # 设计硬约束
│   ├── design-options.md    # 多套方案
│   ├── comparison.md        # 方案对比
│   ├── shared-layer.md      # 共享层（领域模型+数据契约）
│   └── proposal-draft.md    # 落地方案草案
├── 03-落地计划/
│   ├── architecture-audit.md# 既有架构审计
│   ├── change-list.md       # 变更清单
│   ├── rollback.md          # 回滚方式
│   └── tickets.md           # 任务拆分 tickets
├── 04-实现与测试/
│   ├── test-plan.md         # 测试计划（测试栈 + seam + should 用例）
│   └── (测试代码/源码在各工程目录，不在此处)
├── 05-交付/
│   ├── build-report.md      # 双端编译报告
│   ├── review-report.md     # 审查报告
│   ├── 一致性对账.md         # 代码↔文档对账（交付门槛，lite 不省略）
│   └── delivery-report.md   # 交付报告
├── 99-来源与日志/
│   ├── (原始需求/设计稿等来源材料)
│   └── run-log.jsonl        # 全程增量日志
```

`<feature>` 用功能短名（如 `subscription-tracker`），由任务 1.1 定名并初始化目录。

---

## 2. 每个模板的通用头部（所有产物文件必含）

每个产物文件头部必须声明「导航入口 + 所属阶段 + 依赖索引」，保持产物之间可互链、可追踪：

```markdown
# <产物名>

> 导航入口：`../00-入口/文档导航.md`。开发/评审先读导航，再进本文件。
> 本产物所属阶段：<阶段名>。任务编号：<X.Y>。
> 若本文件新增/修改了领域模型、数据契约、测试用例，须同步更新对应阶段产物。
```

---

## 3. 模板清单（templates/ 目录）

| 模板文件 | 对应产物 | 必填章节（校验器核验锚点） |
|---|---|---|
| `templates/01-requirements.md` | 01-需求/requirements.md | 业务目标 / 边界 / 非目标 |
| `templates/01-domain-model.md` | 域模型 | 术语表 / 实体 / 不变量 |
| `templates/01-user-stories.md` | 用户故事 | 用户故事 / 验收场景 |
| `templates/01-shared-requirements.md` | 共享需求 | 共享范围 / 分叉点 |
| `templates/02-search-questions.md` | 问题清单 | 问题清单 |
| `templates/02-facts.md` | 事实纪要 | 结论 / 来源 |
| `templates/02-constraints.md` | 设计约束 | 硬约束 / 软约束 |
| `templates/02-design-options.md` | 多案 | 方案 1 / 方案 2 / 方案 3 |
| `templates/02-comparison.md` | 对比 | 对比维度 / 推荐 |
| `templates/02-shared-layer.md` | 共享层 | 领域模型 / 数据契约 / 不变量清单 |
| `templates/02-proposal-draft.md` | 方案草案 | 变更概述 / 落地分叉 |
| `templates/03-architecture-audit.md` | 架构审计 | 摩擦点 / 风险 |
| `templates/03-change-list.md` | 变更清单 | 文件变更 / 依赖 / 签名·导航·资源变更 |
| `templates/03-rollback.md` | 回滚 | 回滚路径 |
| `templates/03-tickets.md` | tickets | Tickets（≥1 条 T-x） |
| `templates/04-test-plan.md` | 测试计划 | 测试栈 / seam 位置 / should 用例 |
| `templates/05-build-report.md` | 编译报告 | 双端 0 error / 命令 |
| `templates/05-review-report.md` | 审查报告 | 审查结论 / 降级说明 |
| `templates/05-consistency-check.md` | 一致性对账 | 同步点 / 漂移项 |
| `templates/05-delivery-report.md` | 交付报告 | 交付清单 / 回滚状态 |
| `templates/00-navigation.md` | `00-入口/文档导航.md` | 读取顺序 / 冲突优先级 / 分派口径 |

---

## 4. 校验器核验规则

`scan-artifacts.py` 对每个产物做两件事：
1. **存在性**：文件是否落在 `docs/<feature>/<分类目录>/<产物名>.md`。
2. **结构核验**：文件内是否包含该模板声明的「必填章节」关键词（上表「必填章节」列）。

四态判定：
- ✅ 已产出：文件存在 + 必填章节命中
- ⚠️ 缺字段：文件存在，但部分必填章节缺失（列出缺哪些）
- ⭕ 不判定：产物落在各工程目录（测试代码/源码），脚本无法从 docs/ 判定
- ❌ 缺失：文件不存在

> 说明：移动端场景下，阶段 4 的测试代码与源码落在各工程目录而非 docs/，校验器对这类任务标
> 「不判定」，由阶段 5.1 双端编译门兜底。

---

## 5. 功能分级（tier）与模板裁剪

`iherefor-smart-development` 按需求规模分两档，判据与闸门收缩见 `config/tier.json`。两档**共用同一套模板目录**，
不另造「lite 专用模板」——lite 档只是把部分产物标为可跳过，避免模板体系翻倍：

| 档位 | 闸门 | 模板全集 |
|---|---|---|
| **full**（标准） | a / b / c1 / c2 / d / 交付门 | 上表 20 个产物模板全套 |
| **lite**（轻量） | a / b / d / 交付门 | 跳过 6 个：`01-shared-requirements`、`02-design-options`、`02-comparison`、`02-shared-layer`、`03-architecture-audit`、`03-tickets` |

- lite 档 `proposal-draft.md` 需在模板内**同载「变更清单 + 执行步骤」**（替代独立的 change-list.md 审批与 tickets.md）。
- `scan-artifacts.py --tier lite` 对上述 6 个跳过产物标「已跳过」，不判缺失。
- 判据、可升降级规则、跳过清单的**唯一数据源**是 `config/tier.json`，本文档不另行复制判据。
