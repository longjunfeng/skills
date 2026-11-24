#!/usr/bin/env python3
"""Validate a static architecture HTML delivery that uses Archify diagrams."""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

REQUIRED = ("index.html", "api.html", "openapi.json", "styles.css", "app.js", "architecture-data.js", "openapi-runtime.js", "vendor/swagger-ui.css", "vendor/swagger-ui-bundle.js", "vendor/swagger-ui-standalone-preset.js")
SECTIONS = ("overview", "architecture", "technology-operations", "flows", "sequences", "er-diagram", "api-catalog", "glossary", "decisions", "risks")
METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
TYPES = {"architecture", "workflow", "sequence", "dataflow", "lifecycle"}
ID_RE = re.compile(r"\bid\s*:\s*(['\"])([^'\"]+)\1")
API_RE = re.compile(r"\bapiOperationId\s*:\s*(['\"])([^'\"]+)\1")
DIAGRAM_RE = re.compile(r"(['\"])(archify/[^'\"]+\.(?:json|html))\1", re.I)

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.ids=[]; self.hrefs=[]; self.resources=[]
    def handle_starttag(self, tag, attrs):
        values=dict(attrs)
        if values.get("id"): self.ids.append(values["id"])
        if tag == "a" and values.get("href"): self.hrefs.append(values["href"])
        if tag in {"script", "iframe", "link"} and values.get("src", values.get("href")): self.resources.append(values.get("src", values.get("href")))

def local(raw):
    p=urlsplit(raw)
    return None if p.scheme or p.netloc or raw.startswith(("mailto:", "tel:", "javascript:")) else unquote(p.path)

def openapi(path, errors, warnings):
    try: doc=json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc: errors.append(f"openapi.json 无法解析: {exc}"); return set()
    if not isinstance(doc, dict) or not str(doc.get("openapi", "")).startswith("3."): errors.append("openapi.json 必须声明 OpenAPI 3.x")
    ids=[]
    for route,item in (doc.get("paths") or {}).items():
        if not isinstance(route,str) or not route.startswith("/") or not isinstance(item,dict): errors.append(f"无效 OpenAPI Path: {route}"); continue
        for method,op in item.items():
            if method.lower() not in METHODS or not isinstance(op,dict): continue
            oid=op.get("operationId")
            if not isinstance(oid,str) or not oid.startswith("api-"): errors.append(f"{method.upper()} {route} 缺少 api- 前缀 operationId"); continue
            ids.append(oid)
            if not op.get("responses"): errors.append(f"Operation 缺少 responses: {oid}")
            if not isinstance(op.get("x-architecture"),dict): errors.append(f"Operation 缺少 x-architecture: {oid}")
            if not op.get("tags"): warnings.append(f"Operation 未分组: {oid}")
    for oid,count in Counter(ids).items():
        if count>1: errors.append(f"operationId 重复: {oid}")
    return set(ids)

def archify(directory, errors, warnings):
    root=directory/"archify"
    if not root.is_dir(): errors.append("缺少 archify/ 图册目录"); return
    specs=sorted(root.glob("*.json"))
    if not specs: errors.append("archify/ 中至少需要一个 Archify JSON")
    for spec in specs:
        try: doc=json.loads(spec.read_text(encoding="utf-8"))
        except Exception as exc: errors.append(f"Archify JSON 无法解析 {spec.name}: {exc}"); continue
        if doc.get("diagram_type") not in TYPES: errors.append(f"Archify diagram_type 无效: {spec.name}")
        meta=doc.get("meta")
        if not isinstance(meta,dict) or not meta.get("title"): errors.append(f"Archify 图缺少 meta.title: {spec.name}")
        if not isinstance(meta,dict) or meta.get("quality_profile") not in {"showcase","standard"}: errors.append(f"Archify 图缺少 quality_profile: {spec.name}")
        if not spec.with_suffix(".html").is_file(): errors.append(f"Archify JSON 缺少同名 HTML: {spec.name}")
        if isinstance(meta,dict) and not meta.get("repository"): warnings.append(f"Archify 图未声明仓库证据: {spec.name}")

def validate(directory):
    errors=[]; warnings=[]
    if not directory.is_dir(): return {"errors":[f"输出目录不存在: {directory}"],"warnings":[]}
    for name in REQUIRED:
        if not (directory/name).is_file(): errors.append(f"缺少必需文件: {name}")
    ops=openapi(directory/"openapi.json",errors,warnings) if (directory/"openapi.json").is_file() else set()
    pages={}
    for name in ("index.html","api.html"):
        path=directory/name
        if not path.is_file(): continue
        text=path.read_text(encoding="utf-8"); parser=Page(); parser.feed(text); pages[name]=parser
        for item,count in Counter(parser.ids).items():
            if count>1: errors.append(f"{name} 存在重复 ID: {item}")
        if re.search(r"(?:mermaid|cytoscape)(?:\.min)?\.(?:js|css)", text, re.I): errors.append(f"{name} 不得加载其他图形运行时")
        for resource in parser.resources:
            target=local(resource)
            if target and not (directory/target).is_file(): errors.append(f"{name} 引用不存在资源: {resource}")
    ids=set(pages.get("index.html",Page()).ids)
    for section in SECTIONS:
        if ids and section not in ids: warnings.append(f"index.html 缺少推荐区域 ID: {section}")
    data=directory/"architecture-data.js"
    if data.is_file():
        text=data.read_text(encoding="utf-8")
        if "ARCHITECTURE_DATA" not in text: errors.append("architecture-data.js 缺少 ARCHITECTURE_DATA")
        if not re.search(r"\bdiagramRefs\s*:",text): errors.append("architecture-data.js 缺少 diagramRefs")
        for value,count in Counter(m.group(2) for m in ID_RE.finditer(text)).items():
            if count>1: errors.append(f"architecture-data.js ID 重复: {value}")
        for match in API_RE.finditer(text):
            if match.group(2) not in ops: errors.append(f"引用不存在 operationId: {match.group(2)}")
        for match in DIAGRAM_RE.finditer(text):
            if not (directory/match.group(2)).is_file(): errors.append(f"引用不存在图册文件: {match.group(2)}")
    archify(directory,errors,warnings)
    node=shutil.which("node")
    if node:
        for name in ("app.js","architecture-data.js","openapi-runtime.js"):
            path=directory/name
            if path.is_file() and subprocess.run([node,"--check",str(path)],capture_output=True).returncode: errors.append(f"{name} JavaScript 语法检查失败")
    else: warnings.append("未找到 node，跳过 JavaScript 语法检查")
    return {"errors":errors,"warnings":warnings}

if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("directory",type=Path); parser.add_argument("--json",action="store_true"); args=parser.parse_args(); result=validate(args.directory.resolve())
    print(json.dumps(result,ensure_ascii=False,indent=2) if args.json else "\n".join(result["errors"]+result["warnings"]))
    sys.exit(1 if result["errors"] else 0)
