# 图形渲染与交互实现规范

本规范规定整体架构图、流程图和时序图的实现方式。创建、修改或验收这些图形时必须完整读取。

## 目录

1. 技术选型与本地资源
2. 页面加载、容器与数据模型
3. Mermaid 渲染与点击事件兼容
4. Mermaid 缩放、平移与全屏
5. Cytoscape.js 架构图与布局
6. 错误降级与验收

## 1. 技术选型

- 流程图：Mermaid `flowchart`。
- 时序图：Mermaid `sequenceDiagram`。
- 整体架构图：Cytoscape.js 复合图。层使用 compound parent node，模块使用 child node，调用关系使用 edge。
- ER 图可继续使用现有 SVG/HTML 实现；如果改用 Mermaid ER 图，也必须保留节点下钻和稳定 ID。
- 使用技能自带的本地依赖，不使用 CDN，不增加构建步骤。

技能资源：

- `assets/vendor/mermaid.min.js`：Mermaid 11.16.1。
- `assets/vendor/cytoscape.min.js`：Cytoscape.js 3.33.1。
- `assets/diagram-runtime.js`：统一转换、渲染和事件桥接。
- `assets/diagram-theme.css`：图形基础样式。
- `assets/vendor/LICENSES.txt`：第三方许可证。

创建模式下，将以上文件复制到输出目录的对应路径：

```text
output/
├── vendor/
│   ├── mermaid.min.js
│   ├── cytoscape.min.js
│   └── LICENSES.txt
├── diagram-runtime.js
└── diagram-theme.css
```

修改模式下，如果已有本地 Mermaid 或 Cytoscape.js，先确认版本和 API 兼容性；兼容时保留现有依赖，不重复引入。若已有实现依赖 CDN，迁移到本地资源。

## 2. 页面加载顺序

在 `index.html` 中按以下顺序加载：

```html
<link rel="stylesheet" href="styles.css">
<link rel="stylesheet" href="diagram-theme.css">
<script src="architecture-data.js"></script>
<script src="vendor/mermaid.min.js"></script>
<script src="vendor/cytoscape.min.js"></script>
<script src="diagram-runtime.js"></script>
<script src="app.js"></script>
```

`api.html` 不加载 Mermaid、Cytoscape.js 或 `architecture-data.js`。它按 `openapi-api-rendering.md` 加载本地 Swagger UI、`openapi-runtime.js` 和唯一的 `openapi.json`；不得因为 API 页面不渲染图形而复制接口数据。

## 3. HTML 容器

HTML 只声明语义容器，不手写图形节点：

```html
<div class="diagram-toolbar" aria-label="架构图工具栏">
  <button type="button" data-diagram-action="fit">适应画布</button>
  <button type="button" data-diagram-action="zoom-in">放大</button>
  <button type="button" data-diagram-action="zoom-out">缩小</button>
</div>
<div id="architecture-canvas" class="diagram-surface cytoscape-architecture"></div>

<div id="flow-canvas" class="diagram-surface" aria-live="polite"></div>
<div id="sequence-canvas" class="diagram-surface" aria-live="polite"></div>
```

架构图工具栏由页面绑定 Cytoscape 控制器。流程图和时序图不要手写工具栏；`renderMermaid` 会在容器内自动创建统一 Mermaid Viewer、控制栏、视口和变换舞台，避免每个 Tab 重复实现事件。

每个 Tab 切换后再渲染当前图。隐藏 Tab 不要提前测量或渲染，否则 Mermaid/Cytoscape.js 可能得到错误尺寸。再次显示已渲染图时调用适配方法，不重复注册事件。

## 4. 数据模型要求

### 流程图

```javascript
{
  id: "flow-submit-order",
  name: "提交订单",
  direction: "LR",
  nodes: [
    { id: "flow-node-start", name: "开始", nodeType: "start", moduleId: "module-order" },
    { id: "flow-node-check", name: "校验库存", nodeType: "decision", moduleId: "module-inventory" }
  ],
  edges: [
    { id: "flow-edge-start-check", sourceId: "flow-node-start", targetId: "flow-node-check", name: "提交", type: "normal" }
  ]
}
```

