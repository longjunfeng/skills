# 统一数据模型

```javascript
window.ARCHITECTURE_DATA = Object.freeze({
  meta: { openapiUrl: "./openapi.json" },
  sources: [], diagramRefs: [], layers: [], modules: [], features: [], edges: [],
  flows: [], sequences: [], tables: [], tableRelations: [],
  technologySelections: [], deploymentDesign: [], operationsDesign: [],
  glossary: [], decisions: [], risks: [], confirmations: [], pocItems: []
});
```

每个元素至少包含稳定 ID、名称、类型、摘要、说明、`status`、`sourceRefs`、关联 ID 和 pending 状态。

`diagramRefs` 示例：

```javascript
{
  id: "diagram-runtime-architecture",
  name: "Runtime 架构",
  type: "architecture",
  specPath: "archify/runtime.architecture.json",
  htmlPath: "archify/runtime.architecture.html",
  status: "fact",
  sourceRefs: ["source-code-runtime"],
  relatedIds: ["module-runtime"]
}
```

模块、流程、时序等通过 `diagramRefId` 或 `diagramRefIds` 关联图册。API 只保存 `apiOperationId(s)`，请求响应正文只在 `openapi.json`。删除对象时同步清理所有反向引用。

