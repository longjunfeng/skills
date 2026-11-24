---
name: system-plan-html-skill
description: 使用 Excel 作为唯一数据源创建、维护和校验项目开发计划与进度，并生成标准化静态 HTML 进度看板。用于新建项目计划工作簿、添加或修改 WBS 任务、重新排期、记录进度与阻塞、管理里程碑和风险问题、检查日期/依赖/状态一致性、生成项目总览与甘特时间线，以及为大模型、Agent 或人工提供稳定 JSON/命令行接口。
---

# 项目开发计划与进度

## 首要规则

将 Excel 工作簿视为唯一业务数据源，将 HTML 看板视为可重复生成的只读产物。不要在 HTML 中直接维护任务、进度、里程碑或风险数据。

执行写操作前完整读取 [references/excel-schema.md](references/excel-schema.md) 和 [references/tool-contracts.md](references/tool-contracts.md)。创建或修改 HTML 看板前再完整读取 [references/html-dashboard-spec.md](references/html-dashboard-spec.md)。

优先通过 `scripts/plan` 调用命令。脚本会选择带有 `openpyxl` 的 Python 运行时。直接调用时使用：

```bash
python3 scripts/plan_cli.py --help
```

如果本机 Python 没有 `openpyxl`，安装运行依赖：

```bash
python3 -m pip install -r scripts/requirements.txt
```

供 Agent 或程序调用时始终添加 `--json`，根据退出码和 `ok/errors/warnings/data` 字段判断结果，不要解析人类输出文本。

## 判断工作模式

- **创建**：工作簿不存在，或用户明确要求初始化新的计划。
- **维护**：新增任务、修改计划、重新排期、更新进度、维护里程碑或风险问题。
- **展示**：从工作簿生成或刷新 HTML 看板。
- **验收**：用户只要求检查时运行 `validate`，保持只读；不要顺便修改工作簿。

## 通用工作流

1. 确认工作簿绝对路径、项目名称、负责人和计划周期；优先从用户上下文发现，不因非关键缺省值停止工作。
2. 新建时运行 `init`，不要手工拼装工作表。
3. 维护前运行 `validate`；如果存在错误，先报告或修复与本次操作直接相关的问题。
4. 新增计划使用 `task add`；普通属性修改使用 `task update`；计划日期、依赖或范围变化必须提供 `--reason`，并保留基线与变更记录。
5. 执行进度更新时使用 `progress update`，同时更新任务摘要并追加不可覆盖的进度日志。
6. 完成写操作后再次运行 `validate`。
7. 用户需要展示、汇报或网页时运行 `dashboard build`，再通过本地静态服务器进行浏览器验收。

## 常用命令

初始化：

```bash
scripts/plan init --workbook /absolute/project-plan.xlsx \
  --project-name "数字员工平台" --owner "张三" \
  --start 2026-08-10 --end 2026-12-31
```

新增任务：

```bash
scripts/plan task add --workbook /absolute/project-plan.xlsx \
  --name "完成接口设计" --phase "技术设计" --owner "李四" \
  --start 2026-08-12 --end 2026-08-20 --effort-days 7
```

修改与重新排期：

```bash
scripts/plan task update --workbook /absolute/project-plan.xlsx \
  --task TASK-001 --end 2026-08-28 --reason "接口依赖方延期"
```

更新进度：

```bash
scripts/plan progress update --workbook /absolute/project-plan.xlsx \
  --task TASK-001 --percent 65 --status "进行中" \
  --completed "完成接口定义" --next "开始联调" --blockers "等待测试环境"
```

校验和生成看板：

```bash
scripts/plan validate --workbook /absolute/project-plan.xlsx
scripts/plan dashboard build --workbook /absolute/project-plan.xlsx --output /absolute/dashboard
```

完整参数、JSON 契约和退出码见 [references/tool-contracts.md](references/tool-contracts.md)。

## 数据维护约束

- 使用稳定 ID 引用项目、任务、里程碑和风险；不要按显示名称建立关联。
- 不覆盖 `baseline_start`、`baseline_end` 和 `baseline_date`，除非用户明确要求重新基线；重新基线也必须写入变更记录。
- 不删除历史进度和变更记录。纠错时追加新记录并说明原因。
- 任务完成度使用 `0..100` 的整数；HTML 中再转换为百分比展示。
- 多个依赖或关联任务使用逗号分隔的 ID；保存前去重并标准化。
- 完成任务时补充实际开始和结束日期；取消任务不计入整体完成度。
- 工作簿可能被其他人或 Agent 使用时，不绕过文件锁或原子保存流程。
- 不要用空白、虚假示例或未说明的 `TODO` 冒充真实项目数据。

## HTML 看板要求

从 Excel 生成 `index.html`、`styles.css`、`app.js` 和 `plan-data.js`。页面至少包含总览 KPI、阶段进度、计划时间线、里程碑、风险问题、最近动态和任务明细。

保持本地离线可用，不引用 CDN；页面不得整体横向溢出，甘特时间线可以在自身容器内滚动。交互同时支持鼠标与键盘，状态不能只通过颜色表达。详细规范见 [references/html-dashboard-spec.md](references/html-dashboard-spec.md)。

## 验收

至少执行：

```bash
scripts/plan validate --workbook /absolute/project-plan.xlsx --json
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" /absolute/path/to/system-plan-html-skill
```

生成看板后启动本地服务器，例如：

```bash
python3 -m http.server 8000 --directory /absolute/dashboard
```

检查桌面端和窄屏布局、控制台错误、筛选、搜索、详情抽屉、Hash 深链、任务时间线和键盘操作。只有实际完成浏览器检查后才报告“浏览器验收通过”。

## 资源

- [references/excel-schema.md](references/excel-schema.md)：工作表、字段、数据规则、计算规则和 ID 规范。
- [references/tool-contracts.md](references/tool-contracts.md)：CLI 命令、参数、JSON 输出、退出码和 Agent 调用规则。
- [references/html-dashboard-spec.md](references/html-dashboard-spec.md)：页面结构、设计令牌、组件、响应式和无障碍规范。
- `scripts/plan`：人类和 Agent 的统一启动入口。
- `scripts/plan_cli.py`：命令行路由与输出契约。
- `scripts/plan_store.py`：Excel 读写、校验、日志、锁和原子保存。
- `scripts/dashboard.py`：看板数据组装与静态文件生成。
- `assets/dashboard-template/`：标准化离线 HTML、CSS 和 JavaScript 模板。
- `assets/sample/project-plan.xlsx`：可直接查看和试用的样例工作簿。
