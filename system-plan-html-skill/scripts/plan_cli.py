#!/usr/bin/env python3
"""CLI for project plan Excel workbooks and HTML dashboards."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dashboard import build_dashboard
from plan_store import (
    DICTIONARIES,
    PlanError,
    WorkbookLock,
    add_issue,
    add_milestone,
    add_task,
    clean_text,
    close_issue,
    create_workbook,
    default_project_id,
    find_record,
    load_plan,
    now_iso,
    parse_date,
    project_completion,
    records,
    save_plan,
    serializable,
    update_issue,
    update_milestone,
    update_progress,
    update_task,
    validate_or_raise,
    validate_workbook,
)


def actor(value: str | None) -> str:
    return clean_text(value) or clean_text(os.environ.get("PLAN_ACTOR")) or clean_text(os.environ.get("USER")) or "User"


def result(action: str, workbook: str | None, data: Any = None, warnings=None, errors=None, ok: bool = True):
    return {
        "ok": ok,
        "action": action,
        "workbook": str(Path(workbook).expanduser().resolve()) if workbook else None,
        "timestamp": now_iso(),
        "data": data if data is not None else {},
        "warnings": warnings or [],
        "errors": errors or [],
    }


def emit(payload: dict[str, Any], json_mode: bool):
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=serializable))
        return
    if payload["ok"]:
        print(f"成功：{payload['action']}")
        data = payload.get("data") or {}
        if isinstance(data, dict):
            for key, value in data.items():
                if key.startswith("_") or isinstance(value, (dict, list)):
                    continue
                print(f"  {key}: {serializable(value)}")
            if isinstance(data.get("items"), list):
                for item in data["items"]:
                    print("  - " + " | ".join(f"{k}={serializable(v)}" for k, v in item.items() if k != "_row" and v not in (None, "")))
        for warning in payload.get("warnings", []):
            print(f"警告：{warning.get('message', warning)}", file=sys.stderr)
    else:
        for error in payload.get("errors", []):
            print(f"错误 [{error.get('code', 'ERROR')}]：{error.get('message', error)}", file=sys.stderr)


def add_common_workbook(parser):
    parser.add_argument("--workbook", required=True, help="项目计划 Excel 工作簿路径")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plan", description="Excel 项目开发计划与进度管理工具")
    parser.add_argument("--json", action="store_true", help="输出稳定 JSON，供 Agent 或程序调用")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="初始化项目计划工作簿")
    add_common_workbook(init)
    init.add_argument("--project-name", required=True)
    init.add_argument("--owner", required=True, help="项目经理")
    init.add_argument("--start", required=True)
    init.add_argument("--end", required=True)
    init.add_argument("--project-id")
    init.add_argument("--business-owner", default="")
    init.add_argument("--priority", choices=DICTIONARIES["priority"], default="P1")
    init.add_argument("--force", action="store_true")

    project = sub.add_parser("project", help="项目操作")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    project_show = project_sub.add_parser("show", help="查看项目概况")
    add_common_workbook(project_show)
    project_show.add_argument("--project")

    task = sub.add_parser("task", help="任务操作")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_add = task_sub.add_parser("add", help="新增任务")
    add_common_workbook(task_add)
    task_add.add_argument("--project")
    task_add.add_argument("--name", required=True)
    task_add.add_argument("--owner", required=True)
    task_add.add_argument("--start", required=True)
    task_add.add_argument("--end", required=True)
    task_add.add_argument("--parent", default="")
    task_add.add_argument("--wbs")
    task_add.add_argument("--type", choices=DICTIONARIES["task_type"], default="任务")
    task_add.add_argument("--phase", default="")
    task_add.add_argument("--contributors", default="")
    task_add.add_argument("--effort-days", type=float, default=0)
    task_add.add_argument("--dependencies", default="")
    task_add.add_argument("--deliverable", default="")
    task_add.add_argument("--acceptance", default="")
    task_add.add_argument("--milestone", action="store_true")
    task_add.add_argument("--remark", default="")
    task_add.add_argument("--updated-by")

    task_update = task_sub.add_parser("update", help="修改任务和重新排期")
    add_common_workbook(task_update)
    task_update.add_argument("--task", required=True)
    task_update.add_argument("--name")
    task_update.add_argument("--owner")
    task_update.add_argument("--parent")
    task_update.add_argument("--phase")
    task_update.add_argument("--type", choices=DICTIONARIES["task_type"])
    task_update.add_argument("--start")
    task_update.add_argument("--end")
    task_update.add_argument("--forecast-start")
    task_update.add_argument("--forecast-end")
    task_update.add_argument("--effort-days", type=float)
    task_update.add_argument("--dependencies")
    task_update.add_argument("--deliverable")
    task_update.add_argument("--acceptance")
    task_update.add_argument("--health", choices=DICTIONARIES["health"])
    task_update.add_argument("--remark")
    task_update.add_argument("--reason", default="")
    task_update.add_argument("--updated-by")

    task_list = task_sub.add_parser("list", help="列出和筛选任务")
    add_common_workbook(task_list)
    task_list.add_argument("--project")
    task_list.add_argument("--status", choices=DICTIONARIES["task_status"])
    task_list.add_argument("--owner")
    task_list.add_argument("--phase")

    progress = sub.add_parser("progress", help="进度操作")
    progress_sub = progress.add_subparsers(dest="progress_command", required=True)
    progress_update = progress_sub.add_parser("update", help="更新任务进度并追加日志")
    add_common_workbook(progress_update)
    progress_update.add_argument("--task", required=True)
    progress_update.add_argument("--percent", required=True, type=int)
    progress_update.add_argument("--status", choices=DICTIONARIES["task_status"])
    progress_update.add_argument("--date")
    progress_update.add_argument("--completed", default="")
    progress_update.add_argument("--next", default="")
    progress_update.add_argument("--blockers", default="")
    progress_update.add_argument("--clear-blocker", action="store_true", help="清除任务阻塞标记")
    progress_update.add_argument("--evidence", default="")
    progress_update.add_argument("--actual-start")
    progress_update.add_argument("--actual-end")
    progress_update.add_argument("--updater")
    progress_update.add_argument("--remark", default="")

    milestone = sub.add_parser("milestone", help="里程碑操作")
    milestone_sub = milestone.add_subparsers(dest="milestone_command", required=True)
    milestone_add = milestone_sub.add_parser("add", help="新增里程碑")
    add_common_workbook(milestone_add)
    milestone_add.add_argument("--project")
    milestone_add.add_argument("--name", required=True)
    milestone_add.add_argument("--date", required=True)
    milestone_add.add_argument("--owner", default="")
    milestone_add.add_argument("--type", default="交付")
    milestone_add.add_argument("--tasks", default="")
    milestone_add.add_argument("--acceptance", default="")
    milestone_add.add_argument("--remark", default="")
    milestone_add.add_argument("--updated-by")

    milestone_update = milestone_sub.add_parser("update", help="修改里程碑")
    add_common_workbook(milestone_update)
    milestone_update.add_argument("--milestone", required=True)
    milestone_update.add_argument("--date")
    milestone_update.add_argument("--forecast-date")
    milestone_update.add_argument("--actual-date")
    milestone_update.add_argument("--status", choices=DICTIONARIES["milestone_status"])
    milestone_update.add_argument("--owner")
    milestone_update.add_argument("--risk-note")
    milestone_update.add_argument("--reason", default="")
    milestone_update.add_argument("--updated-by")

    issue = sub.add_parser("issue", help="风险、问题和阻塞操作")
    issue_sub = issue.add_subparsers(dest="issue_command", required=True)
    issue_add = issue_sub.add_parser("add", help="新增风险问题")
    add_common_workbook(issue_add)
    issue_add.add_argument("--project")
    issue_add.add_argument("--task")
    issue_add.add_argument("--type", required=True, choices=DICTIONARIES["item_type"])
    issue_add.add_argument("--title", required=True)
    issue_add.add_argument("--severity", required=True, choices=DICTIONARIES["severity"])
    issue_add.add_argument("--owner", required=True)
    issue_add.add_argument("--description", default="")
    issue_add.add_argument("--impact", default="")
    issue_add.add_argument("--probability", choices=DICTIONARIES["probability"], default="中")
    issue_add.add_argument("--due-date")
    issue_add.add_argument("--mitigation", default="")
    issue_add.add_argument("--remark", default="")
    issue_add.add_argument("--updated-by")

    issue_update = issue_sub.add_parser("update", help="修改风险问题")
    add_common_workbook(issue_update)
    issue_update.add_argument("--issue", required=True)
    issue_update.add_argument("--status", choices=DICTIONARIES["item_status"])
    issue_update.add_argument("--owner")
    issue_update.add_argument("--severity", choices=DICTIONARIES["severity"])
    issue_update.add_argument("--probability", choices=DICTIONARIES["probability"])
    issue_update.add_argument("--due-date")
    issue_update.add_argument("--mitigation")
    issue_update.add_argument("--resolution")
    issue_update.add_argument("--reason", default="")
    issue_update.add_argument("--updated-by")

    issue_close = issue_sub.add_parser("close", help="关闭风险问题")
    add_common_workbook(issue_close)
    issue_close.add_argument("--issue", required=True)
    issue_close.add_argument("--resolution", required=True)
    issue_close.add_argument("--date")
    issue_close.add_argument("--updated-by")

    validate = sub.add_parser("validate", help="校验计划工作簿")
    add_common_workbook(validate)
    validate.add_argument("--strict", action="store_true")

    dashboard = sub.add_parser("dashboard", help="HTML 看板操作")
    dashboard_sub = dashboard.add_subparsers(dest="dashboard_command", required=True)
    dashboard_build = dashboard_sub.add_parser("build", help="生成静态 HTML 看板")
    add_common_workbook(dashboard_build)
    dashboard_build.add_argument("--output", required=True)
    dashboard_build.add_argument("--project")
    dashboard_build.add_argument("--title")
    return parser


def write_operation(workbook_path: str, callback):
    with WorkbookLock(workbook_path):
        wb = load_plan(workbook_path)
        data = callback(wb)
        validate_or_raise(wb)
        save_plan(wb, workbook_path)
        return data


def run(args) -> tuple[dict[str, Any], int]:
    command = args.command
    if command == "init":
        data = create_workbook(
            args.workbook, args.project_name, args.owner,
            parse_date(args.start, "start", False), parse_date(args.end, "end", False),
            args.project_id, args.business_owner, args.priority, args.force,
        )
        return result("init", args.workbook, data), 0

    if command == "project" and args.project_command == "show":
        wb = load_plan(args.workbook)
        project_id = default_project_id(wb, args.project)
        project = find_record(wb, "项目", project_id)
        data = {key: serializable(value) for key, value in project.items() if key != "_row"}
        data["overall_percent"] = project_completion(wb, project_id)
        data["task_count"] = sum(1 for item in records(wb, "任务") if clean_text(item["project_id"]) == project_id)
        return result("project.show", args.workbook, data), 0

    if command == "task" and args.task_command == "add":
        def operation(wb):
            project_id = default_project_id(wb, args.project)
            return add_task(wb, project_id, {
                "task_name": args.name, "owner": args.owner, "planned_start": args.start,
                "planned_end": args.end, "parent_task_id": args.parent, "wbs_code": args.wbs,
                "task_type": args.type, "phase": args.phase, "contributors": args.contributors,
                "effort_days": args.effort_days, "dependency_task_ids": args.dependencies,
                "deliverable": args.deliverable, "acceptance_criteria": args.acceptance,
                "milestone_flag": args.milestone, "remark": args.remark,
                "last_updated_by": actor(args.updated_by),
            })
        data = write_operation(args.workbook, operation)
        return result("task.add", args.workbook, {k: serializable(v) for k, v in data.items() if k != "_row"}), 0

    if command == "task" and args.task_command == "update":
        field_map = {
            "name": "task_name", "owner": "owner", "parent": "parent_task_id", "phase": "phase",
            "type": "task_type", "start": "planned_start", "end": "planned_end",
            "forecast_start": "forecast_start", "forecast_end": "forecast_end", "effort_days": "effort_days",
            "dependencies": "dependency_task_ids", "deliverable": "deliverable", "acceptance": "acceptance_criteria",
            "health": "health", "remark": "remark",
        }
        updates = {target: getattr(args, source) for source, target in field_map.items() if getattr(args, source) is not None}
        data = write_operation(args.workbook, lambda wb: update_task(wb, args.task, updates, args.reason, actor(args.updated_by)))
        return result("task.update", args.workbook, {k: serializable(v) for k, v in data.items() if not k.startswith("_")}), 0

    if command == "task" and args.task_command == "list":
        wb = load_plan(args.workbook)
        project_id = default_project_id(wb, args.project)
        items = []
        for item in records(wb, "任务"):
            if clean_text(item["project_id"]) != project_id:
                continue
            if args.status and clean_text(item["task_status"]) != args.status:
                continue
            if args.owner and clean_text(item["owner"]) != args.owner:
                continue
            if args.phase and clean_text(item["phase"]) != args.phase:
                continue
            items.append({key: serializable(item.get(key)) for key in ["task_id", "wbs_code", "task_name", "phase", "owner", "planned_start", "planned_end", "percent_complete", "task_status", "health"]})
        return result("task.list", args.workbook, {"project_id": project_id, "count": len(items), "items": items}), 0

    if command == "progress" and args.progress_command == "update":
        data = write_operation(args.workbook, lambda wb: update_progress(wb, args.task, {
            "percent_complete": args.percent, "task_status": args.status, "update_date": args.date,
            "work_completed": args.completed, "next_steps": args.next, "blockers": args.blockers,
            "clear_blocker": args.clear_blocker,
            "evidence_link": args.evidence, "actual_start": args.actual_start, "actual_end": args.actual_end,
            "updater": actor(args.updater), "remark": args.remark,
        }))
        return result("progress.update", args.workbook, {k: serializable(v) for k, v in data.items()}), 0

    if command == "milestone" and args.milestone_command == "add":
        def operation(wb):
            project_id = default_project_id(wb, args.project)
            return add_milestone(wb, project_id, {
                "milestone_name": args.name, "planned_date": args.date, "owner": args.owner,
                "milestone_type": args.type, "related_task_ids": args.tasks,
                "acceptance_condition": args.acceptance, "remark": args.remark,
                "last_updated_by": actor(args.updated_by),
            })
        data = write_operation(args.workbook, operation)
        return result("milestone.add", args.workbook, {k: serializable(v) for k, v in data.items()}), 0

    if command == "milestone" and args.milestone_command == "update":
        updates = {
            "planned_date": args.date, "forecast_date": args.forecast_date, "actual_date": args.actual_date,
            "milestone_status": args.status, "owner": args.owner, "risk_note": args.risk_note,
        }
        data = write_operation(args.workbook, lambda wb: update_milestone(wb, args.milestone, updates, args.reason, actor(args.updated_by)))
        return result("milestone.update", args.workbook, {k: serializable(v) for k, v in data.items() if not k.startswith("_")}), 0

    if command == "issue" and args.issue_command == "add":
        def operation(wb):
            project_id = default_project_id(wb, args.project)
            return add_issue(wb, project_id, {
                "task_id": args.task, "item_type": args.type, "title": args.title,
                "severity": args.severity, "owner": args.owner, "description": args.description,
                "impact": args.impact, "probability": args.probability, "due_date": args.due_date,
                "mitigation": args.mitigation, "remark": args.remark,
                "last_updated_by": actor(args.updated_by),
            })
        data = write_operation(args.workbook, operation)
        return result("issue.add", args.workbook, {k: serializable(v) for k, v in data.items()}), 0

    if command == "issue" and args.issue_command == "update":
        updates = {
            "item_status": args.status, "owner": args.owner, "severity": args.severity,
            "probability": args.probability, "due_date": args.due_date, "mitigation": args.mitigation,
            "resolution": args.resolution,
        }
        data = write_operation(args.workbook, lambda wb: update_issue(wb, args.issue, updates, args.reason, actor(args.updated_by)))
        return result("issue.update", args.workbook, {k: serializable(v) for k, v in data.items() if not k.startswith("_")}), 0

    if command == "issue" and args.issue_command == "close":
        data = write_operation(args.workbook, lambda wb: close_issue(
            wb, args.issue, args.resolution, parse_date(args.date or None, "date") or __import__("datetime").date.today(), actor(args.updated_by)
        ))
        return result("issue.close", args.workbook, {k: serializable(v) for k, v in data.items() if not k.startswith("_")}), 0

    if command == "validate":
        wb = load_plan(args.workbook)
        issues = validate_workbook(wb)
        errors = [item for item in issues if item["severity"] == "error"]
        warnings = [item for item in issues if item["severity"] == "warning"]
        ok = not errors and (not args.strict or not warnings)
        payload = result("validate", args.workbook, {
            "error_count": len(errors), "warning_count": len(warnings), "issues": issues,
        }, warnings=warnings, errors=errors, ok=ok)
        return payload, 0 if ok else 2

    if command == "dashboard" and args.dashboard_command == "build":
        wb = load_plan(args.workbook)
        issues = validate_workbook(wb)
        errors = [item for item in issues if item["severity"] == "error"]
        if errors:
            raise PlanError("VALIDATION_FAILED", f"工作簿存在 {len(errors)} 个错误，不能生成看板：{errors[0]['message']}")
        data = build_dashboard(wb, args.workbook, args.output, args.project, args.title)
        warnings = [item for item in issues if item["severity"] == "warning"]
        return result("dashboard.build", args.workbook, data, warnings=warnings), 0

    raise PlanError("UNKNOWN_COMMAND", "无法识别命令")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in argv
    argv = [arg for arg in argv if arg != "--json"]
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        args.json = json_mode
        payload, exit_code = run(args)
        emit(payload, json_mode)
        return exit_code
    except PlanError as exc:
        workbook = None
        for index, value in enumerate(argv):
            if value == "--workbook" and index + 1 < len(argv):
                workbook = argv[index + 1]
                break
        payload = result("error", workbook, errors=[exc.as_dict()], ok=False)
        emit(payload, json_mode)
        return exc.exit_code
    except KeyboardInterrupt:
        payload = result("error", None, errors=[{"code": "INTERRUPTED", "message": "操作已中断"}], ok=False)
        emit(payload, json_mode)
        return 130
    except Exception as exc:
        payload = result("error", None, errors=[{"code": "RUNTIME_ERROR", "message": str(exc)}], ok=False)
        emit(payload, json_mode)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
