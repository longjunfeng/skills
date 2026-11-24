#!/usr/bin/env python3
"""Validate a static system-architecture HTML delivery with stdlib only."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


REQUIRED_FILES = (
    "index.html",
    "api.html",
    "openapi.json",
    "styles.css",
    "app.js",
    "architecture-data.js",
    "diagram-theme.css",
    "diagram-runtime.js",
    "openapi-runtime.js",
    "vendor/mermaid.min.js",
    "vendor/cytoscape.min.js",
    "vendor/swagger-ui.css",
    "vendor/swagger-ui.css.map",
    "vendor/swagger-ui-bundle.js",
    "vendor/swagger-ui-bundle.js.map",
    "vendor/swagger-ui-standalone-preset.js",
    "vendor/swagger-ui-standalone-preset.js.map",
    "vendor/swagger-ui-LICENSE.txt",
    "vendor/swagger-ui-NOTICE.txt",
    "vendor/LICENSES.txt",
)
INDEX_DIAGRAM_RESOURCES = (
    "diagram-theme.css",
    "diagram-runtime.js",
    "mermaid.min.js",
    "cytoscape.min.js",
)
API_RESOURCES = (
    "swagger-ui.css",
    "swagger-ui-bundle.js",
    "swagger-ui-standalone-preset.js",
    "openapi-runtime.js",
)
HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
CANONICAL_SECTION_IDS = (
    "overview",
    "architecture",
    "technology-operations",
    "flows",
    "sequences",
    "er-diagram",
    "api-catalog",
    "glossary",
    "decisions",
    "risks",
)
PLACEHOLDER_RE = re.compile(r"\b(?:TODO|FIXME|TBD)\b|lorem\s+ipsum|待补充|占位(?:内容|文本|数据)", re.I)
DATA_ID_RE = re.compile(r"\bid\s*:\s*(['\"])([^'\"]+)\1")
API_REF_SINGLE_RE = re.compile(r"\b(?:apiOperationId|apiId)\s*:\s*(['\"])([^'\"]+)\1")
API_REF_ARRAY_RE = re.compile(r"\b(?:apiOperationIds|apiIds)\s*:\s*\[([^\]]*)\]", re.S)
QUOTED_VALUE_RE = re.compile(r"(['\"])([^'\"]+)\1")


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.hrefs: list[str] = []
        self.local_resources: list[str] = []
        self.external_resources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag == "a" and values.get("href"):
            self.hrefs.append(values["href"] or "")
        resource = None
        if tag == "script" and values.get("src"):
            resource = values["src"]
        elif tag == "link" and values.get("href") and "stylesheet" in (values.get("rel") or "").lower():
            resource = values["href"]
        if resource:
            scheme = urlsplit(resource).scheme.lower()
            if scheme in {"http", "https", "//"} or resource.startswith("//"):
                self.external_resources.append(resource)
            elif scheme not in {"data", "blob"}:
                self.local_resources.append(resource)


def add(result: dict[str, list[str]], level: str, message: str) -> None:
    result[level].append(message)


def parse_page(path: Path, result: dict[str, list[str]]) -> PageParser | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        add(result, "errors", f"无法读取 {path.name}: {exc}")
        return None
    parser = PageParser()
    try:
        parser.feed(text)
    except Exception as exc:  # HTMLParser can surface malformed declarations.
        add(result, "errors", f"{path.name} HTML 解析失败: {exc}")
        return None
    duplicates = [item for item, count in Counter(parser.ids).items() if count > 1]
    for item in duplicates:
        add(result, "errors", f"{path.name} 存在重复 ID: {item}")
    for match in PLACEHOLDER_RE.finditer(text):
        add(result, "errors", f"{path.name} 含未清理占位文本: {match.group(0)}")
    for resource in parser.external_resources:
        add(result, "warnings", f"{path.name} 使用外部脚本或样式资源: {resource}")
    return parser


def clean_local_target(raw: str) -> str | None:
    parsed = urlsplit(raw)
    if parsed.scheme or parsed.netloc or raw.startswith(("mailto:", "tel:", "javascript:")):
        return None
    return unquote(parsed.path)


def resolve_json_pointer(document: object, pointer: str) -> bool:
    if pointer == "#":
        return True
    if not pointer.startswith("#/"):
        return False
    current = document
    for raw_part in pointer[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False
    return True


def iter_json_refs(value: object):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str):
                yield item
            else:
                yield from iter_json_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_json_refs(item)


def validate_openapi(path: Path, result: dict[str, list[str]]) -> set[str]:
    operation_ids: set[str] = set()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        add(result, "errors", f"openapi.json 无法解析为 JSON: {exc}")
        return operation_ids
    if not isinstance(document, dict):
        add(result, "errors", "openapi.json 顶层必须是 JSON 对象")
        return operation_ids

    version = document.get("openapi")
    if not isinstance(version, str) or not re.fullmatch(r"3\.(?:0|1)\.\d+", version):
        add(result, "errors", "openapi.json 必须声明 OpenAPI 3.0.x 或 3.1.x 版本")
    info = document.get("info")
    if not isinstance(info, dict) or not info.get("title") or not info.get("version"):
        add(result, "errors", "openapi.json 的 info.title 和 info.version 为必填项")
    paths = document.get("paths")
    if not isinstance(paths, dict):
        add(result, "errors", "openapi.json 的 paths 必须是对象")
        paths = {}

    operation_locations: list[tuple[str, dict]] = []
    for route, path_item in paths.items():
        if not isinstance(route, str) or not route.startswith("/"):
            add(result, "errors", f"OpenAPI Path 必须以 / 开头: {route}")
        if not isinstance(path_item, dict):
            add(result, "errors", f"OpenAPI Path Item 必须是对象: {route}")
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                add(result, "errors", f"OpenAPI Operation 必须是对象: {method.upper()} {route}")
                continue
            operation_locations.append((f"{method.upper()} {route}", operation))

    webhooks = document.get("webhooks", {})
    if isinstance(webhooks, dict):
        for name, path_item in webhooks.items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if method.lower() in HTTP_METHODS and isinstance(operation, dict):
                    operation_locations.append((f"WEBHOOK {name} {method.upper()}", operation))

    seen: Counter[str] = Counter()
    for location, operation in operation_locations:
        operation_id = operation.get("operationId")
        if not isinstance(operation_id, str) or not operation_id:
            add(result, "errors", f"OpenAPI Operation 缺少 operationId: {location}")
            continue
        seen[operation_id] += 1
        operation_ids.add(operation_id)
        if not operation_id.startswith("api-"):
            add(result, "errors", f"OpenAPI operationId 必须以 api- 开头: {operation_id}")
        if not operation.get("summary") and not operation.get("description"):
            add(result, "errors", f"OpenAPI Operation 缺少 summary 或 description: {operation_id}")
        responses = operation.get("responses")
        if not isinstance(responses, dict) or not responses:
            add(result, "errors", f"OpenAPI Operation 缺少 responses: {operation_id}")
        if not isinstance(operation.get("x-architecture"), dict):
            add(result, "errors", f"OpenAPI Operation 缺少 x-architecture 追溯信息: {operation_id}")
        tags = operation.get("tags")
        if not isinstance(tags, list) or not tags:
            add(result, "warnings", f"OpenAPI Operation 未设置 Swagger 分组 tags: {operation_id}")
    for operation_id, count in seen.items():
        if count > 1:
            add(result, "errors", f"OpenAPI operationId 重复: {operation_id} ({count} 次)")

    pending = document.get("x-pending-interfaces", [])
    if not isinstance(pending, list):
        add(result, "errors", "openapi.json 的 x-pending-interfaces 必须是数组")
    for ref in iter_json_refs(document):
        if not ref.startswith("#"):
            add(result, "errors", f"OpenAPI 不允许外部 $ref，需改为本地 components 引用: {ref}")
        elif not resolve_json_pointer(document, ref):
            add(result, "errors", f"OpenAPI 本地 $ref 无法解析: {ref}")
    return operation_ids


def validate(directory: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    if not directory.is_dir():
        add(result, "errors", f"输出目录不存在或不是目录: {directory}")
        return result

    for filename in REQUIRED_FILES:
        if not (directory / filename).is_file():
            add(result, "errors", f"缺少必需文件: {filename}")

    openapi_file = directory / "openapi.json"
    operation_ids = validate_openapi(openapi_file, result) if openapi_file.is_file() else set()

    pages: dict[str, PageParser] = {}
    for filename in ("index.html", "api.html"):
        path = directory / filename
        if path.is_file():
            parsed = parse_page(path, result)
            if parsed:
                pages[filename] = parsed

    id_sets = {name: set(page.ids) for name, page in pages.items()}
    for filename, page in pages.items():
        resource_names = {
            Path(clean_local_target(item) or "").name
            for item in page.local_resources
            if clean_local_target(item)
        }
        if filename == "index.html":
            for shared_file in ("styles.css", "app.js", "architecture-data.js"):
                if shared_file not in resource_names:
                    add(result, "errors", f"{filename} 未加载共享资源: {shared_file}")
            for diagram_resource in INDEX_DIAGRAM_RESOURCES:
                if diagram_resource not in resource_names:
                    add(result, "errors", f"index.html 未加载图形资源: {diagram_resource}")
        if filename == "api.html":
            if "swagger-ui" not in id_sets.get(filename, set()):
                add(result, "errors", "api.html 缺少 id=swagger-ui 的 Swagger UI 容器")
            if "styles.css" not in resource_names:
                add(result, "errors", "api.html 未加载共享样式: styles.css")
            if "architecture-data.js" in resource_names:
                add(result, "errors", "api.html 不应加载 architecture-data.js；API 契约应只来自 openapi.json")
            for api_resource in API_RESOURCES:
                if api_resource not in resource_names:
                    add(result, "errors", f"api.html 未加载 OpenAPI 页面资源: {api_resource}")
            try:
                api_html_text = (directory / filename).read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                api_html_text = ""
            if "ArchitectureApiDocs.render" not in api_html_text:
                add(result, "errors", "api.html 未调用 ArchitectureApiDocs.render 初始化 Swagger UI")
        for resource in page.local_resources:
            local = clean_local_target(resource)
            if local and not (directory / local).is_file():
                add(result, "errors", f"{filename} 引用不存在的本地资源: {resource}")
        for href in page.hrefs:
            parsed = urlsplit(href)
            local = clean_local_target(href)
            if local is None:
                continue
            target_file = local or filename
            if target_file not in {"index.html", "api.html"}:
                if local and not (directory / local).exists():
                    add(result, "errors", f"{filename} 链接目标不存在: {href}")
                continue
            dynamic_api_target = (
                target_file == "api.html"
                and (parsed.fragment in operation_ids or parsed.fragment.startswith("/"))
            )
            if parsed.fragment and parsed.fragment not in id_sets.get(target_file, set()) and not dynamic_api_target:
                add(result, "errors", f"{filename} 锚点目标不存在: {href}")
        for resource in page.external_resources:
            if re.search(r"(?:mermaid|cytoscape|swagger)", resource, re.I):
                add(result, "errors", f"{filename} 的渲染框架必须本地加载，不能使用 CDN: {resource}")

    index_ids = id_sets.get("index.html", set())
    for section_id in CANONICAL_SECTION_IDS:
        if index_ids and section_id not in index_ids:
            add(result, "warnings", f"index.html 未使用推荐区域 ID: {section_id}")

    data_file = directory / "architecture-data.js"
    if data_file.is_file():
        try:
            data_text = data_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            add(result, "errors", f"无法读取 architecture-data.js: {exc}")
        else:
            ids = [match.group(2) for match in DATA_ID_RE.finditer(data_text)]
            for item, count in Counter(ids).items():
                if count > 1:
                    add(result, "errors", f"architecture-data.js 存在重复设计 ID: {item} ({count} 次)")
            if "ARCHITECTURE_DATA" not in data_text:
                add(result, "warnings", "architecture-data.js 未发现明确的 ARCHITECTURE_DATA 统一入口")
            if re.search(r"\bapis\s*:", data_text):
                add(result, "warnings", "architecture-data.js 仍包含 apis 字段；HTTP API 契约应迁移到 openapi.json")
            for field, label in (
                ("technologySelections", "技术选型"),
                ("deploymentDesign", "部署设计"),
                ("operationsDesign", "运维设计"),
            ):
                if not re.search(rf"\b{field}\s*:", data_text):
                    add(result, "warnings", f"architecture-data.js 缺少 {label} 数据字段: {field}")
            api_refs = [match.group(2) for match in API_REF_SINGLE_RE.finditer(data_text)]
            for match in API_REF_ARRAY_RE.finditer(data_text):
                api_refs.extend(item.group(2) for item in QUOTED_VALUE_RE.finditer(match.group(1)))
            for api_ref in sorted(set(api_refs)):
                if api_ref not in operation_ids:
                    add(result, "errors", f"architecture-data.js 引用不存在的 OpenAPI operationId: {api_ref}")
            for match in PLACEHOLDER_RE.finditer(data_text):
                add(result, "errors", f"architecture-data.js 含未清理占位文本: {match.group(0)}")

    node = shutil.which("node")
    runtime_file = directory / "diagram-runtime.js"
    if runtime_file.is_file():
        try:
            runtime_text = runtime_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            add(result, "errors", f"无法读取 diagram-runtime.js: {exc}")
        else:
            for marker in ("buildFlowchart", "buildSequence", "renderMermaid", "renderArchitecture"):
                if marker not in runtime_text:
                    add(result, "errors", f"diagram-runtime.js 缺少图形运行时入口: {marker}")
            for marker in ("createMermaidViewport", "zoomAt", "toggleFullscreen", "ResizeObserver"):
                if marker not in runtime_text:
                    add(result, "errors", f"diagram-runtime.js 缺少 Mermaid 视图控制能力: {marker}")
            if "mermaid.render" not in runtime_text:
                add(result, "errors", "diagram-runtime.js 未显式调用 mermaid.render")
            if "cytoscape" not in runtime_text:
                add(result, "errors", "diagram-runtime.js 未发现 Cytoscape.js 架构图实现")
            for marker in ("layerTint", "routing", "keyboardListSummary", "sweeps"):
                if marker not in runtime_text:
                    add(result, "warnings", f"diagram-runtime.js 未使用推荐的可读架构图布局能力: {marker}")

    diagram_theme_file = directory / "diagram-theme.css"
    if diagram_theme_file.is_file():
        try:
            diagram_theme_text = diagram_theme_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            add(result, "errors", f"无法读取 diagram-theme.css: {exc}")
        else:
            for marker in (".mermaid-viewport", ".mermaid-stage", ":fullscreen", ".is-pseudo-fullscreen"):
                if marker not in diagram_theme_text:
                    add(result, "errors", f"diagram-theme.css 缺少 Mermaid 缩放或全屏样式: {marker}")
            if ".architecture-keyboard-grid" not in diagram_theme_text:
                add(result, "warnings", "diagram-theme.css 未发现可折叠架构键盘导航布局: .architecture-keyboard-grid")

    openapi_runtime_file = directory / "openapi-runtime.js"
    if openapi_runtime_file.is_file():
        try:
            openapi_runtime_text = openapi_runtime_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            add(result, "errors", f"无法读取 openapi-runtime.js: {exc}")
        else:
            for marker in ("SwaggerUIBundle", "openapi.json", "focusOperation"):
                if marker not in openapi_runtime_text:
                    add(result, "errors", f"openapi-runtime.js 缺少 Swagger UI 运行时入口: {marker}")

    if node:
        for filename in ("app.js", "architecture-data.js", "diagram-runtime.js", "openapi-runtime.js"):
            path = directory / filename
            if not path.is_file():
                continue
            process = subprocess.run(
                [node, "--check", str(path)], capture_output=True, text=True, check=False
            )
            if process.returncode:
                details = (process.stderr or process.stdout).strip()
                add(result, "errors", f"{filename} JavaScript 语法检查失败: {details}")
    else:
        add(result, "warnings", "未找到 node，跳过 JavaScript 语法检查")

    for filename in ("styles.css", "diagram-theme.css", "app.js", "diagram-runtime.js", "openapi-runtime.js"):
        path = directory / filename
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            for match in PLACEHOLDER_RE.finditer(text):
                add(result, "errors", f"{filename} 含未清理占位文本: {match.group(0)}")
            if filename == "styles.css":
                for marker in (".design-table", ".glossary-table"):
                    if marker not in text:
                        add(result, "warnings", f"styles.css 未发现推荐的业务名词 Table 样式: {marker}")
    return result


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="architecture-validator-") as temp:
        root = Path(temp)
        sections = "".join(f'<section id="{item}"></section>' for item in CANONICAL_SECTION_IDS)
        (root / "index.html").write_text(
            f'<!doctype html><link rel="stylesheet" href="styles.css">'
            f'<link rel="stylesheet" href="diagram-theme.css">{sections}'
            '<a href="api.html#api-demo">API</a><script src="architecture-data.js"></script>'
            '<script src="vendor/mermaid.min.js"></script><script src="vendor/cytoscape.min.js"></script>'
            '<script src="diagram-runtime.js"></script>'
            '<script src="app.js"></script>', encoding="utf-8"
        )
        (root / "api.html").write_text(
            '<!doctype html><link rel="stylesheet" href="styles.css">'
            '<link rel="stylesheet" href="vendor/swagger-ui.css"><main id="swagger-ui"></main>'
            '<script src="vendor/swagger-ui-bundle.js"></script>'
            '<script src="vendor/swagger-ui-standalone-preset.js"></script>'
            '<script src="openapi-runtime.js"></script>'
            '<script>ArchitectureApiDocs.render({specUrl:"./openapi.json"});</script>', encoding="utf-8"
        )
        (root / "styles.css").write_text("body { margin: 0; }", encoding="utf-8")
        (root / "diagram-theme.css").write_text(
            ".diagram-surface { min-height: 20rem; } .mermaid-viewport{} .mermaid-stage{} "
            ".mermaid-viewer:fullscreen{} .is-pseudo-fullscreen{}", encoding="utf-8"
        )
        (root / "app.js").write_text("void 0;", encoding="utf-8")
        (root / "diagram-runtime.js").write_text(
            "function buildFlowchart(){} function buildSequence(){} function renderMermaid(){mermaid.render()} "
            "function createMermaidViewport(){ResizeObserver} function zoomAt(){} function toggleFullscreen(){} "
            "function renderArchitecture(){cytoscape()}", encoding="utf-8"
        )
        (root / "architecture-data.js").write_text(
            'window.ARCHITECTURE_DATA = Object.freeze({meta:{openapiUrl:"./openapi.json"},'
            'modules:[{id:"module-demo",apiOperationIds:["api-demo"]}]});', encoding="utf-8"
        )
        (root / "openapi.json").write_text(
            json.dumps({
                "openapi": "3.1.0",
                "info": {"title": "Demo API", "version": "0.1.0"},
                "paths": {"/demo": {"get": {
                    "operationId": "api-demo",
                    "summary": "Demo",
                    "tags": ["Demo"],
                    "responses": {"200": {"description": "OK"}},
                    "x-architecture": {"moduleId": "module-demo"},
                }}},
                "x-pending-interfaces": [],
            }), encoding="utf-8"
        )
        (root / "openapi-runtime.js").write_text(
            'void SwaggerUIBundle; void "openapi.json"; function focusOperation(){}', encoding="utf-8"
        )
        (root / "vendor").mkdir()
        (root / "vendor" / "mermaid.min.js").write_text("void 0;", encoding="utf-8")
        (root / "vendor" / "cytoscape.min.js").write_text("void 0;", encoding="utf-8")
        (root / "vendor" / "swagger-ui.css").write_text(".swagger-ui {}", encoding="utf-8")
        (root / "vendor" / "swagger-ui.css.map").write_text("{}", encoding="utf-8")
        (root / "vendor" / "swagger-ui-bundle.js").write_text("void 0;", encoding="utf-8")
        (root / "vendor" / "swagger-ui-bundle.js.map").write_text("{}", encoding="utf-8")
        (root / "vendor" / "swagger-ui-standalone-preset.js").write_text("void 0;", encoding="utf-8")
        (root / "vendor" / "swagger-ui-standalone-preset.js.map").write_text("{}", encoding="utf-8")
        (root / "vendor" / "swagger-ui-LICENSE.txt").write_text("Apache-2.0", encoding="utf-8")
        (root / "vendor" / "swagger-ui-NOTICE.txt").write_text("NOTICE", encoding="utf-8")
        (root / "vendor" / "LICENSES.txt").write_text("MIT", encoding="utf-8")
        result = validate(root)
        if result.get("errors"):
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1
        (root / "index.html").write_text(
            (root / "index.html").read_text(encoding="utf-8") + '<div id="overview"></div>',
            encoding="utf-8",
        )
        negative_result = validate(root)
        if not any("重复 ID: overview" in item for item in negative_result.get("errors", [])):
            print("self-test failed: duplicate ID was not detected")
            return 1
        openapi_document = json.loads((root / "openapi.json").read_text(encoding="utf-8"))
        openapi_document["paths"]["/demo"]["get"]["responses"]["200"]["content"] = {
            "application/json": {"schema": {"$ref": "#/components/schemas/Missing"}}
        }
        (root / "openapi.json").write_text(json.dumps(openapi_document), encoding="utf-8")
        openapi_negative_result = validate(root)
        if not any("本地 $ref 无法解析" in item for item in openapi_negative_result.get("errors", [])):
            print("self-test failed: broken OpenAPI $ref was not detected")
            return 1
    print("self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, help="架构设计输出目录")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    parser.add_argument("--self-test", action="store_true", help="运行内置自测")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.directory is None:
        parser.error("需要输出目录，或使用 --self-test")
    result = validate(args.directory.resolve())
    errors = result.get("errors", [])
    warnings = result.get("warnings", [])
    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    else:
        for label, items in (("ERROR", errors), ("WARN", warnings)):
            for item in items:
                print(f"[{label}] {item}")
        print(f"validation complete: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
