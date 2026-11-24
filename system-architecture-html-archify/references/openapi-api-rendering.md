# OpenAPI 与 Swagger UI 规范

使用 `openapi.json` 作为 HTTP 契约唯一事实源，默认 OpenAPI 3.1.0。每个 Operation 使用唯一、稳定、`api-` 前缀的 `operationId`，具有 summary/description、responses、tags 和 `x-architecture` 追溯。

`architecture-data.js` 和 Archify 图册只引用 operationId，不复制参数、请求、响应、错误或 Schema。缺少 Method/Path 依据的接口进入 `x-pending-interfaces`。非 HTTP 异步契约使用 AsyncAPI 或明确标注的扩展。

`api.html` 使用本地 Swagger UI 和 `openapi-runtime.js`，禁用默认真实请求提交。主页面使用 `api.html#<operationId>` 深链；加载失败显示可读错误。禁止 CDN 和第二套手写接口正文。

验收 JSON、唯一 operationId、本地 `$ref`、架构引用、Swagger 搜索/Schema/响应、深链和无控制台错误。

