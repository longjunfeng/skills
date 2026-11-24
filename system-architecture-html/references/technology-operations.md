# 技术选型与部署运维设计规范

创建、修改或验收“技术选型与部署运维”区域时完整读取本规范。该区域用于说明系统如何实现、如何部署以及如何长期运行，不得只罗列产品名称。

## 1. 页面结构

主页面使用稳定区域 ID `technology-operations`，建议紧随整体架构图。区域内部至少包含三组设计表：

1. 技术选型
2. 部署设计
3. 运维设计

使用简洁、响应式 Table 展示；表格上方可以提供分类筛选。点击或键盘触发表格行时打开详情抽屉，展示完整依据、备选方案、风险和关联模块。

## 2. 技术选型

从需求、代码和约束中识别实际需要的类别。常见类别包括：

- 编程语言与版本
- 前端、后端和客户端框架
- 架构风格：分层、六边形、事件驱动、微服务、模块化单体等
- 设计模式：DDD、CQRS、Saga、Outbox、Adapter、Strategy 等
- API、消息与集成协议
- 数据库、缓存、搜索、对象存储和消息系统
- 工作流、任务调度、规则引擎和 Agent Runtime
- 安全、身份、密钥、策略和审计组件
- 测试、构建、依赖管理和质量工具

每个选型项至少包含：

```javascript
{
  id: "tech-backend-language",
  category: "后端语言",
  name: "Java",
  version: "21",
  purpose: "承载控制面和领域服务",
  rationale: "与现有代码和组织能力一致",
  alternatives: ["Kotlin", "Go"],
  constraints: ["必须兼容现有 JVM 公共组件"],
  moduleIds: ["module-control-plane"],
  status: "fact | decision | suggestion | pending | poc",
  sourceRefs: ["source-code-build"]
}
```

不得仅写“使用 Java”而不说明用途、版本、选择理由和适用模块。输入未明确版本时标记待确认，不猜测版本号。

## 3. 部署设计

部署设计至少覆盖：

- 部署模式：单机、集群、容器、Kubernetes、Serverless、边缘或混合部署
- 环境分层：开发、测试、预发布、生产和灾备
- 拓扑与计算单元：服务、Worker、Sidecar、Job、Pod、节点池和可用区
- 网络边界：入口、出口、服务间通信、内外网、零信任和防火墙
- 数据部署：主从、多副本、分片、备份、跨区复制和数据驻留
- 配置与密钥：配置中心、Secret Manager、轮换和环境隔离
- 发布策略：滚动、蓝绿、金丝雀、Feature Flag、回滚和数据库迁移
- 弹性与容量：水平扩缩、垂直扩缩、队列削峰、限流和容量基线

每个部署项至少包含：

```javascript
{
  id: "deploy-runtime-cluster",
  category: "运行环境",
  name: "Kubernetes 多可用区集群",
  environment: "production",
  topology: "Gateway + Control Plane + Worker Pool",
  strategy: "滚动发布；高风险组件使用金丝雀",
  availability: "跨可用区副本",
  scaling: "基于队列深度和 CPU 水平扩缩",
  recovery: "失败自动回滚，状态服务按恢复目标切换",
  moduleIds: [],
  status: "decision",
  sourceRefs: []
}
```

架构图表达逻辑模块，部署设计表达运行拓扑；不要把 Pod、节点或云产品强行混入业务模块层级。

## 4. 运维设计

运维设计至少覆盖：

- 责任模式：开发自运维、平台托管、SRE、值班与职责边界
- 可观测性：指标、日志、Trace、审计和业务事件
- SLI/SLO/SLA：可用性、延迟、错误率、吞吐、恢复时间和数据恢复点
- 告警：分级、聚合、抑制、升级和通知渠道
- 事件响应：发现、止损、恢复、复盘和行动项
- 变更管理：发布审批、自动验证、回滚和变更审计
- 备份灾备：备份频率、恢复演练、RTO、RPO 和跨区域策略
- 容量与成本：容量预测、配额、成本归集、预算和异常检测
- 安全运维：漏洞、补丁、密钥轮换、权限复核和合规证据
- Runbook：常见故障、诊断步骤、自动化处置和人工升级

