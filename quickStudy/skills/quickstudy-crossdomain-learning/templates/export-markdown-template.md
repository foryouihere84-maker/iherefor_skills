# 导出 Markdown 模板

# {{topic}} 学习记录

- 生成日期：{{date}}
- 生成时间：{{time}}
- 导出格式：Markdown
- topicSlug：{{topicSlug}}

## 一、知识结果

### 1. 首屏核心 6 段
{{core_card_or_not_entered_reason}}

### 2. 深挖内容
{{deep_dive_sections_or_none}}

### 3. 结论修订轨迹
{{revision_trail_or_none}}

## 二、学习过程摘要表（非全量对话）

| 序号 | 阶段 | 用户输入摘要 | 模型输出摘要 | 关键信息增量/更新 | 时间 |
|---|---|---|---|---|---|
{{interaction_table_rows_or_none}}

---

## 导出说明
- 触发词（命令式）：导出 / export / 保存学习记录（可带 json/markdown 参数）
- 导出文件名：`YYYY-MM-DD-HHMMSS-<topicSlug>-study.*`
- 本文件包含知识结果与学习过程摘要表（非全量对话）
- 无深挖时固定写“无”；无修订轨迹时固定写“无”；无摘要表行时固定写“无”