`nodeType` 使用 `start | end | process | decision | manual | external | data`。异常边使用 `type: "exception"` 或 `lineType: "dashed"`。

### 时序图

```javascript
{
  id: "sequence-submit-order",
  name: "提交订单场景",
  participants: [
    { id: "participant-user", name: "用户", type: "actor", refId: "actor-user" },
    { id: "participant-order", name: "订单模块", type: "module", refId: "module-order" }
  ],
  messages: [
    { id: "message-submit", sourceId: "participant-user", targetId: "participant-order", name: "提交订单", callType: "sync", apiOperationId: "api-submit-order" }
  ]
}
```

`callType` 使用 `sync | async | event | return | callback | exception | timeout`。`apiOperationId` 指向 `openapi.json` 中唯一的 Operation。每条消息必须有稳定 ID；不要用消息文本充当关联键。

### 架构图

`layers`、`modules`、`edges` 直接消费统一数据：

- `layers[].id` 作为 Cytoscape compound parent node ID。
- `modules[].layerId` 映射为 Cytoscape `parent`。
- `edges[].sourceId`、`targetId` 映射为 Cytoscape edge source/target。
- `edges[].relationType === "hierarchy"` 使用虚线；模块调用使用实线。

## 5. Mermaid 渲染

不要使用 `<pre class="mermaid">` 的自动扫描模式。使用 `startOnLoad: false` 和显式异步渲染，以便在 Tab 切换、错误处理和事件绑定完成后再显示结果。

```javascript
const diagrams = window.ArchitectureDiagrams;
const definition = diagrams.buildFlowchart(flow);

const renderedFlow = await diagrams.renderMermaid(
  document.querySelector("#flow-canvas"),
  definition,
  { nodes: flow.nodes, edges: flow.edges },
  {
    kind: "flow",
    ariaLabel: `${flow.name}流程图`,
    onActivate: handleDiagramActivate,
    onHover: handleDiagramHover,
    onLeave: hideTooltip
  }
);

renderedFlow.view.fit();
```

时序图：

```javascript
const definition = diagrams.buildSequence(sequence);
await diagrams.renderMermaid(
  document.querySelector("#sequence-canvas"),
  definition,
  { participants: sequence.participants, messages: sequence.messages },
  {
    kind: "sequence",
    ariaLabel: `${sequence.name}时序图`,
    onActivate: handleDiagramActivate,
    onHover: handleDiagramHover,
    onLeave: hideTooltip
  }
);
```

Mermaid DSL 必须由统一数据生成，禁止同时维护一份硬编码 Mermaid 文本和一份 JavaScript 业务数据。

`renderMermaid` 返回 `{ container, svg, definition, view }`。`view` 至少提供：

```javascript
view.fit();
view.reset();
view.zoomIn();
view.zoomOut();
view.zoomAt(1.5);
view.toggleFullscreen();
view.getScale();
view.destroy();
```

Tab 激活、折叠区域展开或容器由隐藏变为可见时调用当前图的 `view.fit()`。重新渲染同一容器时，运行时必须先销毁旧控制器，清理 ResizeObserver、Fullscreen 和文档级监听器。

## 6. Mermaid 缩放、平移与全屏

统一 Viewer 必须包含以下控制：

- “适应”：完整显示当前 SVG，并居中到可用视口。
- “缩小”和“放大”：默认按约 `1.2` 倍调整，缩放范围默认 `25%–400%`。
- “100%”：恢复原始比例并居中。
- “全屏”：优先调用 Fullscreen API；失败时使用固定定位降级。
- 比例状态：显示当前百分比，并通过 `aria-live` 向辅助技术报告。

直接操作要求：

- 从非交互背景按下并拖动时平移；节点、边、参与者和消息上的指针操作仍进入详情逻辑。
- 双击非交互背景时以指针位置为中心放大。
- `Ctrl/⌘ + 滚轮` 或触控板捏合时以指针位置为中心缩放；普通滚轮继续用于页面滚动。
- 视口聚焦时，`+`/`-` 缩放，`0` 适应，`1` 恢复 100%，`F` 切换全屏，方向键平移；不得截获 SVG 内交互元素的 Enter、Space 或方向键。
- 非全屏移动端保留页面纵向触摸滚动；全屏模式允许触摸拖拽图形。

