---
name: system-architecture-html
description: 根据需求文档、现有代码、参考架构图和补充说明，创建或修改结构完整、可交互、可下钻、可追溯的静态系统架构设计 HTML；使用 Mermaid 渲染流程图和时序图，使用 Cytoscape.js 渲染可读的分层模块架构图，使用 OpenAPI JSON 与本地 Swagger UI 渲染接口，并设计技术选型、部署拓扑和运维模式。用于新建或增量修改架构 HTML、API、技术与运维设计、业务名词表格、数据模型、决策、风险，或执行一致性、响应式、图形和无障碍验收。
---

# 系统架构设计 HTML

## 首要规则

在分析资料、制定方案、创建文件或修改文件之前，完整读取 [references/architecture-html-spec.md](references/architecture-html-spec.md)、[references/diagram-rendering.md](references/diagram-rendering.md)、[references/openapi-api-rendering.md](references/openapi-api-rendering.md) 和 [references/technology-operations.md](references/technology-operations.md)。四份文件是创建、修改和验收的强制规范；不得只依据本文件的摘要行动。

保持事实、设计与推断的边界。按规范标记“已有事实”“本次设计决策”“架构建议”“待确认事项”“POC 验证项”，不得把未确认推断写成事实。

## 判断工作模式

先根据用户意图和输出目录选择模式：

- **创建**：输出目录中不存在可用的架构设计，或用户明确要求新建、重建。
- **修改**：用户要求更新、补充、修正、重构或美化已有架构设计。
- **验收**：用户只要求检查、评审或报告问题时，保持只读，不自动修改。

修改模式下必须先检查现有实现和基线问题，不得直接用模板覆盖。

## 收集与解析输入

确认或从上下文解析以下信息：系统名称、需求文档目录、现有代码目录、参考架构图、输出目录、技术栈约束、补充设计要求。优先从用户消息、附件和工作区发现答案；仅在关键路径或目标存在实质歧义且错误假设会造成风险时询问。

按以下顺序处理冲突：调用者明确说明 → 已确认的需求和设计文档 → 现有代码和公共组件 → 参考架构图 → 通用架构原则 → 本次架构推断。

使用 `rg --files` 建立资料清单，再用 `rg`、文件读取和必要的代码检查提取证据。对图片格式的参考架构图进行视觉检查。不要只读目录名或文件名就推断设计。

## 通用工作流

1. **盘点资料**：列出需求、代码、图示和现有交付物，识别冲突、缺口及权威来源。
2. **提取事实**：识别系统边界、参与者、外部系统、模块、功能、流程、场景、接口、领域对象、表、名词、技术约束、部署环境、运维责任、非功能要求和风险。
3. **建立追溯关系**：为关键结论记录来源文件或代码位置；为每类设计元素分配稳定唯一 ID。
4. **统一建模**：使用 `architecture-data.js` 维护架构元素、技术选型、部署和运维设计，使用 `openapi.json` 维护 HTTP API 契约；两者通过稳定 `operationId` 关联，禁止复制接口正文。
5. **实现页面**：使用静态 HTML、CSS 和 JavaScript；流程图、时序图使用本地 Mermaid，整体架构图使用本地 Cytoscape.js；不引入构建步骤或外部 CDN。
6. **交互核验**：检查折叠、Hash 定位、Tab、Tooltip、详情抽屉、节点与边高亮、Mermaid 缩放/平移/全屏、搜索筛选、键盘操作和移动端布局。
7. **一致性核验**：检查模块、接口、表、流程、时序和名词之间没有失效引用或无法追溯的孤立元素。
8. **运行验收**：执行附带校验脚本，并在可用时通过本地静态服务器进行浏览器验收。
9. **交付报告**：按规范报告文件、数量、待确认事项、浏览器结果和未完成内容。

## 创建架构设计

