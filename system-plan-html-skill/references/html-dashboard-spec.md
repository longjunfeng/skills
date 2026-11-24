# HTML 进度看板规范

## 目录

1. 文件与数据入口
2. 页面区域
3. 指标口径
4. 交互规范
5. 视觉规范
6. 响应式与无障碍
7. 验收清单

## 文件与数据入口

生成目录必须包含：

```text
index.html
styles.css
app.js
plan-data.js
```

`plan-data.js` 只暴露一个只读入口：

```js
window.PLAN_DATA = Object.freeze({...});
```

页面不得复制第二份任务、里程碑或风险业务数据。不得引用 CDN、远程字体或外部运行时。

## 页面区域

使用稳定区域 ID：

- `overview`：整体完成度、按期任务、延期任务、里程碑达成率、开放风险问题。
- `phases`：按阶段的完成度和任务数量。
- `timeline`：任务计划、预测和实际时间线。
- `milestones`：里程碑时间轴。
- `issues`：未关闭风险、问题和阻塞。
- `updates`：最近进度与计划变更。
- `tasks`：可搜索、筛选和排序的任务明细。

任务、里程碑和风险详情使用侧边抽屉，不跳转新页面。

## 指标口径

- 整体完成度：按 `completion_weight` 加权，取消任务不参与。
- 按期任务：非取消、非延期、非阻塞且计划未逾期的任务。
- 延期任务：状态为延期，或未完成且当前日期超过计划结束日期。
- 里程碑达成率：已达成数量 / 非取消里程碑数量。
- 开放风险问题：状态不是已解决或已关闭的风险问题。
- 阶段完成度：阶段内任务按相同权重口径计算。

## 交互规范

- 顶部提供项目名称、健康度、计划周期、数据更新时间和源文件名。
- 支持按关键字、状态、负责人、阶段筛选任务。
- 支持按 WBS、日期、完成度和状态排序。
- 点击任务、里程碑或风险打开详情抽屉。
- 详情抽屉更新 URL Hash，例如 `#task-TASK-001`；刷新后恢复详情。
- Escape 关闭抽屉；Enter/Space 激活可点击行；关闭后焦点回到触发元素。
- 时间线仅在自身容器内横向滚动。
- 空数据时显示明确空状态，不生成假数据。

## 视觉规范

基础设计令牌：

```css
--color-primary: #2563eb;
--color-primary-soft: #eff6ff;
--color-success: #15803d;
--color-warning: #b45309;
--color-danger: #b91c1c;
--color-text: #172033;
--color-muted: #64748b;
--color-border: #e2e8f0;
--color-surface: #ffffff;
--color-background: #f8fafc;
--radius-card: 16px;
--shadow-card: 0 10px 30px rgba(15, 23, 42, 0.06);
```

统一组件类：

```text
.app-header .kpi-grid .kpi-card .panel .status-badge .progress-track
.timeline-grid .milestone-list .issue-list .filter-bar .task-table
.detail-drawer .empty-state .alert-panel
```

状态必须同时显示文本和颜色。绿色表示完成/正常，蓝色表示进行中，橙色表示关注，红色表示延期/阻塞/风险，灰色表示未开始，紫色表示暂停。

## 响应式与无障碍

- 页面主体最大宽度建议 1600px，使用流式边距。
- 1200px 以下 KPI 和双栏区域减少列数；760px 以下变为单栏。
- 页面本身不得产生横向滚动。
- 所有控件有可见焦点样式和可读标签。
- 颜色对比度满足常规文本可读性。
- 表格在窄屏使用内部滚动，不压缩到不可读。
- 尊重 `prefers-reduced-motion`。

## 验收清单

- 四个必需文件存在，引用均为本地相对路径。
- 浏览器控制台无错误，网络面板无外部请求。
- KPI 与任务、里程碑、风险原始数据一致。
- 搜索、筛选、排序、抽屉、Hash 和 Escape 操作可用。
- 桌面端和 390px 窄屏无整体横向溢出。
- 超宽时间线只在图表容器内滚动。
- 空数据、长文本、中文姓名和 100% 完成度显示正常。