状态与生命周期要求：

- 每张 Mermaid 图保存独立 `scale/x/y/mode` 状态，不能用全局比例影响其他 Tab。
- ResizeObserver 只在当前模式为“适应”时重新计算；用户手动缩放或平移后不自动重置。
- 进入或退出全屏后，在“适应”模式重新适配；手动模式保持用户比例和位置。
- Escape 退出原生或降级全屏；降级全屏退出后移除页面滚动锁定并把焦点返回全屏按钮。
- 工具栏和视口均位于 Mermaid 容器内部；全屏时工具栏保持可见，SVG 不得突破 Viewer 造成页面横向溢出。
- 缩放使用 SVG 外层舞台的 CSS transform，保持 Mermaid SVG 内部稳定 ID 绑定和点击事件，不重新生成 DSL。

## 7. 点击事件兼容

迁移图形实现时保持原来的业务处理函数、稳定 ID、Hash 和详情类型。只替换 DOM 事件入口：

```javascript
function handleDiagramActivate({ kind, id, data, element }) {
  if (kind === "flow-node") return openDetail("flow-node", id, element);
  if (kind === "flow-edge") return openDetail("flow-edge", id, element);
  if (kind === "sequence-participant") return openDetail(data.refId ? "related" : "participant", data.refId || id, element);
  if (kind === "sequence-message") return openDetail("sequence-message", id, element);
  if (kind === "architecture-layer") return openDetail("layer", id, element);
  if (kind === "architecture-node") return openDetail("module", id, element);
  if (kind === "architecture-edge") return openDetail("edge", id, element);
}
```

要求：

- 节点和边都可点击。
- Enter 和 Space 触发与点击相同的行为。
- 点击 Mermaid 边的线条或边标签都打开同一详情。
- 点击时序消息线或消息文字都打开同一详情。
- 事件回调只传稳定 ID，不用 DOM 自动生成 ID 作为业务 ID。
- 重渲染前清空旧容器；不得在同一节点重复注册监听器。
- 打开详情后，关闭时恢复焦点到触发元素或对应键盘入口。

Mermaid 没有稳定的跨图形边点击 API。`diagram-runtime.js` 按统一数据顺序将渲染后的边和消息重新绑定到稳定 ID；因此生成 DSL 时必须保持 `flow.edges` 和 `sequence.messages` 的原顺序，不能排序后只更新 DSL 而不更新绑定数组。

## 8. Cytoscape.js 架构图

```javascript
const architectureView = window.ArchitectureDiagrams.renderArchitecture(
  document.querySelector("#architecture-canvas"),
  {
    layers: ARCHITECTURE_DATA.layers,
    modules: ARCHITECTURE_DATA.modules,
    edges: ARCHITECTURE_DATA.edges
  },
  {
    ariaLabel: "系统整体分层与模块架构图",
    onActivate: handleDiagramActivate,
    onHover: handleDiagramHover,
    onLeave: hideTooltip
  }
);
```

工具栏操作：

```javascript
architectureView.cy.fit(undefined, 34);
architectureView.cy.zoom(architectureView.cy.zoom() * 1.15);
architectureView.cy.zoom(architectureView.cy.zoom() / 1.15);
```

架构图视觉规则：

- 层为低饱和虚线复合边界，标题固定在边界左上。
- 模块卡片使用白色或轻微色阶背景、细边框和弱阴影。
- 普通关系边透明度保持在 25%–40%，宽度约 1px。
- 只在悬浮、选中或键盘聚焦时增强当前边和箭头。
- 页面提供适应画布、放大、缩小和重置操作。
- 图形容器设置稳定最小高度；不得依靠内容自动撑高 Canvas。
- 模块过多时按领域拆分视图或提供筛选，不把全部模块挤进一个不可读画布。

Cytoscape.js Canvas 内部元素不能成为原生 Tab 焦点。必须保留运行时生成的 `architecture-keyboard-list`，或实现功能等价的可访问节点/边列表。该列表与画布使用相同稳定 ID，聚焦时高亮对应图形，点击时打开同一详情。

## 9. 布局选择