1. 先分析全部相关输入，再决定分层、模块、流程、时序、接口和表；不得预设固定业务结构。
2. 先定义统一数据模型和稳定 ID，再编写渲染逻辑。新建项目优先参考 [references/data-model.md](references/data-model.md)。
3. 至少生成：`index.html`、`api.html`、`openapi.json`、`styles.css`、`app.js`、`architecture-data.js`、`diagram-theme.css`、`diagram-runtime.js`、`openapi-runtime.js`、`vendor/mermaid.min.js`、`vendor/cytoscape.min.js`、Swagger UI 的 CSS/JS/Source Map 和第三方许可证文件。
4. 新建页面优先使用以下稳定区域 ID：`overview`、`architecture`、`technology-operations`、`flows`、`sequences`、`er-diagram`、`api-catalog`、`glossary`、`decisions`、`risks`。
5. 将所有不确定信息显式纳入待确认事项；只有具备输入依据时才创建接口、数据库表和业务规则。
6. 保证 `api.html` 可通过本地静态服务器独立访问，并使用本地 Swagger UI 加载与主页面共用的 `openapi.json`。
7. 页面整体不得横向溢出；超宽图仅允许在图表容器内滚动。
8. 从技能的 `assets/` 复制图形、OpenAPI 运行时和本地依赖；不要重新手写、压缩或从 CDN 引入 Mermaid、Cytoscape.js 或 Swagger UI。

## 修改已有架构设计

1. 读取现有 HTML、CSS、JavaScript 和数据文件，理解数据流、渲染方式、交互和用户定制。
2. 修改前运行 `python3 scripts/validate_architecture.py <输出目录>`，记录基线问题；区分既有问题和本次改动引入的问题。
3. 将新资料与现有设计逐项对比，列出新增、变更、废弃、冲突和待确认内容。
4. 尽量保留已有稳定 ID、URL Hash、API 锚点、数据字段和外部引用。确需更名时同步迁移所有引用，必要时保留兼容锚点。
5. 架构变化优先修改 `architecture-data.js`，HTTP API 契约变化优先修改 `openapi.json`；两者只通过稳定 `operationId` 关联，避免在 HTML 或 JavaScript 中重复写接口正文。
6. 保留与用户请求无关的自定义样式、交互和内容。不要整页重写，除非现有结构无法安全满足规范或用户明确要求重建。
7. 删除元素前先检查所有关联对象；将合理的删除同步到导航、详情、搜索、流程、时序、ER 和 API 锚点。
8. 完成后重新运行校验脚本和浏览器回归，重点检查旧链接、旧 Hash 和未修改区域。
9. 从原生 HTML/SVG 迁移图形时，只替换渲染层和事件入口；保留原节点/边/消息 ID、详情类型、Hash、抽屉函数和 Tooltip 数据。
10. 从自定义 API 卡片或接口数组迁移时，先生成等价 `openapi.json`，再接入 Swagger UI；保留旧 API ID 作为 `operationId`，并把旧 Hash 迁移为 `api.html#<operationId>`。

## 实现约束

- 让 `architecture-data.js` 暴露一个明确的全局只读入口，例如 `window.ARCHITECTURE_DATA`；页面不得各自维护重复的接口或表定义。
- 让 `openapi.json` 成为 HTTP API 请求、响应、参数、鉴权、错误码和 Schema 的唯一事实源；默认使用 OpenAPI 3.1.0 JSON。
- 让模块、功能、流程和时序只保存 `operationId` 引用；不要在 `architecture-data.js` 中复制 OpenAPI Operation 字段。
- 使用 `technologySelections`、`deploymentDesign`、`operationsDesign` 维护技术选型、部署和运维事实；每项包含理由、范围、状态和来源，不用静态 HTML 复制正文。
- 将业务名词渲染为简洁的响应式 `.design-table.glossary-table`，保留搜索、领域筛选、键盘下钻和详情抽屉；不要默认使用卡片瀑布流。
- 让 `api.html` 使用本地 Swagger UI 与 `openapi-runtime.js` 渲染；架构页到具体接口使用 `api.html#<operationId>` 稳定链接。
- 让 Mermaid DSL 从 `architecture-data.js` 的流程节点、流程边、参与者和时序消息生成；不得维护第二份硬编码 Mermaid 业务数据。
- 使用 `window.ArchitectureDiagrams` 统一渲染和绑定事件。流程图和时序图必须显式调用 `mermaid.render`，不要使用自动扫描 `<pre class="mermaid">`。
- 使用 `renderMermaid` 自动生成 Mermaid Viewer 和工具栏；流程图与时序图必须支持适应画布、放大、缩小、100% 重置、拖拽平移、双击背景放大、`Ctrl/⌘ + 滚轮` 缩放和全屏查看。
- 保留 `renderMermaid` 返回的 `view` 控制器，在 Tab 激活、折叠展开或容器尺寸变化后调用 `view.fit()`；不得为同一图重复绑定工具栏或全屏监听器。
- 使用 Cytoscape.js compound node 表达层和模块，使用 Cytoscape edge 表达关系；不要继续用 HTML 卡片加绝对定位线条实现整体架构图。
- 架构图默认使用运行时的连接感知分层布局：按层级排序、按相邻依赖进行重心排序、限制每行节点数并居中层内容；模块使用所属层的低饱和色，关系标签降低默认权重，键盘列表默认折叠。
- 使用稳定、可读、带类型前缀的 ID，例如 `layer-`、`module-`、`feature-`、`edge-`、`flow-`、`sequence-`、`table-`、`api-`、`term-`、`decision-`、`risk-`。
- 所有跨页面关系按 ID 引用，不按显示名称做脆弱匹配。
- 图形节点、关系边和时序消息同时支持鼠标与键盘操作；不要只依赖颜色表达状态。
- 将未知字段明确显示为待确认，不使用空白卡片、虚假示例、占位文本或未说明的 `TODO`。
- 如果输入提供真实代码，代码结构建议必须与仓库语言、框架、模块边界和已有公共组件相符。

