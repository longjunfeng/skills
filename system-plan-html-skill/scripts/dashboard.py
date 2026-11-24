#!/usr/bin/env python3
"""Build the offline HTML dashboard from an Excel plan workbook."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from plan_store import clean_text, now_iso, workbook_snapshot


def build_dashboard(wb, workbook_path: str | Path, output_dir: str | Path, project_id: str | None = None, title: str | None = None) -> dict[str, Any]:
    source = Path(workbook_path).expanduser().resolve()
    output = Path(output_dir).expanduser().resolve()
    template_dir = Path(__file__).resolve().parent.parent / "assets" / "dashboard-template"
    required = ["index.html", "styles.css", "app.js"]
    missing = [name for name in required if not (template_dir / name).exists()]
    if missing:
        raise RuntimeError(f"看板模板缺失：{', '.join(missing)}")

    snapshot = workbook_snapshot(wb, project_id)
    projects = snapshot["projects"]
    project = projects[0] if projects else {}
    data = {
        "meta": {
            "schema_version": "1.0",
            "generated_at": now_iso(),
            "source_file": source.name,
            "title": title or clean_text(project.get("project_name")) or "项目开发计划和进度",
        },
        **snapshot,
    }

    output.mkdir(parents=True, exist_ok=True)
    for name in required:
        shutil.copy2(template_dir / name, output / name)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
    (output / "plan-data.js").write_text(
        f"window.PLAN_DATA = Object.freeze({payload});\n",
        encoding="utf-8",
    )
    return {
        "output": str(output),
        "files": [str(output / name) for name in ["index.html", "styles.css", "app.js", "plan-data.js"]],
        "project_id": snapshot["project_id"],
        "task_count": len(snapshot["tasks"]),
        "milestone_count": len(snapshot["milestones"]),
        "open_issue_count": sum(1 for item in snapshot["issues"] if item.get("item_status") not in {"已解决", "已关闭"}),
        "overall_percent": snapshot["overall_percent"],
    }
