# OpenAPI 与 Swagger UI 实现规范

创建、修改或验收 API 契约与 API 页面时完整读取本规范。

## 目录

1. 单一事实源
2. OpenAPI JSON 生成规则
3. 架构追溯扩展
4. Swagger UI 页面
5. 稳定链接与主页面集成
6. 非 HTTP 接口与待确认接口
7. 验收

## 1. 单一事实源

- 使用输出目录中的 `openapi.json` 作为 HTTP API 契约的唯一事实源。
- 默认生成 OpenAPI `3.1.0` JSON；只有现有工具链明确要求时才降级到 `3.0.3`，并在设计决策中记录原因。
- 不在 `architecture-data.js`、`api.html` 或 `app.js` 中复制请求字段、响应字段、错误码、Schema 或接口说明。
- `architecture-data.js` 仅使用稳定 `operationId` 关联接口，例如 `api-submit-order`；模块、功能、流程和时序中的接口引用都保存 `operationId`。
- `api.html` 使用 Swagger UI 加载 `openapi.json`，不得手写第二套 API 卡片或树形接口正文。
- 修改旧交付物时，先把现有接口数组迁移为 OpenAPI Operations，再将旧数据缩减为 `operationId` 引用。只有外部兼容确有需要时才暂时保留旧字段，并明确标记废弃，禁止继续双写。

## 2. OpenAPI JSON 生成规则

生成合法 JSON，不生成 YAML。至少包含：

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "示例系统 API",
    "version": "0.1.0",
    "description": "契约范围、事实状态与依据说明"
  },
  "tags": [],
  "paths": {},
  "components": {
    "schemas": {},
    "securitySchemes": {}
  },
  "x-pending-interfaces": []
}
```

每个已具备 Method 和 Path 依据的 HTTP 接口建模为一个 Operation，并满足：

- `operationId` 使用稳定、唯一、带 `api-` 前缀的 ID；显示名称变化不得修改它。
- 使用 `summary` 表达简短中文用途，使用 `description` 记录边界、业务规则和依据。
- 使用 `tags` 分组；按领域、模块或资源选择一种稳定分组方式，不为视觉效果重复定义接口。
- 使用 `parameters` 描述 path、query、header 和 cookie 参数。
- 使用 `requestBody.content` 和 `responses[*].content` 引用 `components.schemas`。
- 使用 `security` 和 `components.securitySchemes` 表达鉴权；未知鉴权不得虚构。
- 至少定义一个响应；已知错误使用对应 HTTP 状态码和统一错误 Schema。
- 可复用对象放入 `components` 并使用本地 `$ref`，不要复制大段 Schema。
- 只有输入资料提供服务器地址时才生成 `servers`；不要用虚假域名或占位 URL。
- 示例值只能来自输入、代码或明确设计决策；无法确认时省略示例并登记待确认事项。

推荐 Operation：

```json
{
  "post": {
    "operationId": "api-submit-order",
    "summary": "提交订单",
    "tags": ["订单"],
    "requestBody": {
      "required": true,
      "content": {
        "application/json": {
          "schema": { "$ref": "#/components/schemas/SubmitOrderRequest" }
        }
      }
    },
    "responses": {
      "200": {
        "description": "提交成功",
        "content": {
          "application/json": {
            "schema": { "$ref": "#/components/schemas/SubmitOrderResponse" }
          }
        }
      }
    },
    "x-architecture": {
      "layerId": "layer-application",
      "moduleId": "module-order",
      "featureId": "feature-submit-order",
      "sourceRefs": ["source-requirement-01"],
      "tableIds": ["table-order"],
      "flowIds": ["flow-submit-order"],
      "sequenceIds": ["sequence-submit-order"],
      "status": "fact",
      "pending": false
    }
  }
}
```

## 3. 架构追溯扩展

使用 OpenAPI 规范扩展 `x-architecture` 保存架构关系，避免另建接口主数据。字段按实际依据填写：

- `layerId`：所属层 ID。
- `moduleId`：所属模块 ID。
- `featureId`：所属功能 ID。
- `sourceRefs`：来源证据 ID。
- `tableIds`：关联表 ID。
- `flowIds`：关联流程 ID。
- `sequenceIds`：关联时序 ID。
- `eventIds`：关联事件 ID。
- `status`：`fact | decision | suggestion | pending | poc`。
- `pending`：是否仍有关键字段待确认。
- `idempotency`、`concurrency`、`timeout`、`retry`：仅在有依据时填写。

OpenAPI 标准字段优先表达协议契约，`x-architecture` 只补充 OpenAPI 没有覆盖的架构追溯信息。

## 4. Swagger UI 页面

从技能 `assets/` 复制以下文件到输出目录：

```text
output/
├── openapi.json
├── openapi-runtime.js
└── vendor/
    ├── swagger-ui.css
    ├── swagger-ui.css.map
    ├── swagger-ui-bundle.js
    ├── swagger-ui-bundle.js.map
    ├── swagger-ui-standalone-preset.js
    ├── swagger-ui-standalone-preset.js.map
    ├── swagger-ui-LICENSE.txt
    └── swagger-ui-NOTICE.txt
