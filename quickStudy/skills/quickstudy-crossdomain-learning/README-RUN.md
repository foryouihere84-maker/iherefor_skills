# quickStudy Skill 运行入口说明

## 1. 目标

运行跨领域速学 Skill，满足：

- 先判意图（了解知识 / 解决问题）
- 知识分支输出首屏固定 6 段
- 深挖双入口（编号 + 自然语言，仅知识分支）
- 争议显式标注不确定性
- 支持导出知识结果 + 学习过程摘要表（表格）

## 2. 仓库边界（重要）

本仓库当前仅提供 Skill 合同与模板资产，不包含统一 runner 代码。

- 已提供：`SKILL.md`、templates、checklists、examples、design spec
- 未提供：可直接执行的通用 skill loader/host runtime

因此：

- 静态一致性检查可在本仓库完成
- 交互行为验证需在外部宿主 runner 中执行

## 3. 前置条件

- 可加载 [SKILL.md](./SKILL.md) 的宿主环境
- 模板目录可读：`templates/`
- 导出目录可写：`exports/`

## 4. 启动入口

### 4.1 Skill 文件路径

- `quickStudy/skills/quickstudy-crossdomain-learning/SKILL.md`

### 4.2 宿主命令占位

```bash
<your-skill-runner> --skill quickStudy/skills/quickstudy-crossdomain-learning/SKILL.md
```

说明：命令需替换为你实际宿主 runner。

## 5. 触发门控（核心）

收到用户输入后，先判意图：

- 了解知识：触发知识流（澄清 -> 6 段 -> 深挖 -> 导出）
- 解决问题：不触发 6 段，走问题求解流（目标 -> 约束 -> 最小可执行步骤 -> 风险与回滚点）
- 意图不明确：在 `clarificationBudget = 1` 预算内先问 1 个澄清问题

预算耗尽后，必须带假设继续，不再追问。

## 6. 交互入口

### 6.1 首轮输入示例

- 知识理解：`零信任架构`
- 问题求解：`Redis 一直超时，怎么处理？`
- 输入不足：`数学`

### 6.2 深挖入口（仅知识分支）

- 编号：`1`~`5`
- 自然语言：例如 `给我反例场景`

问题求解分支不展示 `1`~`5` 知识菜单。

## 7. 导出入口

### 7.1 命令式触发词

仅命令式输入触发导出：

- `导出`
- `export`
- `保存学习记录`
- 可选格式参数：`导出 json` / `export json` / `导出 markdown`

语义提及不触发（例：`解释 export 这个词`）。

### 7.2 输出路径

- 默认 Markdown：`exports/YYYY-MM-DD-HHMMSS-<topicSlug>-study.md`
- 可选 JSON：`exports/YYYY-MM-DD-HHMMSS-<topicSlug>-study.json`
- 导出行为：始终写 `.md`；若输入 `导出 json` / `export json`，额外同时写 `.json`

### 7.3 topicSlug 规则

从原始 `topic` 生成路径安全 `topicSlug`：

1. 小写化
2. 空白/分隔符替换为 `-`
3. 仅保留 `[a-z0-9-]`
4. 压缩连续 `-` 并去首尾 `-`
5. 长度上限 48
6. 为空时兜底固定字面量 `untitled`（不是原始 `topic` 文本）

示例：

- `Redis 超时 / 连接池?` -> `redis`
- `Zero Trust Architecture` -> `zero-trust-architecture`

### 7.4 导出内容要求

导出内容必须包含：

1. 知识结果（首屏 + 深挖 + 修订轨迹）
2. 学习过程摘要表（表格，非全量对话）

模板对应关系：
- Markdown：`templates/export-markdown-template.md`
- JSON：`templates/export-json-template.md`

## 8. 验证方式

### 8.1 静态一致性检查（本仓库可执行）

1. 检查 `SKILL.md` 是否定义：
   - `clarificationBudget`
   - 分支收口差异（knowledge vs problem_solving）
   - 命令式导出触发
   - `topicSlug` 规则
2. 检查 spec/README/templates/examples/checklists 与 `SKILL.md` 不冲突。

### 8.2 交互冒烟验证（需宿主 runner）

1. 输入 `零信任架构`：应输出完整 6 段 + 深挖菜单。
2. 输入 `2`：应进入“详细案例拆解”。
3. 输入 `Redis 一直超时，怎么处理？`：应走问题求解流，不输出 6 段与知识菜单。
4. 输入 `解释 export 这个词`：不触发导出。
5. 输入 `导出 json`：应导出 JSON 与 Markdown，文件名使用 `HHMMSS + topicSlug`，且导出交互部分为摘要表。
