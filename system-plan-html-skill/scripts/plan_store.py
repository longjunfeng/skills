#!/usr/bin/env python3
"""Excel storage and validation for the project plan skill."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from contextlib import AbstractContextManager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.comments import Comment
    from openpyxl.formatting.rule import CellIsRule, DataBarRule, FormulaRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.table import Table, TableStyleInfo
except ImportError as exc:  # pragma: no cover - handled by launcher/CLI
    raise SystemExit(
        "缺少 openpyxl。请通过 scripts/plan 启动，或使用安装了 openpyxl 的 Python 运行 scripts/plan_cli.py。"
    ) from exc


SHEET_SCHEMAS: dict[str, dict[str, Any]] = {
    "项目": {
        "table": "tbl_projects",
        "key": "project_id",
        "fields": [
            "project_id", "project_name", "project_description", "business_owner",
            "project_manager", "priority", "project_status", "health", "planned_start",
            "planned_end", "actual_start", "actual_end", "current_phase", "overall_percent",
            "last_updated_at", "last_updated_by", "remark",
        ],
    },
    "任务": {
        "table": "tbl_tasks",
        "key": "task_id",
        "fields": [
            "task_id", "project_id", "parent_task_id", "wbs_code", "task_name", "task_type",
            "phase", "owner", "contributors", "planned_start", "planned_end", "baseline_start",
            "baseline_end", "forecast_start", "forecast_end", "actual_start", "actual_end",
            "effort_days", "percent_complete", "task_status", "health", "milestone_flag",
            "dependency_task_ids", "deliverable", "acceptance_criteria", "blocker_flag",
            "schedule_variance_days", "completion_weight", "last_progress_date",
            "last_updated_at", "last_updated_by", "remark",
        ],
    },
    "里程碑": {
        "table": "tbl_milestones",
        "key": "milestone_id",
        "fields": [
            "milestone_id", "project_id", "milestone_name", "milestone_type", "owner",
            "baseline_date", "planned_date", "forecast_date", "actual_date", "milestone_status",
            "acceptance_condition", "related_task_ids", "risk_note", "last_updated_at",
            "last_updated_by", "remark",
        ],
    },
    "进度日志": {
        "table": "tbl_progress_log",
        "key": "log_id",
        "fields": [
            "log_id", "project_id", "task_id", "update_date", "percent_before", "percent_after",
            "status_before", "status_after", "work_completed", "next_steps", "blockers",
            "evidence_link", "updater", "updated_at", "remark",
        ],
    },
    "风险问题": {
        "table": "tbl_risks",
        "key": "item_id",
        "fields": [
            "item_id", "project_id", "task_id", "item_type", "title", "description", "impact",
            "probability", "severity", "owner", "identified_date", "due_date", "item_status",
            "mitigation", "resolution", "closed_date", "last_updated_at", "last_updated_by", "remark",
        ],
    },
    "变更记录": {
        "table": "tbl_change_log",
        "key": "change_id",
        "fields": [
            "change_id", "project_id", "entity_type", "entity_id", "change_type", "field_name",
            "old_value", "new_value", "change_reason", "effective_date", "changed_by",
            "changed_at", "remark",
        ],
    },
    "字典": {
        "table": "tbl_dictionary",
        "key": "dict_type",
        "fields": ["dict_type", "dict_code", "dict_label", "sort_order", "enabled", "description"],
    },
}


FIELD_COMMENTS = {
    "project_id": "项目稳定唯一 ID",
    "task_id": "任务稳定唯一 ID",
    "parent_task_id": "父任务 ID；顶层任务留空",
    "dependency_task_ids": "前置任务 ID，多个使用英文逗号分隔",
    "percent_complete": "整数完成度，范围 0 到 100",
    "baseline_start": "首次确认的基线开始日期，普通修改不得覆盖",
    "baseline_end": "首次确认的基线结束日期，普通修改不得覆盖",
    "planned_start": "当前批准计划开始日期",
    "planned_end": "当前批准计划结束日期",
    "forecast_start": "根据当前情况预测的开始日期",
    "forecast_end": "根据当前情况预测的结束日期",
    "schedule_variance_days": "公式列：实际/预测结束日期相对计划结束日期的偏差天数",
    "completion_weight": "公式列：优先使用工作量，否则使用计划工期",
    "overall_percent": "公式列：项目任务加权整体完成度",
    "last_updated_at": "ISO 8601 格式的最后更新时间",
}


DICTIONARIES: dict[str, list[str]] = {
    "project_status": ["未开始", "进行中", "暂停", "已完成", "已取消"],
    "task_status": ["未开始", "进行中", "已完成", "延期", "阻塞", "取消"],
    "health": ["正常", "关注", "风险"],
    "priority": ["P0", "P1", "P2", "P3"],
    "task_type": ["阶段", "任务", "缺陷", "研究", "交付"],
    "milestone_status": ["未开始", "进行中", "已达成", "延期", "取消"],
    "item_type": ["风险", "问题", "阻塞"],
    "item_status": ["开放", "处理中", "已解决", "已关闭"],
    "probability": ["低", "中", "高"],
    "severity": ["低", "中", "高", "严重"],
    "yes_no": ["是", "否"],
}


VALIDATION_COLUMNS = {
    "项目": {"priority": "priority", "project_status": "project_status", "health": "health"},
    "任务": {
        "task_type": "task_type", "task_status": "task_status", "health": "health",
        "milestone_flag": "yes_no", "blocker_flag": "yes_no",
    },
    "里程碑": {"milestone_status": "milestone_status"},
    "风险问题": {
        "item_type": "item_type", "probability": "probability", "severity": "severity",
        "item_status": "item_status",
    },
}


DATE_FIELDS = {
    "planned_start", "planned_end", "actual_start", "actual_end", "baseline_start", "baseline_end",
    "forecast_start", "forecast_end", "baseline_date", "planned_date", "forecast_date", "actual_date",
    "update_date", "identified_date", "due_date", "closed_date", "effective_date", "last_progress_date",
}


class PlanError(Exception):
    def __init__(self, code: str, message: str, field: str | None = None, exit_code: int = 2):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.exit_code = exit_code

    def as_dict(self) -> dict[str, Any]:
        result = {"code": self.code, "message": self.message}
        if self.field:
            result["field"] = self.field
        return result


class WorkbookLock(AbstractContextManager):
    def __init__(self, workbook_path: str | Path):
        self.lock_path = Path(f"{Path(workbook_path).resolve()}.lock")
        self.fd: int | None = None

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            payload = json.dumps({"pid": os.getpid(), "created_at": now_iso()}, ensure_ascii=False)
            os.write(self.fd, payload.encode("utf-8"))
        except FileExistsError as exc:
            raise PlanError(
                "WORKBOOK_LOCKED",
                f"工作簿正在被其他进程使用，锁文件为 {self.lock_path}",
                exit_code=3,
            ) from exc
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.fd is not None:
            os.close(self.fd)
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass
        return False


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def today() -> date:
    return datetime.now().astimezone().date()


def parse_date(value: Any, field: str = "date", allow_none: bool = True) -> date | None:
    if value in (None, ""):
        if allow_none:
            return None
        raise PlanError("DATE_REQUIRED", f"字段 {field} 必须填写日期", field)
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise PlanError("INVALID_DATE", f"字段 {field} 的日期必须为 YYYY-MM-DD：{value}", field) from exc


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_id_list(value: Any) -> str:
    if not value:
        return ""
    parts = re.split(r"[,，\s]+", str(value).strip())
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        item = part.strip()
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ",".join(ordered)


def split_ids(value: Any) -> list[str]:
    normalized = normalize_id_list(value)
    return normalized.split(",") if normalized else []


def serializable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def column_letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _style_sheet(ws, fields: list[str], widths: dict[str, int] | None = None):
    navy = "172033"
    border_color = "D8E1EC"
    header_fill = PatternFill("solid", fgColor=navy)
    header_font = Font(color="FFFFFF", bold=True, size=10)
    thin_bottom = Border(bottom=Side(style="thin", color=border_color))

    ws.freeze_panes = "A2"
    ws.sheet_view.showGridLines = False
    ws.auto_filter.ref = f"A1:{column_letter(len(fields))}2"
    ws.row_dimensions[1].height = 30
    for idx, field in enumerate(fields, start=1):
        cell = ws.cell(1, idx, field)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_bottom
        if field in FIELD_COMMENTS:
            cell.comment = Comment(FIELD_COMMENTS[field], "Codex")
        width = (widths or {}).get(field, 16)
        ws.column_dimensions[column_letter(idx)].width = min(max(width, 11), 42)

    _style_data_row(ws, fields, 2)


def _style_data_row(ws, fields: list[str], row: int):
    ws.row_dimensions[row].height = 22
    for idx, field in enumerate(fields, start=1):
        cell = ws.cell(row, idx)
        cell.alignment = Alignment(
            horizontal="right" if field in {"effort_days", "percent_complete", "overall_percent", "schedule_variance_days", "completion_weight"} else "left",
            vertical="center",
            wrap_text=field in {"project_description", "deliverable", "acceptance_criteria", "description", "impact", "mitigation", "resolution", "remark", "work_completed", "next_steps", "blockers"},
        )
        if field in DATE_FIELDS:
            cell.number_format = "yyyy-mm-dd"
        elif field in {"overall_percent", "percent_complete"}:
            cell.number_format = '0"%"'
        elif field in {"effort_days", "schedule_variance_days", "completion_weight"}:
            cell.number_format = "0.0"


def _add_table(ws, schema: dict[str, Any]):
    fields = schema["fields"]
    for idx, field in enumerate(fields, start=1):
        ws.cell(1, idx, field)
    table = Table(displayName=schema["table"], ref=f"A1:{column_letter(len(fields))}2")
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False,
        showRowStripes=True, showColumnStripes=False,
    )
    ws.add_table(table)


def _add_validations(ws, fields: list[str], mapping: dict[str, str]):
    for field, dict_type in mapping.items():
        col = column_letter(fields.index(field) + 1)
        values = DICTIONARIES[dict_type]
        formula = '"' + ",".join(values) + '"'
        validation = DataValidation(type="list", formula1=formula, allow_blank=True)
        validation.error = f"请选择有效值：{', '.join(values)}"
        validation.errorTitle = "无效选项"
        validation.prompt = f"可选值：{', '.join(values)}"
        validation.promptTitle = field
        ws.add_data_validation(validation)
        validation.add(f"{col}2:{col}2000")


def _add_task_conditional_formatting(ws):
    fields = SHEET_SCHEMAS["任务"]["fields"]
    status_col = column_letter(fields.index("task_status") + 1)
    health_col = column_letter(fields.index("health") + 1)
    percent_col = column_letter(fields.index("percent_complete") + 1)
    blocker_col = column_letter(fields.index("blocker_flag") + 1)
    ws.conditional_formatting.add(
        f"{percent_col}2:{percent_col}2000",
        DataBarRule(start_type="num", start_value=0, end_type="num", end_value=100, color="2563EB"),
    )
    for text_value, color in [("已完成", "DCFCE7"), ("延期", "FEE2E2"), ("阻塞", "FECACA"), ("进行中", "DBEAFE")]:
        ws.conditional_formatting.add(
            f"{status_col}2:{status_col}2000",
            FormulaRule(formula=[f'{status_col}2="{text_value}"'], fill=PatternFill("solid", fgColor=color)),
        )
    for text_value, color in [("正常", "DCFCE7"), ("关注", "FEF3C7"), ("风险", "FEE2E2")]:
        ws.conditional_formatting.add(
            f"{health_col}2:{health_col}2000",
            FormulaRule(formula=[f'{health_col}2="{text_value}"'], fill=PatternFill("solid", fgColor=color)),
        )
    ws.conditional_formatting.add(
        f"{blocker_col}2:{blocker_col}2000",
        FormulaRule(formula=[f'{blocker_col}2="是"'], fill=PatternFill("solid", fgColor="FECACA")),
    )


def _build_instructions(ws):
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 88
    ws.merge_cells("A1:B1")
    ws["A1"] = "项目开发计划与进度工作簿"
    ws["A1"].font = Font(size=20, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="172033")
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 42

    rows = [
        ("定位", "Excel 是唯一业务数据源；HTML 看板由工具生成，不要在页面中直接维护数据。"),
        ("推荐操作", "通过 Skill 的 scripts/plan 命令新增、修改和更新进度，以保留校验、日志和变更审计。"),
        ("直接编辑", "可以人工编辑非公式字段；编辑后必须运行 plan validate，并重新生成 HTML 看板。"),
        ("基线", "baseline_* 字段记录首次批准计划。普通调整只修改 planned_* 或 forecast_*，并填写变更原因。"),
        ("进度", "percent_complete 使用 0 到 100 的整数。每次更新会追加到“进度日志”。"),
        ("关联", "父任务、依赖任务、里程碑关联任务均使用稳定 ID；多个 ID 使用英文逗号分隔。"),
        ("状态颜色", "绿色=完成/正常，蓝色=进行中，橙色=关注，红色=延期/阻塞/风险。"),
        ("初始化示例", 'scripts/plan init --workbook /path/project-plan.xlsx --project-name "项目" --owner "负责人" --start 2026-01-01 --end 2026-12-31'),
        ("新增任务", 'scripts/plan task add --workbook /path/project-plan.xlsx --name "接口设计" --owner "李四" --start 2026-01-02 --end 2026-01-10'),
        ("更新进度", 'scripts/plan progress update --workbook /path/project-plan.xlsx --task TASK-001 --percent 60 --completed "已完成接口定义"'),
        ("校验", "scripts/plan validate --workbook /path/project-plan.xlsx"),
        ("生成看板", "scripts/plan dashboard build --workbook /path/project-plan.xlsx --output /path/dashboard"),
    ]
    for row_idx, (label, value) in enumerate(rows, start=3):
        ws.cell(row_idx, 1, label)
        ws.cell(row_idx, 2, value)
        ws.cell(row_idx, 1).font = Font(bold=True, color="172033")
        ws.cell(row_idx, 1).fill = PatternFill("solid", fgColor="EFF6FF")
        ws.cell(row_idx, 1).alignment = Alignment(vertical="top")
        ws.cell(row_idx, 2).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[row_idx].height = 36 if len(value) > 55 else 26


def create_workbook(
    workbook_path: str | Path,
    project_name: str,
    owner: str,
    start: date,
    end: date,
    project_id: str | None = None,
    business_owner: str = "",
    priority: str = "P1",
    force: bool = False,
) -> dict[str, Any]:
    path = Path(workbook_path).expanduser().resolve()
    if not clean_text(project_name):
        raise PlanError("PROJECT_NAME_REQUIRED", "项目名称不能为空", "project_name")
    if not clean_text(owner):
        raise PlanError("OWNER_REQUIRED", "项目负责人不能为空", "owner")
    if path.exists() and not force:
        raise PlanError("WORKBOOK_EXISTS", f"工作簿已存在：{path}")
    if start > end:
        raise PlanError("INVALID_DATE_RANGE", "项目开始日期不能晚于结束日期", "planned_start")
    if priority not in DICTIONARIES["priority"]:
        raise PlanError("INVALID_ENUM", f"无效优先级：{priority}", "priority")

    path.parent.mkdir(parents=True, exist_ok=True)
    with WorkbookLock(path):
        wb = Workbook()
        instructions = wb.active
        instructions.title = "使用说明"
        _build_instructions(instructions)

        width_overrides = {
            "project_name": 24, "project_description": 34, "task_name": 30, "contributors": 22,
            "deliverable": 30, "acceptance_criteria": 34, "description": 36, "impact": 28,
            "mitigation": 34, "resolution": 34, "remark": 28, "work_completed": 34,
            "next_steps": 34, "blockers": 30, "evidence_link": 30, "old_value": 28,
            "new_value": 28, "change_reason": 34,
        }

        for sheet_name, schema in SHEET_SCHEMAS.items():
            ws = wb.create_sheet(sheet_name)
            _style_sheet(ws, schema["fields"], width_overrides)
            _add_table(ws, schema)
            if sheet_name in VALIDATION_COLUMNS:
                _add_validations(ws, schema["fields"], VALIDATION_COLUMNS[sheet_name])
            if sheet_name == "任务":
                _add_task_conditional_formatting(ws)

        dict_ws = wb["字典"]
        row = 2
        for dict_type, values in DICTIONARIES.items():
            for order, value in enumerate(values, start=1):
                data = [dict_type, value, value, order, "是", "系统内置枚举"]
                for col, item in enumerate(data, start=1):
                    dict_ws.cell(row, col, item)
                row += 1
        _resize_table(dict_ws, SHEET_SCHEMAS["字典"]["table"], row - 1)

        project_id = project_id or _new_project_id([])
        ts = now_iso()
        project_row = {
            "project_id": project_id,
            "project_name": project_name,
            "project_description": "",
            "business_owner": business_owner,
            "project_manager": owner,
            "priority": priority,
            "project_status": "未开始",
            "health": "正常",
            "planned_start": start,
            "planned_end": end,
            "actual_start": None,
            "actual_end": None,
            "current_phase": "",
            "overall_percent": None,
            "last_updated_at": ts,
            "last_updated_by": owner,
            "remark": "",
        }
        row_index = append_record(wb, "项目", project_row)
        _set_project_formula(wb["项目"], row_index)
        _atomic_save(wb, path)

    return {"project_id": project_id, "project_name": project_name, "path": str(path)}


def load_plan(workbook_path: str | Path):
    path = Path(workbook_path).expanduser().resolve()
    if not path.exists():
        raise PlanError("WORKBOOK_NOT_FOUND", f"工作簿不存在：{path}", exit_code=1)
    try:
        return load_workbook(path)
    except Exception as exc:
        raise PlanError("WORKBOOK_OPEN_FAILED", f"无法打开工作簿：{exc}", exit_code=1) from exc


def _atomic_save(wb, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".xlsx", dir=path.parent)
    os.close(fd)
    try:
        wb.calculation.fullCalcOnLoad = True
        wb.calculation.forceFullCalc = True
        wb.calculation.calcMode = "auto"
        wb.save(temp_name)
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def save_plan(wb, workbook_path: str | Path):
    _atomic_save(wb, Path(workbook_path).expanduser().resolve())


def _resize_table(ws, table_name: str, last_row: int):
    table = ws.tables[table_name]
    last_row = max(2, last_row)
    table.ref = f"A1:{column_letter(ws.max_column)}{last_row}"
    ws.auto_filter.ref = table.ref


def records(wb, sheet_name: str) -> list[dict[str, Any]]:
    if sheet_name not in wb.sheetnames:
        return []
    schema = SHEET_SCHEMAS[sheet_name]
    fields = schema["fields"]
    key = schema["key"]
    ws = wb[sheet_name]
    result: list[dict[str, Any]] = []
    for row_idx in range(2, ws.max_row + 1):
        row = {field: ws.cell(row_idx, col_idx + 1).value for col_idx, field in enumerate(fields)}
        if not clean_text(row.get(key)):
            continue
        row["_row"] = row_idx
        result.append(row)
    return result


def find_record(wb, sheet_name: str, entity_id: str) -> dict[str, Any]:
    key = SHEET_SCHEMAS[sheet_name]["key"]
    for record in records(wb, sheet_name):
        if clean_text(record.get(key)) == clean_text(entity_id):
            return record
    code = {
        "项目": "PROJECT_NOT_FOUND", "任务": "TASK_NOT_FOUND", "里程碑": "MILESTONE_NOT_FOUND",
        "风险问题": "ISSUE_NOT_FOUND",
    }.get(sheet_name, "RECORD_NOT_FOUND")
    raise PlanError(code, f"{sheet_name}记录不存在：{entity_id}", key)


def append_record(wb, sheet_name: str, data: dict[str, Any]) -> int:
    schema = SHEET_SCHEMAS[sheet_name]
    ws = wb[sheet_name]
    key = schema["key"]
    target_row = None
    for row_idx in range(2, ws.max_row + 1):
        if not clean_text(ws.cell(row_idx, 1).value):
            target_row = row_idx
            break
    target_row = target_row or ws.max_row + 1
    for col_idx, field in enumerate(schema["fields"], start=1):
        value = data.get(field)
        ws.cell(target_row, col_idx, value)
    _style_data_row(ws, schema["fields"], target_row)
    if sheet_name == "任务":
        _set_task_formulas(ws, target_row)
    _resize_table(ws, schema["table"], max(target_row, _last_data_row(ws, key)))
    return target_row


def _last_data_row(ws, key: str) -> int:
    key_col = SHEET_SCHEMAS[ws.title]["fields"].index(key) + 1
    for row_idx in range(ws.max_row, 1, -1):
        if clean_text(ws.cell(row_idx, key_col).value):
            return row_idx
    return 2


def update_record(wb, sheet_name: str, row_index: int, updates: dict[str, Any]):
    fields = SHEET_SCHEMAS[sheet_name]["fields"]
    ws = wb[sheet_name]
    for field, value in updates.items():
        if field not in fields:
            continue
        ws.cell(row_index, fields.index(field) + 1, value)
    if sheet_name == "任务":
        _set_task_formulas(ws, row_index)


def _set_task_formulas(ws, row: int):
    fields = SHEET_SCHEMAS["任务"]["fields"]
    variance_col = fields.index("schedule_variance_days") + 1
    weight_col = fields.index("completion_weight") + 1
    ws.cell(row, variance_col, f'=IF(T{row}="已完成",IF(Q{row}="","",Q{row}-K{row}),IF(O{row}<>"",O{row}-K{row},IF(AND(TODAY()>K{row},T{row}<>"取消"),TODAY()-K{row},0)))')
    ws.cell(row, weight_col, f'=IF(R{row}>0,R{row},MAX(1,K{row}-J{row}+1))')


def _set_project_formula(ws, row: int):
    fields = SHEET_SCHEMAS["项目"]["fields"]
    col = fields.index("overall_percent") + 1
    formula = (
        f'=IFERROR(SUMPRODUCT((\'任务\'!$B$2:$B$2000=A{row})*(\'任务\'!$S$2:$S$2000)*'
        f'(\'任务\'!$AB$2:$AB$2000)*(\'任务\'!$T$2:$T$2000<>"取消"))/'
        f'SUMPRODUCT((\'任务\'!$B$2:$B$2000=A{row})*(\'任务\'!$AB$2:$AB$2000)*'
        f'(\'任务\'!$T$2:$T$2000<>"取消")),0)'
    )
    ws.cell(row, col, formula)


def default_project_id(wb, requested: str | None = None) -> str:
    projects = records(wb, "项目")
    if requested:
        find_record(wb, "项目", requested)
        return requested
    if len(projects) == 1:
        return clean_text(projects[0]["project_id"])
    if not projects:
        raise PlanError("PROJECT_NOT_FOUND", "工作簿中没有项目记录", "project_id")
    raise PlanError("PROJECT_REQUIRED", "工作簿包含多个项目，请使用 --project 指定项目", "project_id")


def _new_project_id(existing: Iterable[str]) -> str:
    prefix = f"PRJ-{today().strftime('%Y%m')}-"
    return _next_id(existing, prefix, 3)


def next_entity_id(wb, sheet_name: str, prefix: str, digits: int = 3) -> str:
    key = SHEET_SCHEMAS[sheet_name]["key"]
    return _next_id((clean_text(r[key]) for r in records(wb, sheet_name)), prefix, digits)


def _next_id(existing: Iterable[str], prefix: str, digits: int) -> str:
    highest = 0
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    for value in existing:
        match = pattern.match(clean_text(value))
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{prefix}{highest + 1:0{digits}d}"


def next_daily_id(wb, sheet_name: str, prefix: str) -> str:
    day_prefix = f"{prefix}-{today().strftime('%Y%m%d')}-"
    return next_entity_id(wb, sheet_name, day_prefix, 3)


def next_wbs_code(wb, project_id: str, parent_task_id: str = "") -> str:
    tasks = [t for t in records(wb, "任务") if clean_text(t["project_id"]) == project_id]
    siblings = [t for t in tasks if clean_text(t.get("parent_task_id")) == clean_text(parent_task_id)]
    if parent_task_id:
        parent = find_record(wb, "任务", parent_task_id)
        base = clean_text(parent.get("wbs_code"))
        if not base:
            raise PlanError("PARENT_WBS_MISSING", f"父任务 {parent_task_id} 没有 WBS 编号", "parent_task_id")
        numbers = []
        pattern = re.compile(rf"^{re.escape(base)}\.(\d+)$")
    else:
        base = ""
        numbers = []
        pattern = re.compile(r"^(\d+)$")
    for task in siblings:
        match = pattern.match(clean_text(task.get("wbs_code")))
        if match:
            numbers.append(int(match.group(1)))
    next_num = max(numbers, default=0) + 1
    return f"{base}.{next_num}" if base else str(next_num)


def add_change(
    wb,
    project_id: str,
    entity_type: str,
    entity_id: str,
    change_type: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    reason: str,
    changed_by: str,
    remark: str = "",
):
    append_record(wb, "变更记录", {
        "change_id": next_daily_id(wb, "变更记录", "CHG"),
        "project_id": project_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "change_type": change_type,
        "field_name": field_name,
        "old_value": serializable(old_value),
        "new_value": serializable(new_value),
        "change_reason": reason,
        "effective_date": today(),
        "changed_by": changed_by,
        "changed_at": now_iso(),
        "remark": remark,
    })


def calculate_task(task: dict[str, Any], reference_date: date | None = None) -> dict[str, Any]:
    reference_date = reference_date or today()
    planned_start = parse_date(task.get("planned_start"), "planned_start")
    planned_end = parse_date(task.get("planned_end"), "planned_end")
    forecast_end = parse_date(task.get("forecast_end"), "forecast_end")
    actual_end = parse_date(task.get("actual_end"), "actual_end")
    status = clean_text(task.get("task_status"))
    effort = task.get("effort_days")
    try:
        effort_value = float(effort) if effort not in (None, "") else 0.0
    except (TypeError, ValueError):
        effort_value = 0.0
    if effort_value > 0:
        weight = effort_value
    elif planned_start and planned_end:
        weight = max(1, (planned_end - planned_start).days + 1)
    else:
        weight = 1
    variance = 0
    compare_end = actual_end if status == "已完成" else forecast_end
    if planned_end and compare_end:
        variance = (compare_end - planned_end).days
    elif planned_end and status not in {"已完成", "取消"} and reference_date > planned_end:
        variance = (reference_date - planned_end).days
    percent = task.get("percent_complete") or 0
    try:
        percent = int(float(percent))
    except (TypeError, ValueError):
        percent = 0
    return {
        "completion_weight": weight,
        "schedule_variance_days": variance,
        "is_late": variance > 0 or status == "延期",
        "percent_complete": percent,
    }


def project_completion(wb, project_id: str) -> float:
    numerator = 0.0
    denominator = 0.0
    for task in records(wb, "任务"):
        if clean_text(task.get("project_id")) != project_id or clean_text(task.get("task_status")) == "取消":
            continue
        calc = calculate_task(task)
        numerator += calc["percent_complete"] * calc["completion_weight"]
        denominator += calc["completion_weight"]
    return round(numerator / denominator, 1) if denominator else 0.0


def add_task(wb, project_id: str, values: dict[str, Any]) -> dict[str, Any]:
    find_record(wb, "项目", project_id)
    if not clean_text(values.get("task_name")):
        raise PlanError("TASK_NAME_REQUIRED", "任务名称不能为空", "task_name")
    if not clean_text(values.get("owner")):
        raise PlanError("OWNER_REQUIRED", "任务负责人不能为空", "owner")
    parent = clean_text(values.get("parent_task_id"))
    if parent:
        parent_record = find_record(wb, "任务", parent)
        if clean_text(parent_record.get("project_id")) != project_id:
            raise PlanError("PARENT_PROJECT_MISMATCH", "父任务不属于当前项目", "parent_task_id")
    dependencies = normalize_id_list(values.get("dependency_task_ids"))
    for dep in split_ids(dependencies):
        dep_record = find_record(wb, "任务", dep)
        if clean_text(dep_record.get("project_id")) != project_id:
            raise PlanError("DEPENDENCY_PROJECT_MISMATCH", f"依赖任务 {dep} 不属于当前项目", "dependency_task_ids")
    start = parse_date(values.get("planned_start"), "planned_start", allow_none=False)
    end = parse_date(values.get("planned_end"), "planned_end", allow_none=False)
    if start > end:
        raise PlanError("INVALID_DATE_RANGE", "任务开始日期不能晚于结束日期", "planned_start")
    task_type = clean_text(values.get("task_type")) or "任务"
    if task_type not in DICTIONARIES["task_type"]:
        raise PlanError("INVALID_ENUM", f"无效任务类型：{task_type}", "task_type")
    task_id = next_entity_id(wb, "任务", "TASK-", 3)
    ts = now_iso()
    updater = clean_text(values.get("last_updated_by")) or "User"
    data = {
        "task_id": task_id,
        "project_id": project_id,
        "parent_task_id": parent,
        "wbs_code": clean_text(values.get("wbs_code")) or next_wbs_code(wb, project_id, parent),
        "task_name": clean_text(values.get("task_name")),
        "task_type": task_type,
        "phase": clean_text(values.get("phase")),
        "owner": clean_text(values.get("owner")),
        "contributors": clean_text(values.get("contributors")),
        "planned_start": start,
        "planned_end": end,
        "baseline_start": start,
        "baseline_end": end,
        "forecast_start": start,
        "forecast_end": end,
        "actual_start": None,
        "actual_end": None,
        "effort_days": values.get("effort_days") or 0,
        "percent_complete": 0,
        "task_status": "未开始",
        "health": "正常",
        "milestone_flag": "是" if values.get("milestone_flag") else "否",
        "dependency_task_ids": dependencies,
        "deliverable": clean_text(values.get("deliverable")),
        "acceptance_criteria": clean_text(values.get("acceptance_criteria")),
        "blocker_flag": "否",
        "schedule_variance_days": None,
        "completion_weight": None,
        "last_progress_date": None,
        "last_updated_at": ts,
        "last_updated_by": updater,
        "remark": clean_text(values.get("remark")),
    }
    row = append_record(wb, "任务", data)
    add_change(wb, project_id, "任务", task_id, "新增任务", "task_id", "", task_id, "创建任务", updater)
    return {**data, "_row": row}


def update_task(wb, task_id: str, updates: dict[str, Any], reason: str, updated_by: str) -> dict[str, Any]:
    task = find_record(wb, "任务", task_id)
    project_id = clean_text(task["project_id"])
    protected = {"task_id", "project_id", "baseline_start", "baseline_end", "percent_complete", "task_status"}
    sensitive = {
        "parent_task_id", "planned_start", "planned_end", "effort_days", "dependency_task_ids",
        "deliverable", "acceptance_criteria",
    }
    actual_updates = {k: v for k, v in updates.items() if k not in protected and v is not None}
    if any(field in sensitive for field in actual_updates) and not clean_text(reason):
        raise PlanError("CHANGE_REASON_REQUIRED", "修改计划日期、依赖、范围或工作量时必须提供 --reason", "reason")
    for field in ["planned_start", "planned_end", "forecast_start", "forecast_end"]:
        if field in actual_updates:
            actual_updates[field] = parse_date(actual_updates[field], field)
    if "dependency_task_ids" in actual_updates:
        actual_updates["dependency_task_ids"] = normalize_id_list(actual_updates["dependency_task_ids"])
        if task_id in split_ids(actual_updates["dependency_task_ids"]):
            raise PlanError("SELF_DEPENDENCY", "任务不能依赖自身", "dependency_task_ids")
        for dep in split_ids(actual_updates["dependency_task_ids"]):
            dep_task = find_record(wb, "任务", dep)
            if clean_text(dep_task["project_id"]) != project_id:
                raise PlanError("DEPENDENCY_PROJECT_MISMATCH", f"依赖任务 {dep} 不属于当前项目", "dependency_task_ids")
    if "parent_task_id" in actual_updates:
        parent = clean_text(actual_updates["parent_task_id"])
        if parent == task_id:
            raise PlanError("SELF_PARENT", "任务不能作为自己的父任务", "parent_task_id")
        if parent:
            parent_task = find_record(wb, "任务", parent)
            if clean_text(parent_task["project_id"]) != project_id:
                raise PlanError("PARENT_PROJECT_MISMATCH", "父任务不属于当前项目", "parent_task_id")
        actual_updates["parent_task_id"] = parent
    merged = {**task, **actual_updates}
    start = parse_date(merged.get("planned_start"), "planned_start", allow_none=False)
    end = parse_date(merged.get("planned_end"), "planned_end", allow_none=False)
    if start > end:
        raise PlanError("INVALID_DATE_RANGE", "任务开始日期不能晚于结束日期", "planned_start")
    forecast_start = parse_date(merged.get("forecast_start"), "forecast_start")
    forecast_end = parse_date(merged.get("forecast_end"), "forecast_end")
    if forecast_start and forecast_end and forecast_start > forecast_end:
        raise PlanError("INVALID_FORECAST_RANGE", "预测开始日期不能晚于预测结束日期", "forecast_start")
    actual_updates["last_updated_at"] = now_iso()
    actual_updates["last_updated_by"] = updated_by
    for field, new_value in actual_updates.items():
        if field in {"last_updated_at", "last_updated_by"}:
            continue
        old_value = task.get(field)
        if serializable(old_value) != serializable(new_value):
            add_change(
                wb, project_id, "任务", task_id,
                "重新排期" if field in {"planned_start", "planned_end", "forecast_start", "forecast_end"} else "修改任务",
                field, old_value, new_value, clean_text(reason) or "任务信息维护", updated_by,
            )
    update_record(wb, "任务", task["_row"], actual_updates)
    return {**task, **actual_updates}


def update_progress(wb, task_id: str, values: dict[str, Any]) -> dict[str, Any]:
    task = find_record(wb, "任务", task_id)
    percent = int(values["percent_complete"])
    if not 0 <= percent <= 100:
        raise PlanError("INVALID_PERCENT", "完成度必须在 0 到 100 之间", "percent_complete")
    old_percent = int(task.get("percent_complete") or 0)
    status = clean_text(values.get("task_status"))
    if not status:
        status = "未开始" if percent == 0 else "已完成" if percent == 100 else "进行中"
    if status not in DICTIONARIES["task_status"]:
        raise PlanError("INVALID_ENUM", f"无效任务状态：{status}", "task_status")
    if status == "已完成" and percent != 100:
        raise PlanError("COMPLETION_MISMATCH", "已完成任务的完成度必须为 100", "percent_complete")
    update_date = parse_date(values.get("update_date") or today(), "update_date", allow_none=False)
    updater = clean_text(values.get("updater")) or "User"
    actual_start = parse_date(values.get("actual_start"), "actual_start") or parse_date(task.get("actual_start"), "actual_start")
    actual_end = parse_date(values.get("actual_end"), "actual_end") or parse_date(task.get("actual_end"), "actual_end")
    if percent > 0 and not actual_start:
        actual_start = update_date
    if status == "已完成" and not actual_end:
        actual_end = update_date
    if actual_start and actual_end and actual_start > actual_end:
        raise PlanError("INVALID_ACTUAL_RANGE", "实际开始日期不能晚于实际结束日期", "actual_start")
    blockers = clean_text(values.get("blockers"))
    updates = {
        "percent_complete": percent,
        "task_status": status,
        "blocker_flag": "否" if values.get("clear_blocker") else "是" if blockers or status == "阻塞" else (task.get("blocker_flag") or "否"),
        "actual_start": actual_start,
        "actual_end": actual_end,
        "last_progress_date": update_date,
        "last_updated_at": now_iso(),
        "last_updated_by": updater,
    }
    update_record(wb, "任务", task["_row"], updates)
    project = find_record(wb, "项目", clean_text(task["project_id"]))
    active_tasks = [
        item for item in records(wb, "任务")
        if clean_text(item.get("project_id")) == clean_text(task["project_id"])
        and clean_text(item.get("task_status")) != "取消"
    ]
    project_updates = {
        "last_updated_at": now_iso(),
        "last_updated_by": updater,
        "current_phase": clean_text(task.get("phase")) or project.get("current_phase"),
    }
    if percent > 0 and not project.get("actual_start"):
        project_updates["actual_start"] = update_date
    if active_tasks and all(clean_text(item.get("task_status")) == "已完成" for item in active_tasks):
        project_updates["project_status"] = "已完成"
        project_updates["actual_end"] = update_date
    elif percent > 0:
        project_updates["project_status"] = "进行中"
    update_record(wb, "项目", project["_row"], project_updates)
    _set_project_formula(wb["项目"], project["_row"])
    log_id = next_daily_id(wb, "进度日志", "LOG")
    append_record(wb, "进度日志", {
        "log_id": log_id,
        "project_id": task["project_id"],
        "task_id": task_id,
        "update_date": update_date,
        "percent_before": old_percent,
        "percent_after": percent,
        "status_before": task.get("task_status") or "",
        "status_after": status,
        "work_completed": clean_text(values.get("work_completed")),
        "next_steps": clean_text(values.get("next_steps")),
        "blockers": blockers,
        "evidence_link": clean_text(values.get("evidence_link")),
        "updater": updater,
        "updated_at": now_iso(),
        "remark": clean_text(values.get("remark")),
    })
    add_change(
        wb, clean_text(task["project_id"]), "任务", task_id, "进度更新", "percent_complete",
        old_percent, percent, clean_text(values.get("remark")) or "任务进度更新", updater,
    )
    return {"task_id": task_id, "log_id": log_id, **updates}


def add_milestone(wb, project_id: str, values: dict[str, Any]) -> dict[str, Any]:
    find_record(wb, "项目", project_id)
    if not clean_text(values.get("milestone_name")):
        raise PlanError("MILESTONE_NAME_REQUIRED", "里程碑名称不能为空", "milestone_name")
    planned_date = parse_date(values.get("planned_date"), "planned_date", allow_none=False)
    related = normalize_id_list(values.get("related_task_ids"))
    for task_id in split_ids(related):
        task = find_record(wb, "任务", task_id)
        if clean_text(task["project_id"]) != project_id:
            raise PlanError("RELATED_TASK_PROJECT_MISMATCH", f"关联任务 {task_id} 不属于当前项目", "related_task_ids")
    updater = clean_text(values.get("last_updated_by")) or "User"
    milestone_id = next_entity_id(wb, "里程碑", "MS-", 3)
    data = {
        "milestone_id": milestone_id,
        "project_id": project_id,
        "milestone_name": clean_text(values.get("milestone_name")),
        "milestone_type": clean_text(values.get("milestone_type")) or "交付",
        "owner": clean_text(values.get("owner")),
        "baseline_date": planned_date,
        "planned_date": planned_date,
        "forecast_date": planned_date,
        "actual_date": None,
        "milestone_status": "未开始",
        "acceptance_condition": clean_text(values.get("acceptance_condition")),
        "related_task_ids": related,
        "risk_note": "",
        "last_updated_at": now_iso(),
        "last_updated_by": updater,
        "remark": clean_text(values.get("remark")),
    }
    append_record(wb, "里程碑", data)
    add_change(wb, project_id, "里程碑", milestone_id, "新增里程碑", "milestone_id", "", milestone_id, "创建里程碑", updater)
    return data


def update_milestone(wb, milestone_id: str, updates: dict[str, Any], reason: str, updated_by: str) -> dict[str, Any]:
    milestone = find_record(wb, "里程碑", milestone_id)
    actual_updates = {k: v for k, v in updates.items() if v is not None}
    if "planned_date" in actual_updates and not clean_text(reason):
        raise PlanError("CHANGE_REASON_REQUIRED", "修改里程碑计划日期时必须提供 --reason", "reason")
    for field in ["planned_date", "forecast_date", "actual_date"]:
        if field in actual_updates:
            actual_updates[field] = parse_date(actual_updates[field], field)
    if "milestone_status" in actual_updates and actual_updates["milestone_status"] not in DICTIONARIES["milestone_status"]:
        raise PlanError("INVALID_ENUM", f"无效里程碑状态：{actual_updates['milestone_status']}", "milestone_status")
    if actual_updates.get("milestone_status") == "已达成" and not actual_updates.get("actual_date") and not milestone.get("actual_date"):
        actual_updates["actual_date"] = today()
    actual_updates["last_updated_at"] = now_iso()
    actual_updates["last_updated_by"] = updated_by
    for field, value in actual_updates.items():
        if field.startswith("last_updated"):
            continue
        if serializable(milestone.get(field)) != serializable(value):
            add_change(
                wb, clean_text(milestone["project_id"]), "里程碑", milestone_id, "修改里程碑",
                field, milestone.get(field), value, clean_text(reason) or "里程碑维护", updated_by,
            )
    update_record(wb, "里程碑", milestone["_row"], actual_updates)
    return {**milestone, **actual_updates}


def add_issue(wb, project_id: str, values: dict[str, Any]) -> dict[str, Any]:
    find_record(wb, "项目", project_id)
    if not clean_text(values.get("title")):
        raise PlanError("ISSUE_TITLE_REQUIRED", "风险问题标题不能为空", "title")
    if not clean_text(values.get("owner")):
        raise PlanError("OWNER_REQUIRED", "风险问题负责人不能为空", "owner")
    task_id = clean_text(values.get("task_id"))
    if task_id:
        task = find_record(wb, "任务", task_id)
        if clean_text(task["project_id"]) != project_id:
            raise PlanError("ISSUE_TASK_PROJECT_MISMATCH", "关联任务不属于当前项目", "task_id")
    item_type = clean_text(values.get("item_type"))
    severity = clean_text(values.get("severity"))
    probability = clean_text(values.get("probability")) or "中"
    if item_type not in DICTIONARIES["item_type"]:
        raise PlanError("INVALID_ENUM", f"无效问题类型：{item_type}", "item_type")
    if severity not in DICTIONARIES["severity"]:
        raise PlanError("INVALID_ENUM", f"无效严重程度：{severity}", "severity")
    if probability not in DICTIONARIES["probability"]:
        raise PlanError("INVALID_ENUM", f"无效概率：{probability}", "probability")
    updater = clean_text(values.get("last_updated_by")) or "User"
    item_id = next_entity_id(wb, "风险问题", "ITEM-", 3)
    data = {
        "item_id": item_id,
        "project_id": project_id,
        "task_id": task_id,
        "item_type": item_type,
        "title": clean_text(values.get("title")),
        "description": clean_text(values.get("description")),
        "impact": clean_text(values.get("impact")),
        "probability": probability,
        "severity": severity,
        "owner": clean_text(values.get("owner")),
        "identified_date": today(),
        "due_date": parse_date(values.get("due_date"), "due_date"),
        "item_status": "开放",
        "mitigation": clean_text(values.get("mitigation")),
        "resolution": "",
        "closed_date": None,
        "last_updated_at": now_iso(),
        "last_updated_by": updater,
        "remark": clean_text(values.get("remark")),
    }
    append_record(wb, "风险问题", data)
    project = find_record(wb, "项目", project_id)
    suggested_health = "风险" if item_type == "阻塞" or severity == "严重" else "关注"
    current_health = clean_text(project.get("health"))
    if current_health != "风险" and current_health != suggested_health:
        update_record(wb, "项目", project["_row"], {
            "health": suggested_health,
            "last_updated_at": now_iso(),
            "last_updated_by": updater,
        })
        _set_project_formula(wb["项目"], project["_row"])
    add_change(wb, project_id, "风险问题", item_id, "新增风险问题", "item_id", "", item_id, "创建风险问题", updater)
    return data


def update_issue(wb, item_id: str, updates: dict[str, Any], reason: str, updated_by: str) -> dict[str, Any]:
    issue = find_record(wb, "风险问题", item_id)
    actual_updates = {k: v for k, v in updates.items() if v is not None}
    if "due_date" in actual_updates:
        actual_updates["due_date"] = parse_date(actual_updates["due_date"], "due_date")
    for field, dict_type in [("item_status", "item_status"), ("severity", "severity"), ("probability", "probability")]:
        if field in actual_updates and actual_updates[field] not in DICTIONARIES[dict_type]:
            raise PlanError("INVALID_ENUM", f"无效字段值：{field}={actual_updates[field]}", field)
    actual_updates["last_updated_at"] = now_iso()
    actual_updates["last_updated_by"] = updated_by
    for field, value in actual_updates.items():
        if field.startswith("last_updated"):
            continue
        if serializable(issue.get(field)) != serializable(value):
            add_change(
                wb, clean_text(issue["project_id"]), "风险问题", item_id, "修改风险问题",
                field, issue.get(field), value, clean_text(reason) or "风险问题维护", updated_by,
            )
    update_record(wb, "风险问题", issue["_row"], actual_updates)
    return {**issue, **actual_updates}


def close_issue(wb, item_id: str, resolution: str, closed_date: date, updated_by: str) -> dict[str, Any]:
    return update_issue(
        wb, item_id,
        {"item_status": "已关闭", "resolution": resolution, "closed_date": closed_date},
        "问题关闭", updated_by,
    )


def validate_workbook(wb) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    def add(severity: str, code: str, message: str, entity_id: str = "", field: str = ""):
        item = {"severity": severity, "code": code, "message": message}
        if entity_id:
            item["entity_id"] = entity_id
        if field:
            item["field"] = field
        issues.append(item)

    for sheet_name, schema in SHEET_SCHEMAS.items():
        if sheet_name not in wb.sheetnames:
            add("error", "MISSING_SHEET", f"缺少工作表：{sheet_name}")
            continue
        ws = wb[sheet_name]
        actual_headers = [clean_text(ws.cell(1, idx).value) for idx in range(1, len(schema["fields"]) + 1)]
        if actual_headers != schema["fields"]:
            add("error", "HEADER_MISMATCH", f"工作表 {sheet_name} 的字段顺序或名称不符合规范")

    if any(item["code"] == "MISSING_SHEET" for item in issues):
        return issues

    all_records = {name: records(wb, name) for name in SHEET_SCHEMAS}
    for sheet_name, rows in all_records.items():
        key = SHEET_SCHEMAS[sheet_name]["key"]
        if sheet_name == "字典":
            continue
        seen: set[str] = set()
        for row in rows:
            entity_id = clean_text(row.get(key))
            if not entity_id:
                add("error", "MISSING_ID", f"{sheet_name}存在空主键", field=key)
            elif entity_id in seen:
                add("error", "DUPLICATE_ID", f"{sheet_name}主键重复：{entity_id}", entity_id, key)
            seen.add(entity_id)

    projects = {clean_text(row["project_id"]): row for row in all_records["项目"]}
    tasks = {clean_text(row["task_id"]): row for row in all_records["任务"]}
    milestones = {clean_text(row["milestone_id"]): row for row in all_records["里程碑"]}

    for project_id, project in projects.items():
        start = _safe_date(project.get("planned_start"), add, project_id, "planned_start")
        end = _safe_date(project.get("planned_end"), add, project_id, "planned_end")
        if start and end and start > end:
            add("error", "INVALID_DATE_RANGE", "项目开始日期晚于结束日期", project_id, "planned_start")
        _check_enum(project, project_id, "priority", "priority", add)
        _check_enum(project, project_id, "project_status", "project_status", add)
        _check_enum(project, project_id, "health", "health", add)

    for task_id, task in tasks.items():
        project_id = clean_text(task.get("project_id"))
        if project_id not in projects:
            add("error", "PROJECT_REFERENCE_MISSING", f"任务引用不存在的项目：{project_id}", task_id, "project_id")
        parent = clean_text(task.get("parent_task_id"))
        if parent:
            if parent not in tasks:
                add("error", "PARENT_MISSING", f"父任务不存在：{parent}", task_id, "parent_task_id")
            elif clean_text(tasks[parent].get("project_id")) != project_id:
                add("error", "PARENT_PROJECT_MISMATCH", f"父任务 {parent} 不属于同一项目", task_id, "parent_task_id")
        for dep in split_ids(task.get("dependency_task_ids")):
            if dep not in tasks:
                add("error", "DEPENDENCY_MISSING", f"依赖任务不存在：{dep}", task_id, "dependency_task_ids")
            elif clean_text(tasks[dep].get("project_id")) != project_id:
                add("error", "DEPENDENCY_PROJECT_MISMATCH", f"依赖任务 {dep} 不属于同一项目", task_id, "dependency_task_ids")
        start = _safe_date(task.get("planned_start"), add, task_id, "planned_start")
        end = _safe_date(task.get("planned_end"), add, task_id, "planned_end")
        if not start or not end:
            add("error", "PLAN_DATE_REQUIRED", "任务必须填写计划开始和结束日期", task_id, "planned_start")
        elif start > end:
            add("error", "INVALID_DATE_RANGE", "任务开始日期晚于结束日期", task_id, "planned_start")
        actual_start = _safe_date(task.get("actual_start"), add, task_id, "actual_start")
        actual_end = _safe_date(task.get("actual_end"), add, task_id, "actual_end")
        if actual_end and not actual_start:
            add("error", "ACTUAL_START_REQUIRED", "存在实际结束日期时必须填写实际开始日期", task_id, "actual_start")
        if actual_start and actual_end and actual_start > actual_end:
            add("error", "INVALID_ACTUAL_RANGE", "实际开始日期晚于实际结束日期", task_id, "actual_start")
        try:
            percent = int(float(task.get("percent_complete") or 0))
        except (TypeError, ValueError):
            percent = -1
        if not 0 <= percent <= 100:
            add("error", "INVALID_PERCENT", "完成度必须在 0 到 100 之间", task_id, "percent_complete")
        status = clean_text(task.get("task_status"))
        if status == "已完成" and percent != 100:
            add("error", "COMPLETION_MISMATCH", "已完成任务的完成度必须为 100", task_id, "percent_complete")
        if percent == 100 and status not in {"已完成", "取消"}:
            add("warning", "STATUS_PERCENT_MISMATCH", "完成度为 100，状态建议设置为已完成", task_id, "task_status")
        if status == "未开始" and percent != 0:
            add("warning", "STATUS_PERCENT_MISMATCH", "未开始任务的完成度建议为 0", task_id, "percent_complete")
        _check_enum(task, task_id, "task_type", "task_type", add)
        _check_enum(task, task_id, "task_status", "task_status", add)
        _check_enum(task, task_id, "health", "health", add)
        calc = calculate_task(task)
        suggested_health = "风险" if clean_text(task.get("blocker_flag")) == "是" or calc["schedule_variance_days"] > 5 else "关注" if calc["schedule_variance_days"] > 0 else "正常"
        if clean_text(task.get("health")) != suggested_health:
            add("warning", "HEALTH_SUGGESTION", f"按当前进度建议健康度为“{suggested_health}”", task_id, "health")

    _detect_cycles(tasks, "parent_task_id", lambda value: [clean_text(value)] if clean_text(value) else [], "PARENT_CYCLE", add)
    _detect_cycles(tasks, "dependency_task_ids", split_ids, "DEPENDENCY_CYCLE", add)

    for milestone_id, milestone in milestones.items():
        project_id = clean_text(milestone.get("project_id"))
        if project_id not in projects:
            add("error", "PROJECT_REFERENCE_MISSING", f"里程碑引用不存在的项目：{project_id}", milestone_id, "project_id")
        for task_id in split_ids(milestone.get("related_task_ids")):
            if task_id not in tasks:
                add("error", "RELATED_TASK_MISSING", f"里程碑关联任务不存在：{task_id}", milestone_id, "related_task_ids")
        _check_enum(milestone, milestone_id, "milestone_status", "milestone_status", add)

    for issue in all_records["风险问题"]:
        item_id = clean_text(issue.get("item_id"))
        project_id = clean_text(issue.get("project_id"))
        if project_id not in projects:
            add("error", "PROJECT_REFERENCE_MISSING", f"风险问题引用不存在的项目：{project_id}", item_id, "project_id")
        task_id = clean_text(issue.get("task_id"))
        if task_id and task_id not in tasks:
            add("error", "ISSUE_TASK_MISSING", f"风险问题关联任务不存在：{task_id}", item_id, "task_id")
        if not clean_text(issue.get("owner")):
            add("warning", "ISSUE_OWNER_MISSING", "风险问题建议指定责任人", item_id, "owner")
        _check_enum(issue, item_id, "item_type", "item_type", add)
        _check_enum(issue, item_id, "item_status", "item_status", add)
        _check_enum(issue, item_id, "severity", "severity", add)

    return issues


def _safe_date(value, add, entity_id: str, field: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return parse_date(value, field)
    except PlanError:
        add("error", "INVALID_DATE", f"日期格式无效：{value}", entity_id, field)
        return None


def _check_enum(row, entity_id: str, field: str, dict_type: str, add):
    value = clean_text(row.get(field))
    if value and value not in DICTIONARIES[dict_type]:
        add("error", "INVALID_ENUM", f"字段 {field} 的值无效：{value}", entity_id, field)


def _detect_cycles(nodes, field: str, edge_parser, code: str, add):
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str, trail: list[str]):
        if node_id in visiting:
            cycle = trail[trail.index(node_id):] + [node_id] if node_id in trail else trail + [node_id]
            add("error", code, "检测到循环关系：" + " -> ".join(cycle), node_id, field)
            return
        if node_id in visited or node_id not in nodes:
            return
        visiting.add(node_id)
        for target in edge_parser(nodes[node_id].get(field)):
            if target:
                visit(target, trail + [node_id])
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in nodes:
        visit(node_id, [])


def validate_or_raise(wb):
    issues = validate_workbook(wb)
    errors = [item for item in issues if item["severity"] == "error"]
    if errors:
        raise PlanError("VALIDATION_FAILED", f"写入后校验失败，共 {len(errors)} 个错误：{errors[0]['message']}")


def workbook_snapshot(wb, project_id: str | None = None) -> dict[str, Any]:
    selected_project = default_project_id(wb, project_id)
    result: dict[str, Any] = {}
    mapping = {
        "projects": "项目", "tasks": "任务", "milestones": "里程碑", "progress_log": "进度日志",
        "issues": "风险问题", "change_log": "变更记录",
    }
    for output_key, sheet_name in mapping.items():
        rows = []
        for row in records(wb, sheet_name):
            if clean_text(row.get("project_id")) != selected_project:
                continue
            clean_row = {key: serializable(value) for key, value in row.items() if key != "_row"}
            if sheet_name == "任务":
                clean_row.update(calculate_task(row))
            rows.append(clean_row)
        result[output_key] = rows
    result["project_id"] = selected_project
    result["overall_percent"] = project_completion(wb, selected_project)
    return result
