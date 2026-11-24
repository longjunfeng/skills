# 推荐统一数据模型

此模型用于新建设计，重点是跨页面复用与可追溯性。修改已有设计时优先兼容现有数据结构，不要为了套用本模型而进行无收益重写。

## 目录

- 顶层结构与通用字段
- 来源记录与关系约束
- 页面消费原则
- 流程图结构
- 时序图结构

## 顶层结构

```javascript
window.ARCHITECTURE_DATA = Object.freeze({
  meta: {
    openapiUrl: "./openapi.json"
  },
  sources: [],
  layers: [],
  modules: [],
  features: [],
  edges: [],
  flows: [],
  sequences: [],
  tables: [],
  tableRelations: [],
  technologySelections: [],
  deploymentDesign: [],
  operationsDesign: [],
  glossary: [],
  decisions: [],
  risks: [],
  confirmations: [],
  pocItems: []
});
```

HTTP API 的参数、请求体、响应、错误码、鉴权与 Schema 只维护在 `openapi.json` 中，不再使用顶层 `apis` 数组复制契约。架构对象通过稳定 `operationId` 关联，例如 `apiOperationIds: ["api-submit-order"]`。

## 通用字段

每个设计元素至少提供：

```javascript
{
  id: "module-example",
  name: "示例模块",
  type: "module",
  summary: "简述",
  description: "详细说明",
  status: "fact | decision | suggestion | pending | poc",
  sourceRefs: ["source-requirement-01"],
  relatedIds: ["api-example", "table-example"],
  pending: false
}
```

`sourceRefs` 指向 `sources` 中稳定的证据记录。关联字段保存 ID，不保存用于连接的显示名称。

## 来源记录

```javascript
{
  id: "source-requirement-01",
  kind: "user | requirement | design | code | diagram | inference",
  path: "/absolute/or/project/relative/path",
  locator: "章节、符号或代码行",
  note: "该来源支持什么结论"
}
```

## 关系约束

- `layers[].moduleIds` 与 `modules[].layerId` 相互一致。
- `modules[].apiOperationIds`、`tableIds`、`flowIds`、`sequenceIds` 均能解析到真实对象。
- `edges[].sourceId` 和 `targetId` 必须存在。
- `flows[].nodes[].moduleId`、`apiOperationIds`、`tableIds` 必须存在。
- `flows[].edges[].sourceId` 和 `targetId` 必须指向同一流程中的真实节点，且每条流程边具有稳定 ID。
- `sequences[].participants[]` 必须具有稳定 ID；参与者的 `refId` 在存在时必须指向真实参与者、外部系统、模块或数据存储。
- `sequences[].messages[].sourceId`、`targetId` 必须指向同一时序图中的参与者，`apiOperationId` 在存在时必须指向 `openapi.json` 中真实 Operation，且每条消息具有稳定 ID。
- `tableRelations[].sourceTableId` 和 `targetTableId` 必须存在。
- `technologySelections[]`、`deploymentDesign[]`、`operationsDesign[]` 使用稳定 ID，`moduleIds`、`tableIds`、`riskIds` 和 `sourceRefs` 必须指向真实对象。
- 模块、功能、流程节点和时序消息中的 `apiOperationId` 或 `apiOperationIds` 必须能解析到 `openapi.json` 中唯一的 Operation。
- OpenAPI Operation 的 `x-architecture.layerId`、`moduleId`、`featureId`、`tableIds`、`flowIds` 和 `sequenceIds` 必须能解析到统一架构数据中的真实对象。
- 删除对象时同步清理或迁移所有反向引用。

## 页面消费原则

- `index.html` 加载 `architecture-data.js`；需要展示 API 摘要时读取 `meta.openapiUrl` 指向的同一个 `openapi.json`。
- `api.html` 使用本地 Swagger UI 和 `openapi-runtime.js` 加载 `openapi.json`，无需加载 `architecture-data.js`。
- HTML 只保留语义容器和降级说明，不复制具体接口、表或模块数据；API 契约正文只存在于 `openapi.json`。
- 搜索索引、节点详情、Tooltip、统计数字和导航计数均从统一数据生成。
- `technology-operations` 区域从 `technologySelections`、`deploymentDesign`、`operationsDesign` 生成三组响应式表格，不在 HTML 中复制选型正文。
- `glossary` 区域使用 `.design-table-wrap` 包裹 `.design-table.glossary-table`，行点击与键盘操作继续使用稳定 `term-` ID 下钻。
- Hash 使用元素稳定 ID；显示名称变化不应破坏深链。
- Mermaid 流程图由 `flows[].nodes` 与 `flows[].edges` 按数组顺序生成；渲染后边绑定顺序必须与 `edges` 一致。
- Mermaid 时序图由 `sequences[].participants` 与 `sequences[].messages` 按数组顺序生成；渲染后消息绑定顺序必须与 `messages` 一致。
- Cytoscape.js 架构图直接消费 `layers`、`modules` 和 `edges`；层 ID 作为 compound parent，模块 `layerId` 作为 parent 引用。
- API 深链使用 `api.html#<operationId>`；显示名称或 Tag 调整不得改变正式 API 引用。

## 技术选型、部署与运维结构

```javascript
technologySelections: [
  { id: "tech-language", category: "后端语言", name: "Java", version: "21", purpose: "领域服务", rationale: "与现有代码一致", alternatives: [], moduleIds: [], status: "fact", sourceRefs: [] }
],
deploymentDesign: [
  { id: "deploy-production", category: "生产部署", name: "容器集群", environment: "production", topology: "Gateway + Services + Workers", strategy: "滚动/金丝雀", scaling: "水平扩缩", recovery: "自动回滚", moduleIds: [], status: "decision", sourceRefs: [] }
],
operationsDesign: [
  { id: "ops-observability", category: "可观测性", name: "统一遥测", objective: "关联业务与运行链路", indicators: [], tooling: [], alerting: "分级告警", owner: "待确认", moduleIds: [], status: "decision", sourceRefs: [] }
]
```

示例字段只说明结构；实际值必须来自输入或明确设计决策。详细要求见 `technology-operations.md`。

## 流程图结构

```javascript
{
  id: "flow-example",
  name: "示例流程",
  direction: "LR",
  nodes: [
    { id: "flow-node-start", name: "开始", nodeType: "start", moduleId: "module-example" },
    { id: "flow-node-handle", name: "处理", nodeType: "process", moduleId: "module-example" }
  ],
  edges: [
    { id: "flow-edge-start-handle", sourceId: "flow-node-start", targetId: "flow-node-handle", name: "进入处理", type: "normal" }
  ]
}
```

`nodeType` 使用 `start | end | process | decision | manual | external | data`。异常或补偿路径使用 `type: "exception"` 或 `lineType: "dashed"`。

## 时序图结构

```javascript
{
  id: "sequence-example",
  name: "示例场景",
  participants: [
    { id: "participant-user", name: "用户", type: "actor", refId: "actor-user" },
    { id: "participant-module", name: "示例模块", type: "module", refId: "module-example" }
  ],
  messages: [
    { id: "message-request", sourceId: "participant-user", targetId: "participant-module", name: "发起请求", callType: "sync", apiOperationId: "api-example" }
  ]
}
```

`callType` 使用 `sync | async | event | return | callback | exception | timeout`。
