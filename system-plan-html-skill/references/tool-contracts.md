# CLI 与 Agent 调用契约

## 目录

1. 调用方式
2. 通用输出
3. 命令清单
4. 写入语义
5. 退出码
6. Agent 使用建议

## 调用方式

从 Skill 根目录运行：

```bash
scripts/plan [--json] <command> ...
```

也可以直接运行：

```bash
python3 scripts/plan_cli.py [--json] <command> ...
```

运行依赖为 Python 3.10+ 和 `openpyxl`。缺少依赖时执行：

```bash
python3 -m pip install -r scripts/requirements.txt
```

可以通过 `PLAN_PYTHON=/absolute/python` 为启动脚本指定 Python 解释器。

`--json` 可以放在子命令前或最后。路径建议始终使用绝对路径。

## 通用输出

机器输出固定为一个 JSON 对象：

```json
{
  "ok": true,
  "action": "task.add",
  "workbook": "/absolute/project-plan.xlsx",
  "timestamp": "2026-08-05T16:30:00+08:00",
  "data": {},
  "warnings": [],
  "errors": []
}
```

失败时 `ok=false`，`errors` 至少包含一个对象：

```json
{
  "code": "TASK_NOT_FOUND",
  "message": "任务 TASK-999 不存在",
  "field": "task_id"
}
```

## 命令清单

### 初始化

```bash
scripts/plan init --workbook PATH --project-name NAME --owner OWNER \
  --start YYYY-MM-DD --end YYYY-MM-DD \
  [--project-id ID] [--business-owner NAME] [--priority P1] [--force]
```

`--force` 仅允许覆盖由本工具创建、且用户明确指定的目标文件。默认拒绝覆盖。

### 查看项目

```bash
scripts/plan project show --workbook PATH [--project ID]
```

### 新增任务

```bash
scripts/plan task add --workbook PATH --name NAME --owner OWNER \
  --start DATE --end DATE [--project ID] [--parent ID] [--wbs CODE] \
  [--type TYPE] [--phase PHASE] [--contributors TEXT] [--effort-days N] \
  [--dependencies ID,ID] [--deliverable TEXT] [--acceptance TEXT] \
  [--milestone] [--updated-by NAME]
```

### 修改任务

```bash
scripts/plan task update --workbook PATH --task ID \
  [--name NAME] [--owner OWNER] [--parent ID] [--phase PHASE] \
  [--start DATE] [--end DATE] [--forecast-start DATE] [--forecast-end DATE] \
  [--effort-days N] [--dependencies ID,ID] [--deliverable TEXT] \
  [--acceptance TEXT] [--health VALUE] [--remark TEXT] \
  [--reason TEXT] [--updated-by NAME]
```

修改计划日期、父任务、依赖、工作量、交付物或验收标准时必须提供 `--reason`。

### 任务列表

```bash
scripts/plan task list --workbook PATH [--project ID] [--status VALUE] \
  [--owner NAME] [--phase PHASE]
```

### 更新进度

```bash
scripts/plan progress update --workbook PATH --task ID --percent 0..100 \
  [--status VALUE] [--date DATE] [--completed TEXT] [--next TEXT] \
  [--blockers TEXT] [--clear-blocker] [--evidence URL_OR_PATH] [--actual-start DATE] \
  [--actual-end DATE] [--updater NAME] [--remark TEXT]
```

如果未提供状态，工具按完成度推断：0 为未开始，1..99 为进行中，100 为已完成；填写阻塞时自动将 `blocker_flag` 设为“是”，但不会强制把状态改为阻塞；问题解决后使用 `--clear-blocker` 清除阻塞标记。

### 里程碑

```bash
scripts/plan milestone add --workbook PATH --name NAME --date DATE \
  [--project ID] [--owner NAME] [--type TYPE] [--tasks ID,ID] \
  [--acceptance TEXT] [--updated-by NAME]

scripts/plan milestone update --workbook PATH --milestone ID \
  [--date DATE] [--forecast-date DATE] [--actual-date DATE] \
  [--status VALUE] [--owner NAME] [--risk-note TEXT] \
  [--reason TEXT] [--updated-by NAME]
```

### 风险、问题和阻塞

```bash
scripts/plan issue add --workbook PATH --type VALUE --title TEXT \
  --severity VALUE --owner NAME [--project ID] [--task ID] \
  [--description TEXT] [--impact TEXT] [--probability VALUE] \
  [--due-date DATE] [--mitigation TEXT] [--updated-by NAME]

scripts/plan issue update --workbook PATH --issue ID \
  [--status VALUE] [--owner NAME] [--severity VALUE] [--due-date DATE] \
  [--mitigation TEXT] [--resolution TEXT] [--reason TEXT] [--updated-by NAME]

scripts/plan issue close --workbook PATH --issue ID --resolution TEXT \
  [--date DATE] [--updated-by NAME]
```

### 校验

```bash
scripts/plan validate --workbook PATH [--strict]
```

普通模式下警告不导致失败；`--strict` 下警告也返回非零退出码。

### 生成看板

```bash
scripts/plan dashboard build --workbook PATH --output DIR \
  [--title TEXT] [--project ID]
```

输出 `index.html`、`styles.css`、`app.js`、`plan-data.js`。重复执行时只覆盖这四个生成文件，不删除目录中的其他内容。

## 写入语义

- 写命令先获取同目录锁文件 `<workbook>.lock`。
- 数据在内存中完成校验后保存到临时文件，再原子替换目标工作簿。
- 正常结束或异常退出时释放锁；陈旧锁不会自动破坏数据文件。
- 每个字段级计划修改都追加一条 `变更记录`。
- 每次进度更新都追加一条 `进度日志`。
- 普通修改不会改变基线字段。

## 退出码

| 退出码 | 含义 |
|---|---|
| 0 | 成功，或普通校验仅有警告 |
| 1 | 运行时错误、文件损坏或依赖不可用 |
| 2 | 参数、业务规则或校验错误 |
| 3 | 文件锁冲突 |

## Agent 使用建议

1. 先运行 `validate --json`。
2. 使用结构化命令修改，不要直接操作单元格。
3. 检查进程退出码，再解析 JSON。
4. 写操作后再次运行 `validate --json`。
5. 只有用户需要浏览或汇报时生成 HTML。
6. 不要根据自然语言输出判断任务 ID；从 `data.task_id` 等固定字段读取。