每个运维项至少包含：

```javascript
{
  id: "ops-observability",
  category: "可观测性",
  name: "统一 Metrics / Logs / Traces",
  objective: "从 Goal 到工具调用保持同一 traceId",
  indicators: ["availability", "p95 latency", "error rate"],
  tooling: ["OpenTelemetry"],
  alerting: "按服务影响等级分级告警",
  runbook: "runbooks/observability.md",
  owner: "平台 SRE",
  moduleIds: [],
  status: "decision",
  sourceRefs: []
}
```

未明确的 SLO、RTO、RPO、保留期、值班责任和预算阈值必须进入待确认事项，不得使用看似合理的虚构数字。

## 5. 统一数据与追溯

在 `architecture-data.js` 顶层使用：

```javascript
technologySelections: [],
deploymentDesign: [],
operationsDesign: []
```

三类记录都使用稳定 ID，并通过 `moduleIds`、`tableIds`、`apiOperationIds`、`riskIds` 和 `sourceRefs` 关联其他设计元素。页面统计、筛选、详情和 Hash 均从这些数据生成。

## 6. 表格视觉规范

- 使用 `.design-table-wrap` 包裹 `.design-table`，横向滚动只能发生在该容器内。
- 表头使用低饱和背景和粘性定位；行高保持紧凑但可读。
- 第一列保持名称或类别，禁止把每个单元格做成独立卡片。
- 状态使用文字 Badge，不只用颜色。
- 行支持 `tabindex="0"`、Enter 和 Space 下钻。
- 窄屏优先保留表格语义并允许容器横向滚动；不要让页面整体横向溢出。
- 内容过长时显示一至两行摘要，完整内容进入详情抽屉。

推荐语义结构：

```html
<div class="design-table-wrap">
  <table class="design-table glossary-table">
    <thead><tr><th>领域</th><th>中文名</th><th>英文名</th><th>定义</th><th>状态</th></tr></thead>
    <tbody><!-- 由 architecture-data.js 生成 --></tbody>
  </table>
</div>
```

推荐基础样式，可合并进项目 `styles.css` 并按现有色板微调：

```css
.design-table-wrap { max-width: 100%; overflow: auto; border: 1px solid var(--line, #dfe4ec); border-radius: 14px; background: #fff; }
.design-table { width: 100%; min-width: 760px; border-collapse: separate; border-spacing: 0; }
.design-table th { position: sticky; top: 0; z-index: 1; padding: 11px 14px; border-bottom: 1px solid var(--line, #dfe4ec); background: #f6f8fb; color: #526077; font-size: 12px; text-align: left; }
.design-table td { padding: 13px 14px; border-bottom: 1px solid #edf0f4; color: #39475f; font-size: 13px; line-height: 1.55; vertical-align: top; }
.design-table tbody tr { cursor: pointer; }
.design-table tbody tr:hover, .design-table tbody tr:focus-visible { background: #f7f9ff; outline: none; }
.design-table tbody tr:last-child td { border-bottom: 0; }
.design-table .cell-name { color: #172033; font-weight: 700; white-space: nowrap; }
.design-table .cell-summary { min-width: 260px; }
```

业务名词和技术/部署/运维表复用这套基础样式，只调整列定义，不为每个区域创建一套视觉体系。

## 7. 验收

- `index.html` 包含 `technology-operations` 区域和导航入口。
- 三类数据均来自 `architecture-data.js`，HTML 不复制具体选型正文。
- 技术选型包含语言、架构风格、模式和核心组件；缺项有明确理由或待确认项。
- 部署设计包含部署模式、环境、拓扑、发布、弹性和恢复。
- 运维设计包含责任、可观测、告警、变更、备份灾备、容量成本和 Runbook。
- 所有选择说明理由、适用范围、状态和来源。
- 表格可搜索或筛选，行点击、键盘、Hash 和详情抽屉有效。
- 桌面和窄屏没有页面级横向溢出。
