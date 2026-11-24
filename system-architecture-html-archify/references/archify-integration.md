# Archify 集成规范

本规范覆盖旧版系统架构 HTML 中的所有图形实现要求。

## 图形事实源

每张图是独立 Archify JSON + HTML。显示名称可以修改，稳定 ID 不因文案改变。`architecture-data.js` 只登记 `diagramRefs` 和业务详情，不生成第二份图形 DSL。

## 来源

真实仓库图在 `meta.repository` 声明仓库地址和 40 位 revision，命令传 `--repo-root`。关键元素使用 `sources` 指向仓库相对路径和可选行号。未验证设计放页面待确认区，不能冒充证据。

## 命令

```bash
ARCHIFY="$CODEX_HOME/skills/archify/bin/archify.mjs"
node "$ARCHIFY" doctor
node "$ARCHIFY" validate architecture archify/architecture.json --repo-root . --quality showcase --json
node "$ARCHIFY" deliver architecture archify/architecture.json archify/architecture.html --repo-root . --quality showcase --json
node "$ARCHIFY" visual-check archify/architecture.html --json
```

## 质量

- 默认 showcase；密集图使用 standard 时必须说明原因。
- 默认自动路由，仅在诊断要求时增加几何控制。
- 保留协议、方向、同步/异步和失败语义，不用删标签修碰撞。
- 一条清晰主路径，少量侧分支；主图通常不超过 12 个一级节点。
- 不接受穿过节点、歧义走廊、标签遮挡或不可读文本。
- deliver 检查必须通过；visual-check containment 和可读性必须通过或如实报告。

## 页面集成

主页面只展示图册摘要和本地链接/同源 iframe，不复制 SVG。图册自身负责交互。若需从图册跳转业务详情，使用稳定 ID 深链或同源消息协议，不依赖自动生成的 SVG DOM ID。