默认使用运行时提供的连接感知 `preset` 分层布局：层按 `level` 和数据顺序纵向排列，模块优先按显式 `order` 排序，再通过相邻层依赖的重心排序减少交叉；层内模块限制每行数量、保持统一间距并相对全图居中。若关系网络比层顺序更重要，可显式改用 Cytoscape.js 内置 `cose` 布局；不要仅使用普通 HTML Grid 后再绝对定位 SVG 边。

选择规则：

- 层少于 4 层或单层模块较多：使用纵向 `preset`，每层一个区带。
- 层达到 4 层且每层通常不超过 6 个模块：运行时默认使用双列蛇形分层，使连续层保持相邻并提高默认缩放比例；可通过 `layerArrangement: "vertical"` 强制纵向。
- 模块少、跨层依赖复杂且层顺序可以弱化：`cose`。
- 模块超过约 35 个或边超过约 70 条：按领域/子系统拆分 Tab，默认只显示主要依赖，提供“显示全部关系”开关。

默认视觉与布局要求：

- 模块宽高保持一致，名称最多换行两行；完整职责进入 Tooltip 和详情。
- 每层使用一组低饱和背景/边框色，模块继承所属层的轻色背景，颜色只用于分组辅助。
- 层标题位于左上，层之间保留明显纵向间距，模块不能贴近父边界。
- 默认关系使用正交或平滑路由；普通边和标签低透明，悬浮、选中或键盘聚焦时才完整显示关系标签。
- 同层连接和跨层连接分开处理；双向或多重边使用不同偏移，避免完全重叠。
- `architectureLayout(data, options)` 允许设置 `layerArrangement`、`maxColumns`、`columnGap`、`rowGap`、`layerGap` 和 `sweeps`，但页面通常使用默认值。
- 可访问节点/边列表使用可折叠容器，避免几十个键盘入口在图下方持续占据大面积空间。

布局完成后调用 `cy.fit(undefined, 34)`。折叠区域展开、Tab 激活或容器尺寸变化后调用 `cy.resize(); cy.fit(...)`。

## 10. 错误与降级

- Mermaid DSL 解析失败时，在图形容器显示可读错误摘要和图 ID，同时将完整异常写入控制台。
- Mermaid Viewer 初始化、全屏或视口控制失败时显示可读降级，并至少保留原 SVG 的容器内滚动查看能力。
- 单个图渲染失败不得阻断其他图、导航、API 页面或详情抽屉。
- 禁止把 Mermaid 源码作为最终默认展示；可在“查看源码”折叠区提供诊断信息。
- Cytoscape.js 加载失败时，使用可访问的层/模块/边列表降级，列表仍可下钻。
- 不静默捕获错误，不显示空白画布。

## 11. 验收

除通用验收外，逐项检查：

- 网络面板没有 Mermaid/Cytoscape CDN 请求。
- 所有流程 Tab 都渲染为 Mermaid SVG。
- 所有时序 Tab 都渲染为 Mermaid SVG。
- 每个 Mermaid 图都自动生成适应、缩小、放大、100% 和全屏控制，比例状态正确更新。
- 按钮、双击背景、`Ctrl/⌘ + 滚轮`、背景拖拽、键盘快捷键均能控制当前图，且缩放范围有效。
- 全屏进入与 Escape 退出有效；原生 Fullscreen 不可用时降级模式仍覆盖视口并能退出。
- 切换 Tab、折叠再展开、窗口变化和退出全屏后适应模式尺寸正确，手动缩放状态不被意外重置。
- 流程节点、流程边、时序参与者、时序消息均能点击和键盘触发。
- 在节点、边、参与者或消息上拖动/双击不会错误触发背景平移或缩放。
- 业务回调收到的是 `architecture-data.js` 中的稳定 ID。
- 架构图由 Cytoscape.js 渲染，层边界包含所属模块，节点不越界到其他层。
- 架构节点和关系边点击行为与迁移前一致。
- 折叠后再展开、切换 Tab、调整窗口尺寸后图形尺寸正确。
- 图形渲染错误有可见降级，不出现空白区域。
- 窄屏只在图形容器内部滚动，页面本身不横向溢出。
