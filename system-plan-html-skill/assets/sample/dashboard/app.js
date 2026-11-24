(function () {
  "use strict";

  const data = window.PLAN_DATA || { meta: {}, projects: [], tasks: [], milestones: [], issues: [], progress_log: [], change_log: [] };
  const project = data.projects[0] || {};
  const state = { sortKey: "wbs_code", sortDirection: 1, lastTrigger: null };
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  function esc(value) {
    return String(value == null || value === "" ? "—" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }

  function dateValue(value) {
    if (!value) return null;
    const match = String(value).slice(0, 10).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    const parsed = match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12, 0, 0) : new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function localDateKey(value) {
    const date = value instanceof Date ? value : new Date(value);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  }

  function formatDate(value) {
    const date = dateValue(value);
    return date ? new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(date) : "—";
  }

  function formatTime(value) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return esc(value);
    return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(parsed);
  }

  function clamp(value, min, max) { return Math.min(max, Math.max(min, Number(value) || 0)); }

  function badgeClass(value) {
    if (["正常", "已完成", "已达成", "已解决", "已关闭"].includes(value)) return "success";
    if (["进行中"].includes(value)) return "primary";
    if (["关注", "延期", "处理中", "高"].includes(value)) return "warning";
    if (["风险", "阻塞", "严重", "开放"].includes(value)) return "danger";
    if (["暂停"].includes(value)) return "paused";
    return "";
  }

  function badge(value) { return `<span class="status-badge ${badgeClass(value)}">${esc(value || "未设置")}</span>`; }

  function empty(message) { return `<div class="empty-state">${esc(message)}</div>`; }

  function weightedProgress(tasks) {
    const active = tasks.filter((task) => task.task_status !== "取消");
    const denominator = active.reduce((sum, task) => sum + (Number(task.completion_weight) || 1), 0);
    if (!denominator) return 0;
    return Math.round(active.reduce((sum, task) => sum + clamp(task.percent_complete, 0, 100) * (Number(task.completion_weight) || 1), 0) / denominator);
  }

  function renderHeader() {
    const title = data.meta.title || project.project_name || "项目开发计划和进度";
    document.title = title;
    $("#page-title").textContent = title;
    $("#project-summary").textContent = project.project_description || `${project.project_manager || "未指定负责人"}负责，当前阶段：${project.current_phase || "未设置"}`;
    $("#project-health").outerHTML = badge(project.health || "未设置").replace("<span", '<span id="project-health"');
    $("#data-updated").textContent = `更新时间：${formatTime(data.meta.generated_at)}`;
    $("#source-file").textContent = `数据源：${data.meta.source_file || "—"}`;
    $("#plan-period").textContent = `计划周期：${formatDate(project.planned_start)} — ${formatDate(project.planned_end)}`;
  }

  function renderKpis() {
    const tasks = data.tasks || [];
    const active = tasks.filter((task) => task.task_status !== "取消");
    const late = active.filter((task) => task.is_late || ["延期", "阻塞"].includes(task.task_status));
    const onTime = active.filter((task) => !late.includes(task) && task.task_status !== "已完成").length;
    const completed = active.filter((task) => task.task_status === "已完成").length;
    const milestones = (data.milestones || []).filter((item) => item.milestone_status !== "取消");
    const reached = milestones.filter((item) => item.milestone_status === "已达成").length;
    const openIssues = (data.issues || []).filter((item) => !["已解决", "已关闭"].includes(item.item_status));
    const cards = [
      ["整体完成度", `${Math.round(Number(data.overall_percent) || weightedProgress(tasks))}%`, `${completed}/${active.length} 个任务完成`, "success"],
      ["按期推进", onTime, "未完成且当前未延期", ""],
      ["延期/阻塞", late.length, late.length ? "需要优先处理" : "当前没有延期任务", late.length ? "danger" : "success"],
      ["里程碑达成率", milestones.length ? `${Math.round(reached / milestones.length * 100)}%` : "—", `${reached}/${milestones.length} 已达成`, ""],
      ["开放风险问题", openIssues.length, openIssues.some((item) => item.severity === "严重") ? "存在严重事项" : "待跟踪和关闭", openIssues.length ? "warning" : "success"],
    ];
    $("#kpi-grid").innerHTML = cards.map(([label, value, caption, type]) => `<article class="kpi-card ${type}"><p class="kpi-label">${esc(label)}</p><p class="kpi-value">${esc(value)}</p><p class="kpi-caption">${esc(caption)}</p></article>`).join("");
  }

  function renderPhases() {
    const groups = new Map();
    (data.tasks || []).filter((task) => task.task_status !== "取消").forEach((task) => {
      const key = task.phase || "未分阶段";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(task);
    });
    const html = Array.from(groups.entries()).map(([phase, tasks]) => {
      const progress = weightedProgress(tasks);
      const done = tasks.filter((task) => task.task_status === "已完成").length;
      return `<div class="phase-row"><div><span class="phase-name">${esc(phase)}</span><span class="phase-meta">${done}/${tasks.length} 个任务完成</span></div><div class="progress-track" aria-label="${esc(phase)}完成度 ${progress}%"><div class="progress-fill" style="width:${progress}%"></div></div><div class="phase-percent">${progress}%</div></div>`;
    }).join("");
    $("#phase-list").innerHTML = html || empty("尚未录入任务阶段");
  }

  function renderHealth() {
    const tasks = (data.tasks || []).filter((task) => task.task_status !== "取消");
    const values = [["正常", "health-normal"], ["关注", "health-watch"], ["风险", "health-risk"]];
    $("#health-breakdown").innerHTML = values.map(([label, className]) => {
      const count = tasks.filter((task) => task.health === label).length;
      const width = tasks.length ? Math.round(count / tasks.length * 100) : 0;
      return `<div class="health-row"><span>${esc(label)}</span><div class="health-bar ${className}"><span style="width:${width}%"></span></div><strong>${count}</strong></div>`;
    }).join("") + `<p class="section-note">健康度来自任务记录；计划偏差与阻塞也会在校验中给出建议。</p>`;
  }

  function renderTimeline() {
    const tasks = (data.tasks || []).filter((task) => task.task_status !== "取消" && dateValue(task.planned_start) && dateValue(task.planned_end));
    if (!tasks.length) { $("#timeline-content").innerHTML = empty("尚无可展示的任务日期"); return; }
    const allDates = [];
    tasks.forEach((task) => [task.planned_start, task.planned_end, task.forecast_start, task.forecast_end, task.actual_start, task.actual_end].forEach((value) => { const d = dateValue(value); if (d) allDates.push(d); }));
    let min = new Date(Math.min.apply(null, allDates));
    let max = new Date(Math.max.apply(null, allDates));
    if (max <= min) max = new Date(min.getTime() + 86400000);
    const span = max - min;
    const position = (value) => { const d = dateValue(value); return d ? clamp((d - min) / span * 100, 0, 100) : 0; };
    const width = (start, end) => Math.max(0.8, position(end) - position(start));
    const ticks = Array.from({ length: 6 }, (_, index) => {
      const d = new Date(min.getTime() + span * index / 5);
      return `<span class="axis-label" style="left:${index * 20}%">${esc(formatDate(d.toISOString()))}</span>`;
    }).join("");
    const todayPos = position(localDateKey(new Date()));
    const rows = tasks.slice().sort((a, b) => String(a.planned_start).localeCompare(String(b.planned_start))).map((task) => {
      const actualStart = task.actual_start || task.forecast_start || task.planned_start;
      const actualEnd = task.actual_end || task.forecast_end || task.planned_end;
      return `<div class="timeline-row" tabindex="0" role="button" data-kind="task" data-id="${esc(task.task_id)}"><div class="timeline-task"><strong>${esc(task.wbs_code)} · ${esc(task.task_name)}</strong><span>${esc(task.owner || "未指定")} · ${clamp(task.percent_complete,0,100)}%</span></div><div class="timeline-track"><span class="timeline-plan" style="left:${position(task.planned_start)}%;width:${width(task.planned_start, task.planned_end)}%"></span><span class="timeline-forecast" style="left:${position(actualStart)}%;width:${width(actualStart, actualEnd)}%"></span><span class="timeline-today" style="left:${todayPos}%" title="今天"></span></div></div>`;
    }).join("");
    $("#timeline-content").innerHTML = `<div class="timeline-grid"><div class="timeline-axis"><strong>任务 / 时间范围</strong><div class="timeline-axis-track">${ticks}</div></div>${rows}</div>`;
  }

  function renderMilestones() {
    const items = (data.milestones || []).slice().sort((a, b) => String(a.planned_date).localeCompare(String(b.planned_date)));
    $("#milestone-list").innerHTML = items.map((item) => `<button class="list-card" type="button" data-kind="milestone" data-id="${esc(item.milestone_id)}"><span class="list-card-head"><span><h3>${esc(item.milestone_name)}</h3><p>${esc(item.owner || "未指定负责人")} · ${esc(item.milestone_type || "里程碑")}</p></span>${badge(item.milestone_status)}</span><p>计划 ${formatDate(item.planned_date)}${item.forecast_date && item.forecast_date !== item.planned_date ? ` · 预测 ${formatDate(item.forecast_date)}` : ""}</p></button>`).join("") || empty("尚未设置里程碑");
  }

  function renderIssues() {
    const items = (data.issues || []).filter((item) => !["已解决", "已关闭"].includes(item.item_status)).sort((a, b) => ["严重", "高", "中", "低"].indexOf(a.severity) - ["严重", "高", "中", "低"].indexOf(b.severity));
    $("#issue-list").innerHTML = items.map((item) => `<button class="list-card" type="button" data-kind="issue" data-id="${esc(item.item_id)}"><span class="list-card-head"><span><h3>${esc(item.title)}</h3><p>${esc(item.item_type)} · ${esc(item.owner || "未指定负责人")}</p></span>${badge(item.severity)}</span><p>${esc(item.impact || item.description || "未填写影响说明")}</p></button>`).join("") || empty("当前没有开放的风险、问题或阻塞");
  }

  function renderUpdates() {
    const progress = (data.progress_log || []).map((item) => ({ type: "进度", time: item.updated_at, title: `${item.task_id}：${item.percent_before || 0}% → ${item.percent_after || 0}%`, copy: item.work_completed || item.remark || "更新任务进度", actor: item.updater }));
    const changes = (data.change_log || []).map((item) => ({ type: "变更", time: item.changed_at, title: `${item.entity_id} · ${item.change_type}`, copy: `${item.field_name}: ${item.old_value || "空"} → ${item.new_value || "空"}；${item.change_reason || "未说明原因"}`, actor: item.changed_by }));
    const items = progress.concat(changes).sort((a, b) => String(b.time).localeCompare(String(a.time))).slice(0, 12);
    $("#update-list").innerHTML = items.map((item) => `<div class="update-item"><span class="update-type">${esc(item.type)}</span><div class="update-copy"><strong>${esc(item.title)}</strong><p>${esc(item.copy)}${item.actor ? ` · ${esc(item.actor)}` : ""}</p></div><time>${formatTime(item.time)}</time></div>`).join("") || empty("尚无进度或计划变更记录");
  }

  function optionList(values) {
    return Array.from(new Set(values.filter(Boolean))).sort((a, b) => String(a).localeCompare(String(b), "zh-CN")).map((value) => `<option value="${esc(value)}">${esc(value)}</option>`).join("");
  }

  function filteredTasks() {
    const search = $("#task-search").value.trim().toLowerCase();
    const status = $("#status-filter").value;
    const owner = $("#owner-filter").value;
    const phase = $("#phase-filter").value;
    return (data.tasks || []).filter((task) => {
      const haystack = [task.task_id, task.wbs_code, task.task_name, task.phase, task.owner, task.contributors, task.deliverable, task.acceptance_criteria].join(" ").toLowerCase();
      return (!search || haystack.includes(search)) && (!status || task.task_status === status) && (!owner || task.owner === owner) && (!phase || task.phase === phase);
    }).sort((a, b) => {
      const left = a[state.sortKey] == null ? "" : a[state.sortKey];
      const right = b[state.sortKey] == null ? "" : b[state.sortKey];
      if (typeof left === "number" || typeof right === "number") return (Number(left) - Number(right)) * state.sortDirection;
      return String(left).localeCompare(String(right), "zh-CN", { numeric: true }) * state.sortDirection;
    });
  }

  function renderTasks() {
    const tasks = filteredTasks();
    $("#task-count").textContent = `${tasks.length} 个任务`;
    $("#task-table-body").innerHTML = tasks.map((task) => {
      const progress = clamp(task.percent_complete, 0, 100);
      return `<tr tabindex="0" role="button" data-kind="task" data-id="${esc(task.task_id)}"><td>${esc(task.wbs_code)}</td><td class="task-name-cell"><strong>${esc(task.task_name)}</strong><span>${esc(task.task_id)}</span></td><td>${esc(task.phase)}</td><td>${esc(task.owner)}</td><td>${formatDate(task.planned_end)}</td><td class="percent-cell"><span>${progress}%</span><div class="progress-track"><div class="progress-fill" style="width:${progress}%"></div></div></td><td>${badge(task.task_status)}</td><td>${badge(task.health)}</td></tr>`;
    }).join("") || `<tr><td colspan="8">${empty("没有符合筛选条件的任务")}</td></tr>`;
  }

  const labels = {
    task_id: "任务 ID", wbs_code: "WBS", task_name: "任务名称", task_type: "任务类型", phase: "阶段", owner: "负责人", contributors: "协作人",
    planned_start: "计划开始", planned_end: "计划结束", baseline_start: "基线开始", baseline_end: "基线结束", forecast_start: "预测开始", forecast_end: "预测结束",
    actual_start: "实际开始", actual_end: "实际结束", effort_days: "工作量（天）", percent_complete: "完成度", task_status: "状态", health: "健康度",
    dependency_task_ids: "依赖任务", deliverable: "交付物", acceptance_criteria: "验收标准", blocker_flag: "是否阻塞", schedule_variance_days: "计划偏差（天）", remark: "备注",
    milestone_id: "里程碑 ID", milestone_name: "里程碑", milestone_type: "类型", baseline_date: "基线日期", planned_date: "计划日期", forecast_date: "预测日期", actual_date: "实际日期", milestone_status: "状态", acceptance_condition: "验收条件", related_task_ids: "关联任务", risk_note: "风险说明",
    item_id: "事项 ID", item_type: "事项类型", title: "标题", description: "描述", impact: "影响", probability: "概率", severity: "严重程度", identified_date: "识别日期", due_date: "截止日期", item_status: "状态", mitigation: "缓解方案", resolution: "解决结果", closed_date: "关闭日期",
  };

  function openDrawer(kind, id, trigger) {
    const collection = kind === "task" ? data.tasks : kind === "milestone" ? data.milestones : data.issues;
    const key = kind === "task" ? "task_id" : kind === "milestone" ? "milestone_id" : "item_id";
    const item = (collection || []).find((entry) => String(entry[key]) === String(id));
    if (!item) return;
    state.lastTrigger = trigger || document.activeElement;
    const displayFields = kind === "task"
      ? ["task_id", "wbs_code", "task_name", "task_type", "phase", "owner", "contributors", "planned_start", "planned_end", "baseline_start", "baseline_end", "forecast_start", "forecast_end", "actual_start", "actual_end", "effort_days", "percent_complete", "task_status", "health", "dependency_task_ids", "deliverable", "acceptance_criteria", "blocker_flag", "schedule_variance_days", "remark"]
      : kind === "milestone"
        ? ["milestone_id", "milestone_name", "milestone_type", "owner", "baseline_date", "planned_date", "forecast_date", "actual_date", "milestone_status", "acceptance_condition", "related_task_ids", "risk_note", "remark"]
        : ["item_id", "item_type", "title", "description", "impact", "probability", "severity", "owner", "identified_date", "due_date", "item_status", "mitigation", "resolution", "closed_date", "remark"];
    $("#drawer-kicker").textContent = kind === "task" ? "TASK DETAIL" : kind === "milestone" ? "MILESTONE DETAIL" : "ISSUE DETAIL";
    $("#drawer-title").textContent = item.task_name || item.milestone_name || item.title || id;
    $("#drawer-content").innerHTML = `<dl class="detail-grid">${displayFields.map((field) => {
      let value = item[field];
      if (field.includes("date") || field.endsWith("_start") || field.endsWith("_end")) value = formatDate(value);
      if (field === "percent_complete") value = `${clamp(value, 0, 100)}%`;
      if (["task_status", "health", "milestone_status", "severity", "item_status"].includes(field)) value = badge(value);
      return `<div class="detail-field ${["task_name", "deliverable", "acceptance_criteria", "description", "impact", "mitigation", "resolution", "remark"].includes(field) ? "wide" : ""}"><dt>${esc(labels[field] || field)}</dt><dd>${typeof value === "string" && value.startsWith("<span") ? value : esc(value)}</dd></div>`;
    }).join("")}</dl>`;
    $("#drawer-backdrop").hidden = false;
    $("#detail-drawer").classList.add("open");
    $("#detail-drawer").setAttribute("aria-hidden", "false");
    history.replaceState(null, "", `#${kind}-${encodeURIComponent(id)}`);
    $("#drawer-close").focus();
  }

  function closeDrawer() {
    $("#detail-drawer").classList.remove("open");
    $("#detail-drawer").setAttribute("aria-hidden", "true");
    $("#drawer-backdrop").hidden = true;
    if (/^#(task|milestone|issue)-/.test(location.hash)) history.replaceState(null, "", location.pathname + location.search);
    if (state.lastTrigger && typeof state.lastTrigger.focus === "function") state.lastTrigger.focus();
  }

  function bindEvents() {
    ["#task-search", "#status-filter", "#owner-filter", "#phase-filter"].forEach((selector) => $(selector).addEventListener("input", renderTasks));
    $("#reset-filters").addEventListener("click", () => { $("#task-search").value = ""; $("#status-filter").value = ""; $("#owner-filter").value = ""; $("#phase-filter").value = ""; renderTasks(); });
    $$(".task-table th button").forEach((button) => button.addEventListener("click", () => { const key = button.dataset.sort; state.sortDirection = state.sortKey === key ? state.sortDirection * -1 : 1; state.sortKey = key; renderTasks(); }));
    document.addEventListener("click", (event) => { const target = event.target.closest("[data-kind][data-id]"); if (target) openDrawer(target.dataset.kind, target.dataset.id, target); });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && $("#detail-drawer").classList.contains("open")) closeDrawer();
      if (["Enter", " "].includes(event.key)) { const target = event.target.closest("[data-kind][data-id]"); if (target) { event.preventDefault(); openDrawer(target.dataset.kind, target.dataset.id, target); } }
    });
    $("#drawer-close").addEventListener("click", closeDrawer);
    $("#drawer-backdrop").addEventListener("click", closeDrawer);
  }

  function restoreHash() {
    const match = location.hash.match(/^#(task|milestone|issue)-(.+)$/);
    if (match) openDrawer(match[1], decodeURIComponent(match[2]));
  }

  function init() {
    renderHeader(); renderKpis(); renderPhases(); renderHealth(); renderTimeline(); renderMilestones(); renderIssues(); renderUpdates();
    $("#status-filter").insertAdjacentHTML("beforeend", optionList((data.tasks || []).map((item) => item.task_status)));
    $("#owner-filter").insertAdjacentHTML("beforeend", optionList((data.tasks || []).map((item) => item.owner)));
    $("#phase-filter").insertAdjacentHTML("beforeend", optionList((data.tasks || []).map((item) => item.phase)));
    renderTasks(); bindEvents(); restoreHash();
  }

  init();
}());