## 验收与修复循环

从技能目录执行：

```bash
python3 scripts/validate_architecture.py /absolute/path/to/output
```

脚本检查必需文件、HTML 重复 ID、页内与跨页锚点、本地资源、外部脚本/样式、占位文本、JavaScript 语法、统一数据 ID、OpenAPI JSON 结构、Operation ID、本地 `$ref` 和 Swagger UI 资源。修复所有错误，并判断每条警告是否会违反项目规范。

随后启动本地静态服务器并进行浏览器检查，例如：

```bash
python3 -m http.server 8000 --directory /absolute/path/to/output
```

检查桌面和窄屏尺寸、控制台错误、网络资源、折叠与 Hash、Tooltip、抽屉、Tab、Mermaid 工具栏缩放、背景拖拽、滚轮缩放、全屏进入/退出与焦点恢复、搜索筛选、Swagger UI 的 Schema/响应展示、`api.html#<operationId>` 深链和键盘焦点。逐一点击流程节点/边、时序参与者/消息、架构层/模块/边，并确认回调收到统一数据中的稳定 ID。只有实际完成浏览器检查后才能报告“浏览器验收通过”。

## 最终响应

简要说明创建或修改结果，提供输出文件的绝对路径链接，并报告规范要求的各类数量。列出待确认事项、POC 验证项、验收结果、未完成内容及原因。修改模式下补充说明保留了哪些兼容性，以及是否仍存在基线问题。

## 资源

- [references/architecture-html-spec.md](references/architecture-html-spec.md)：用户提供的完整架构设计 HTML 编写和验收规范，始终完整读取。
- [references/diagram-rendering.md](references/diagram-rendering.md)：Mermaid、Cytoscape.js、事件兼容、可访问性和图形验收规范，始终完整读取。
- [references/openapi-api-rendering.md](references/openapi-api-rendering.md)：OpenAPI JSON、架构追溯扩展、Swagger UI、稳定链接和 API 验收规范，始终完整读取。
- [references/technology-operations.md](references/technology-operations.md)：技术选型、部署拓扑、运维模式、统一数据和表格验收规范，始终完整读取。
- [references/data-model.md](references/data-model.md)：新建设计时的推荐统一数据结构；修改现有设计时仅在兼容的前提下采用。
- `assets/diagram-runtime.js`、`assets/diagram-theme.css`：复制到输出目录的通用图形渲染与视觉资源。
- `assets/openapi-runtime.js`：复制到输出目录的 Swagger UI 初始化、错误降级和 Operation ID 定位运行时。
- `assets/vendor/`：复制到输出目录的 Mermaid、Cytoscape.js、Swagger UI 和许可证文件。
- `scripts/validate_architecture.py`：静态交付物快速验收工具。
