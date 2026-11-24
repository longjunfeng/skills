# Excel 数据模型

## 目录

1. 总体约束
2. 工作表与表名
3. 字段定义
4. 计算规则
5. 数据一致性规则
6. ID 与日期规范

## 总体约束

- 默认工作簿名为 `project-plan.xlsx`。
- 中文工作表名面向人工，英文 snake_case 表头面向脚本、Agent 和长期兼容。
- 每个数据工作表使用 Excel Table；第 1 行是字段名，第 2 行可作为首条数据或空白预留行。
- 表头单元格使用中文批注解释字段含义。
- `进度日志` 与 `变更记录` 只追加，不覆盖或删除历史记录。
- `使用说明` 不是数据表，不参与程序解析。
- `字典` 中的枚举值是数据校验和 CLI 校验的权威来源。

## 工作表与表名

| 工作表 | Excel Table | 每行含义 | 主键 |
|---|---|---|---|
| 项目 | tbl_projects | 一个项目 | project_id |
| 任务 | tbl_tasks | 一个 WBS 任务 | task_id |
| 里程碑 | tbl_milestones | 一个里程碑 | milestone_id |
| 进度日志 | tbl_progress_log | 一次任务进度更新 | log_id |
| 风险问题 | tbl_risks | 一个风险、问题或阻塞 | item_id |
| 变更记录 | tbl_change_log | 一个字段级变更 | change_id |
| 字典 | tbl_dictionary | 一个枚举项 | dict_type + dict_code |

## 字段定义

### 项目

```text
project_id, project_name, project_description, business_owner,
project_manager, priority, project_status, health, planned_start,
planned_end, actual_start, actual_end, current_phase, overall_percent,
last_updated_at, last_updated_by, remark
```

### 任务

```text
task_id, project_id, parent_task_id, wbs_code, task_name, task_type,
phase, owner, contributors, planned_start, planned_end, baseline_start,
baseline_end, forecast_start, forecast_end, actual_start, actual_end,
effort_days, percent_complete, task_status, health, milestone_flag,
dependency_task_ids, deliverable, acceptance_criteria, blocker_flag,
schedule_variance_days, completion_weight, last_progress_date,
last_updated_at, last_updated_by, remark
```

关键规则：

- `baseline_start/baseline_end`：首次创建时等于计划日期，普通修改不得覆盖。
- `planned_start/planned_end`：当前批准计划，可通过 `task update --reason` 修改。
- `forecast_start/forecast_end`：当前预测，不改变基线。
- `percent_complete`：整数，范围为 0 到 100。
- `dependency_task_ids`：逗号分隔的任务 ID，不允许循环依赖。
- `milestone_flag` 与 `blocker_flag`：使用 `是/否`。
- `schedule_variance_days` 与 `completion_weight`：Excel 中为可审计公式；程序侧也按同一规则计算，避免依赖 Excel 公式缓存。

### 里程碑

```text
milestone_id, project_id, milestone_name, milestone_type, owner,
baseline_date, planned_date, forecast_date, actual_date, milestone_status,
acceptance_condition, related_task_ids, risk_note, last_updated_at,
last_updated_by, remark
```

### 进度日志

```text
log_id, project_id, task_id, update_date, percent_before, percent_after,
status_before, status_after, work_completed, next_steps, blockers,
evidence_link, updater, updated_at, remark
```

### 风险问题

```text
item_id, project_id, task_id, item_type, title, description, impact,
probability, severity, owner, identified_date, due_date, item_status,
mitigation, resolution, closed_date, last_updated_at, last_updated_by, remark
```

### 变更记录

```text
change_id, project_id, entity_type, entity_id, change_type, field_name,
old_value, new_value, change_reason, effective_date, changed_by,
changed_at, remark
```

### 字典

```text
dict_type, dict_code, dict_label, sort_order, enabled, description
```

内置字典：

- `project_status`：未开始、进行中、暂停、已完成、已取消
- `task_status`：未开始、进行中、已完成、延期、阻塞、取消
- `health`：正常、关注、风险
- `priority`：P0、P1、P2、P3
- `task_type`：阶段、任务、缺陷、研究、交付
- `milestone_status`：未开始、进行中、已达成、延期、取消
- `item_type`：风险、问题、阻塞
- `item_status`：开放、处理中、已解决、已关闭
- `probability`：低、中、高
- `severity`：低、中、高、严重
- `yes_no`：是、否

## 计算规则

整体完成度：

```text
Σ(percent_complete × completion_weight) / Σ(completion_weight)
```

其中取消任务不参与计算。`completion_weight` 优先使用大于 0 的 `effort_days`，否则使用 `MAX(1, planned_end - planned_start + 1)`。

计划偏差天数：

- 已完成任务：`actual_end - planned_end`。
- 未完成且有预测结束日期：`forecast_end - planned_end`。
- 未完成、无预测日期且已过期：`today - planned_end`。
- 其他情况：0。

健康度建议：

- 存在阻塞或偏差超过 5 天：风险。
- 偏差为 1 到 5 天，或存在未关闭风险：关注。
- 其他：正常。

CLI 不强制覆盖人工填写的健康度，但校验结果会给出不一致警告。

## 数据一致性规则

- 主键不可为空或重复。
- 所有外键引用必须存在。
- 父任务必须属于同一项目，且不能形成父子环。
- 依赖任务必须属于同一项目，且不能形成依赖环。
- 开始日期不得晚于对应结束日期。
- 实际结束日期存在时必须存在实际开始日期。
- `已完成` 任务的完成度必须为 100；完成度为 100 的非取消任务应为 `已完成`。
- `未开始` 任务的完成度应为 0。
- 里程碑关联任务、风险关联任务必须存在。
- 重新排期、调整依赖、调整负责人和调整范围必须留下变更记录及原因。

## ID 与日期规范

- 项目：`PRJ-YYYYMM-NNN`
- 任务：`TASK-NNN`
- 里程碑：`MS-NNN`
- 风险问题：`ITEM-NNN`
- 进度日志：`LOG-YYYYMMDD-NNN`
- 变更记录：`CHG-YYYYMMDD-NNN`
- 日期：`YYYY-MM-DD`
- 时间：ISO 8601，例如 `2026-08-05T16:30:00+08:00`
