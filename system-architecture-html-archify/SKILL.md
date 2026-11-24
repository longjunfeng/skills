---
name: system-architecture-html-archify
description: 根据需求、代码和参考资料创建或修改可追溯的系统架构设计 HTML；整体架构图、流程图和时序图统一使用已安装的 Archify 生成并校验，同时维护 OpenAPI、技术选型、部署运维和统一数据关系。
---

# 系统架构设计 HTML（Archify 图形版）

本技能保留 `system-architecture-html` 的页面、OpenAPI、技术选型、部署运维、业务名词、追溯和验收能力，但把所有架构图、流程图和时序图统一交给 Archify。

## 使用前必读

在分析或修改文件前完整读取：

- `references/architecture-html-spec.md`
- `references/archify-integration.md`
- `references/data-model.md`
- `references/openapi-api-rendering.md`
- `references/technology-operations.md`

同时完整读取已安装 `archify/SKILL.md`，并按当前图形类型读取 Archify 的 `common.schema.json`、对应 schema 和一个示例。若旧交付使用 Mermaid/Cytoscape，只将其作为迁移基线；新图形事实源必须是 Archify JSON。

保持 `fact / decision / suggestion / pending / poc` 的边界，未知内容不得伪装成事实。

## 工作模式

- 创建：分析输入后建立统一数据、OpenAPI、静态页面和 Archify 图册。
- 修改：先运行校验并理解现有稳定 ID、Hash、接口与图册，再做增量变更。
- 验收：保持只读，报告静态页面、OpenAPI 和 Archify artifact/browser evidence。

用 `rg --files` 盘点需求、代码、参考图和现有交付物；用 `rg` 和代码定位建立证据。图片参考必须实际视觉检查。

## 输出结构

至少生成：

```text
index.html
api.html
openapi.json
styles.css
app.js
architecture-data.js
openapi-runtime.js
vendor/swagger-ui*
archify/*.json
archify/*.html
```

主页面保留 `overview`、`architecture`、`technology-operations`、`flows`、`sequences`、`er-diagram`、`api-catalog`、`glossary`、`decisions`、`risks` 等稳定区域。通过同源 iframe 或本地链接引用 Archify HTML；不要复制生成的 SVG 或节点正文。

## Archify 生成流程

1. 选择 `architecture`、`workflow`、`sequence`、`lifecycle` 或 `dataflow`。逻辑架构和物理部署通常分图。
2. 先写候选 JSON；使用稳定业务 ID、清晰主路径、自动路由、简洁标签，默认 `meta.quality_profile: showcase`。真实代码图为关键元素提供 `sources`。
3. 每次修改后运行：

   ```bash
   node "$CODEX_HOME/skills/archify/bin/archify.mjs" validate <type> <spec.json> --repo-root <repo> --quality showcase --json
   ```

4. 依据诊断的 `subject`、`evidence`、`supportedFixes` 做单点修复。不得通过删除有意义标签或关闭检查规避错误。
5. 最终运行 `deliver`；通过后冻结 JSON，不再编辑。随后对精确 HTML 运行 `visual-check`。
6. 分别报告 artifact checks、浏览器 evidence 和人工视觉复核；不能把自动截图称作人工复核。

若 `CODEX_HOME` 未设置，使用已安装 Archify 的绝对路径，例如 `C:\Users\88888\.codex\skills\archify\bin\archify.mjs`。

## 数据职责

- Archify JSON：图形拓扑、呈现语义、稳定图元 ID、来源证据和图册元数据。
- `architecture-data.js`：跨图册详情、模块/表/API/风险关联、搜索和页面抽屉数据。
- `openapi.json`：HTTP Operation 的唯一契约事实源。

统一数据必须有 `diagramRefs`，每项登记图册 ID、类型、JSON/HTML 路径、状态、来源和关联对象。`flowIds`、`sequenceIds`、`diagramRefId`、`apiOperationIds` 必须可解析，禁止按显示名称关联。

## 图形边界

- 架构与部署：Archify `architecture`。
- 业务流程、审批、Agent/工具调用：Archify `workflow`。
- API、异步消息、回调、超时、重试调用链：Archify `sequence`。
- 状态、恢复与终态：Archify `lifecycle`。
- 管道、ETL、数据血缘：Archify `dataflow`。
- ER 可用语义化 SVG；需要完整图册体验时用 Archify `architecture`，表节点保留 `table-` ID。

不要在新交付中加载 Mermaid、Cytoscape 或另一套图形运行时。

## 验收

运行 `scripts/validate_architecture.py <output> --json`，修复全部错误。每张 Archify 图还必须完成 `validate`、`deliver` 和 `visual-check`；检查主页面 Hash、折叠、图册链接/iframe、键盘、错误降级、窄屏无页面级横向溢出，以及 `api.html#<operationId>` 深链和本地 Swagger UI。

最终提供绝对文件路径、图册类型和数量、Archify receipt、浏览器 evidence、人工视觉复核状态、待确认与未完成项。