```

`api.html` 只声明页面外壳和 Swagger 容器，按顺序加载：

```html
<link rel="stylesheet" href="styles.css">
<link rel="stylesheet" href="vendor/swagger-ui.css">
<main id="swagger-ui" aria-label="API 接口文档"></main>
<script src="vendor/swagger-ui-bundle.js"></script>
<script src="vendor/swagger-ui-standalone-preset.js"></script>
<script src="openapi-runtime.js"></script>
<script>
  window.ArchitectureApiDocs.render({
    specUrl: "./openapi.json",
    domId: "#swagger-ui"
  });
</script>
```

要求：

- 使用本地 Swagger UI，不使用 CDN，不引入构建步骤。
- 默认启用搜索筛选、Operation ID 展示和深链接。
- 静态架构文档默认禁用真实请求提交；只有用户明确要求并确认目标环境安全时才开启 Try it out。
- 加载失败时显示可读错误，不留下空白页面，并把完整错误写入控制台。
- 通过本地静态服务器访问；`file://` 下浏览器通常会阻止读取 `openapi.json`，不得据此改为复制内联契约。
- 保留 Swagger UI 的响应式和键盘能力，不用大段自定义 CSS 覆盖其核心布局。

## 5. 稳定链接与主页面集成

- 从架构页链接具体接口时使用 `api.html#<operationId>`，例如 `api.html#api-submit-order`。
- `openapi-runtime.js` 在 Swagger UI 完成渲染后按 `operationId` 定位并展开 Operation；不要依赖 Swagger 自动生成的 DOM ID 作为业务 ID。
- Swagger 自带 `#/tag/operationId` 深链接可以继续使用，但架构数据中的正式引用只保存 `operationId`。
- 主页面的 API 区域可以使用 `iframe` 集成 `api.html`，也可以读取同一个 `openapi.json` 生成轻量目录；不得复制接口正文。
- 统计 API 数量时按 `paths` 下的 Operation 数量计算，不按 Path 数量计算。

## 6. 非 HTTP 接口与待确认接口

- OpenAPI 只原生描述 HTTP API。Webhook 使用 OpenAPI `webhooks`，回调使用 `callbacks`。
- Kafka、MQ、事件 Topic 或其他异步消息契约优先使用 AsyncAPI；若本次交付被限定为单一 OpenAPI 文件，可在顶层 `x-async-interfaces` 中保存最小追溯信息，并明确说明它不是标准 OpenAPI Operation，Swagger UI 不会完整渲染消息契约。
- 已识别但缺少 Method、Path 或请求响应依据的接口放入顶层 `x-pending-interfaces`，包含稳定 ID、已知信息、缺失信息、影响范围和来源；不得编造 Path 塞入 `paths`。

## 7. 验收

除通用验收外，检查：

- `openapi.json` 是合法 JSON，`openapi`、`info`、`paths` 结构正确。
- 每个 Operation 的 `operationId` 唯一、稳定且以 `api-` 开头。
- 每个 Operation 至少具有 `summary` 或 `description`、`responses` 和 `x-architecture`。
- 所有本地 `$ref` 都能解析，未引用外部契约文件或远程 URL。
- `architecture-data.js` 中所有 API 引用都能解析到真实 `operationId`。
- `api.html` 只从本地加载 Swagger UI，并成功请求 `openapi.json`。
- Swagger UI 无控制台错误，搜索、折叠、Schema、鉴权说明和响应内容可用。
- `api.html#<operationId>` 能定位并展开正确接口。
- 主页面 API 入口和具体接口链接有效。
- 页面不包含与 `openapi.json` 重复维护的接口正文。
