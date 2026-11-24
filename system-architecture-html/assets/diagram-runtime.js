(function bootstrapArchitectureDiagrams(global) {
  "use strict";

  let renderCounter = 0;
  let mermaidInitialized = false;
  const mermaidViews = new WeakMap();

  function asElement(target) {
    const element = typeof target === "string" ? document.querySelector(target) : target;
    if (!(element instanceof Element)) {
      throw new Error("Diagram container was not found");
    }
    return element;
  }

  function text(value, fallback = "") {
    return value == null ? fallback : String(value);
  }

  function escapeLabel(value) {
    return text(value).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function mermaidId(value, prefix) {
    const raw = text(value);
    const normalized = raw
      .normalize("NFKD")
      .replace(/[^A-Za-z0-9_]/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_+|_+$/g, "");
    let hash = 2166136261;
    for (let index = 0; index < raw.length; index += 1) {
      hash ^= raw.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return `${prefix || "item"}_${normalized || "unknown"}_${(hash >>> 0).toString(36)}`;
  }

  function flowNodeSyntax(node) {
    const id = mermaidId(node.id, "flow");
    const label = escapeLabel(node.name || node.label || node.summary || node.id);
    switch (node.nodeType || node.type) {
      case "start":
      case "end":
        return `${id}(["${label}"])`;
      case "decision":
        return `${id}{"${label}"}`;
      case "data":
      case "database":
        return `${id}[("${label}")]`;
      case "manual":
        return `${id}[/"${label}"/]`;
      case "external":
        return `${id}[["${label}"]]`;
      default:
        return `${id}["${label}"]`;
    }
  }

  function buildFlowchart(flow, options = {}) {
    const direction = options.direction || flow.direction || "LR";
    const nodes = Array.isArray(flow.nodes) ? flow.nodes : [];
    const edges = Array.isArray(flow.edges) ? flow.edges : [];
    const lines = ["flowchart " + direction];

    nodes.forEach((node) => lines.push(`  ${flowNodeSyntax(node)}`));
    edges.forEach((edge) => {
      const source = mermaidId(edge.sourceId, "flow");
      const target = mermaidId(edge.targetId, "flow");
      const label = escapeLabel(edge.name || edge.label || edge.condition || "");
      const arrow = edge.lineType === "dashed" || edge.type === "exception" ? "-.->" : "-->";
      lines.push(label ? `  ${source} ${arrow}|"${label}"| ${target}` : `  ${source} ${arrow} ${target}`);
    });

    return lines.join("\n");
  }

  function sequenceArrow(message) {
    const type = message.callType || message.type;
    if (type === "async" || type === "event" || type === "callback") return "-)";
    if (type === "return" || type === "response") return "-->>";
    if (type === "exception" || type === "timeout") return "--x";
    return "->>";
  }

  function buildSequence(sequence) {
    const participants = Array.isArray(sequence.participants) ? sequence.participants : [];
    const messages = Array.isArray(sequence.messages) ? sequence.messages : [];
    const lines = ["sequenceDiagram", "  autonumber"];

    participants.forEach((participant) => {
      const id = mermaidId(participant.id, "participant");
      const role = participant.type === "actor" || participant.type === "user" ? "actor" : "participant";
      lines.push(`  ${role} ${id} as ${escapeLabel(participant.name || participant.label || participant.id)}`);
    });

    messages.forEach((message) => {
      const source = mermaidId(message.sourceId, "participant");
      const target = mermaidId(message.targetId, "participant");
      const label = escapeLabel(message.name || message.label || message.summary || message.id);
      lines.push(`  ${source}${sequenceArrow(message)}${target}: ${label}`);
    });

    return lines.join("\n");
  }

  function activateOnKeyboard(element, callback) {
    element.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      callback(event);
    });
  }

  function makeInteractive(element, binding, options) {
    if (!element || !binding) return;
    const kind = binding.kind || "item";
    const label = binding.name || binding.label || binding.id;
    element.dataset.entityId = binding.id;
    element.dataset.entityKind = kind;
    element.setAttribute("tabindex", "0");
    element.setAttribute("role", "button");
    element.setAttribute("aria-label", `${kind}: ${label}`);
    element.classList.add("diagram-interactive");

    const payload = (event) => ({ kind, id: binding.id, data: binding, element, event });
    const activate = (event) => options.onActivate && options.onActivate(payload(event));
    const enter = (event) => {
      element.classList.add("is-highlighted");
      if (options.onHover) options.onHover(payload(event));
    };
    const leave = (event) => {
      element.classList.remove("is-highlighted");
      if (options.onLeave) options.onLeave(payload(event));
    };

    element.addEventListener("click", activate);
    activateOnKeyboard(element, activate);
    element.addEventListener("pointerenter", enter);
    element.addEventListener("focus", enter);
    element.addEventListener("pointerleave", leave);
    element.addEventListener("blur", leave);
  }

  function bindFlowInteractions(container, bindings, options) {
    const nodeGroups = Array.from(container.querySelectorAll("g.node"));
    const edgeGroups = Array.from(container.querySelectorAll("g.edgePath, g.edgePaths > path.flowchart-link"));
    const edgeLabels = Array.from(container.querySelectorAll("g.edgeLabel"));
    const nodesByMermaidId = new Map((bindings.nodes || []).map((item) => [mermaidId(item.id, "flow"), item]));

    nodeGroups.forEach((group) => {
      const rawId = group.id.replace(/^flowchart-/, "").replace(/-\d+$/, "");
      const binding = nodesByMermaidId.get(rawId) || Array.from(nodesByMermaidId.entries()).find(([id]) => group.id.includes(id))?.[1];
      makeInteractive(group, binding && { ...binding, kind: binding.kind || "flow-node" }, options);
    });

    (bindings.edges || []).forEach((edge, index) => {
      const binding = { ...edge, kind: edge.kind || "flow-edge" };
      makeInteractive(edgeGroups[index], binding, options);
      const labelElement = edgeLabels[index];
      makeInteractive(labelElement, binding, options);
    });
  }

  function bindSequenceInteractions(container, bindings, options) {
    const participantElements = Array.from(container.querySelectorAll('[data-et="participant"]'));
    const messageLines = Array.from(container.querySelectorAll("line.messageLine0, line.messageLine1, path.messageLine0, path.messageLine1"));
    const messageTexts = Array.from(container.querySelectorAll("text.messageText"));

    (bindings.participants || []).forEach((participant) => {
      const expectedId = mermaidId(participant.id, "participant");
      const element = participantElements.find((candidate) => {
        const renderedId = candidate.dataset.id || candidate.getAttribute("name") || "";
        return renderedId === expectedId || renderedId.endsWith(expectedId);
      });
      makeInteractive(element, { ...participant, kind: participant.kind || "sequence-participant" }, options);
    });

    (bindings.messages || []).forEach((message, index) => {
      const binding = { ...message, kind: message.kind || "sequence-message" };
      makeInteractive(messageLines[index], binding, options);
      if (messageTexts[index]) {
        makeInteractive(messageTexts[index], binding, options);
      }
    });
  }

  function initializeMermaid(config = {}) {
    if (!global.mermaid) throw new Error("mermaid.min.js must be loaded before diagram-runtime.js");
    if (mermaidInitialized) return;
    global.mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "base",
      flowchart: { htmlLabels: false, useMaxWidth: true, curve: "basis" },
      sequence: { useMaxWidth: true, wrap: true, mirrorActors: false },
      themeVariables: {
        fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        primaryColor: "#eef6ff",
        primaryBorderColor: "#5b86b3",
        primaryTextColor: "#172033",
        lineColor: "#64748b",
        secondaryColor: "#f8fafc",
        tertiaryColor: "#ffffff"
      },
      ...config
    });
    mermaidInitialized = true;
  }

  function clamp(value, minimum, maximum) {
    return Math.min(maximum, Math.max(minimum, value));
  }

  function createToolbarButton(action, label, title, shortcut) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.diagramAction = action;
    button.textContent = label;
    button.setAttribute("aria-label", title);
    button.title = title;
    if (shortcut) button.setAttribute("aria-keyshortcuts", shortcut);
    return button;
  }

  function createMermaidViewport(container, svgMarkup, options = {}) {
    const previousView = mermaidViews.get(container);
    if (previousView) previousView.destroy();

    container.innerHTML = "";
    container.classList.add("mermaid-diagram");

    const viewer = document.createElement("div");
    viewer.className = "mermaid-viewer";
    const toolbar = document.createElement("div");
    toolbar.className = "diagram-toolbar mermaid-toolbar";
    toolbar.setAttribute("role", "toolbar");
    toolbar.setAttribute("aria-label", `${options.ariaLabel || "Mermaid 图形"}视图工具`);
    const fitButton = createToolbarButton("fit", "适应", "适应可用画布", "0");
    const zoomOutButton = createToolbarButton("zoom-out", "缩小", "缩小图形", "-");
    const zoomInButton = createToolbarButton("zoom-in", "放大", "放大图形", "+");
    const resetButton = createToolbarButton("reset", "100%", "恢复 100% 比例", "1");
    const fullscreenButton = createToolbarButton("fullscreen", "全屏", "进入全屏查看", "F");
    const zoomValue = document.createElement("output");
    zoomValue.className = "diagram-zoom-value";
    zoomValue.setAttribute("aria-live", "polite");
    toolbar.append(fitButton, zoomOutButton, zoomInButton, resetButton, zoomValue, fullscreenButton);

    const viewport = document.createElement("div");
    viewport.className = "mermaid-viewport";
    viewport.tabIndex = 0;
    viewport.setAttribute("role", "region");
    viewport.setAttribute("aria-label", `${options.ariaLabel || "Mermaid 图形"}；可拖拽平移，按加减号缩放，按 F 全屏`);
    const stage = document.createElement("div");
    stage.className = "mermaid-stage";
    stage.innerHTML = svgMarkup;
    viewport.appendChild(stage);
    viewer.append(toolbar, viewport);
    container.appendChild(viewer);

    const svg = stage.querySelector("svg");
    if (!svg) throw new Error("Mermaid did not return an SVG element");
    const viewBox = svg.viewBox && svg.viewBox.baseVal;
    const diagramWidth = Math.max(1, viewBox?.width || Number.parseFloat(svg.getAttribute("width")) || 960);
    const diagramHeight = Math.max(1, viewBox?.height || Number.parseFloat(svg.getAttribute("height")) || 540);
    svg.removeAttribute("height");
    svg.removeAttribute("width");
    svg.style.width = `${diagramWidth}px`;
    svg.style.height = `${diagramHeight}px`;
    svg.style.maxWidth = "none";
    stage.style.width = `${diagramWidth}px`;
    stage.style.height = `${diagramHeight}px`;

    const state = {
      scale: 1,
      x: 0,
      y: 0,
      mode: "fit",
      pointer: null,
      pseudoFullscreen: false,
      destroyed: false
    };
    const minimumScale = Number.isFinite(options.minScale) ? options.minScale : 0.25;
    const maximumScale = Number.isFinite(options.maxScale) ? options.maxScale : 4;
    const zoomStep = Number.isFinite(options.zoomStep) ? options.zoomStep : 1.2;

    function updateControls() {
      const percent = Math.round(state.scale * 100);
      zoomValue.value = `${percent}%`;
      zoomValue.textContent = `${percent}%`;
      zoomOutButton.disabled = state.scale <= minimumScale + 0.001;
      zoomInButton.disabled = state.scale >= maximumScale - 0.001;
      const fullscreen = document.fullscreenElement === viewer || state.pseudoFullscreen;
      fullscreenButton.textContent = fullscreen ? "退出全屏" : "全屏";
      fullscreenButton.setAttribute("aria-label", fullscreen ? "退出全屏查看" : "进入全屏查看");
      fullscreenButton.setAttribute("aria-pressed", String(fullscreen));
    }

    function applyTransform() {
      stage.style.transform = `translate(${state.x}px, ${state.y}px) scale(${state.scale})`;
      updateControls();
    }

    function centerAtScale(nextScale) {
      state.scale = clamp(nextScale, minimumScale, maximumScale);
      state.x = (viewport.clientWidth - diagramWidth * state.scale) / 2;
      state.y = (viewport.clientHeight - diagramHeight * state.scale) / 2;
      applyTransform();
    }

    function fit() {
      const padding = options.fitPadding == null ? 28 : Number(options.fitPadding);
      const availableWidth = Math.max(1, viewport.clientWidth - padding * 2);
      const availableHeight = Math.max(1, viewport.clientHeight - padding * 2);
      const fittedScale = Math.min(availableWidth / diagramWidth, availableHeight / diagramHeight, 1.35);
      state.mode = "fit";
      centerAtScale(fittedScale);
    }

    function reset() {
      state.mode = "manual";
      centerAtScale(1);
    }

    function zoomAt(nextScale, clientX, clientY) {
      const boundedScale = clamp(nextScale, minimumScale, maximumScale);
      const rect = viewport.getBoundingClientRect();
      const pointX = clientX == null ? viewport.clientWidth / 2 : clientX - rect.left;
      const pointY = clientY == null ? viewport.clientHeight / 2 : clientY - rect.top;
      const worldX = (pointX - state.x) / state.scale;
      const worldY = (pointY - state.y) / state.scale;
      state.scale = boundedScale;
      state.x = pointX - worldX * boundedScale;
      state.y = pointY - worldY * boundedScale;
      state.mode = "manual";
      applyTransform();
    }

    function zoomIn() {
      zoomAt(state.scale * zoomStep);
    }

    function zoomOut() {
      zoomAt(state.scale / zoomStep);
    }

    function setPseudoFullscreen(active) {
      state.pseudoFullscreen = active;
      viewer.classList.toggle("is-pseudo-fullscreen", active);
      document.documentElement.classList.toggle("diagram-fullscreen-open", active);
      updateControls();
      global.requestAnimationFrame(() => state.mode === "fit" && fit());
    }

    async function toggleFullscreen() {
      if (document.fullscreenElement === viewer) {
        await document.exitFullscreen();
        return;
      }
      if (state.pseudoFullscreen) {
        setPseudoFullscreen(false);
        fullscreenButton.focus();
        return;
      }
      if (viewer.requestFullscreen) {
        try {
          await viewer.requestFullscreen();
          return;
        } catch (error) {
          console.warn("Native fullscreen failed; using fixed-position fallback", error);
        }
      }
      setPseudoFullscreen(true);
    }

    function handleToolbarClick(event) {
      const action = event.target.closest("button[data-diagram-action]")?.dataset.diagramAction;
      if (action === "fit") fit();
      else if (action === "reset") reset();
      else if (action === "zoom-in") zoomIn();
      else if (action === "zoom-out") zoomOut();
      else if (action === "fullscreen") toggleFullscreen();
    }

    function handleWheel(event) {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      zoomAt(state.scale * factor, event.clientX, event.clientY);
    }

    function handleDoubleClick(event) {
      if (event.target.closest(".diagram-interactive")) return;
      event.preventDefault();
      zoomAt(state.scale * zoomStep, event.clientX, event.clientY);
    }

    function handlePointerDown(event) {
      if (event.button !== 0 || event.target.closest(".diagram-interactive")) return;
      if (event.pointerType === "touch" && document.fullscreenElement !== viewer && !state.pseudoFullscreen) return;
      state.pointer = { id: event.pointerId, clientX: event.clientX, clientY: event.clientY, x: state.x, y: state.y };
      state.mode = "manual";
      viewport.classList.add("is-panning");
      viewport.setPointerCapture(event.pointerId);
    }

    function handlePointerMove(event) {
      if (!state.pointer || state.pointer.id !== event.pointerId) return;
      state.x = state.pointer.x + event.clientX - state.pointer.clientX;
      state.y = state.pointer.y + event.clientY - state.pointer.clientY;
      applyTransform();
    }

    function handlePointerEnd(event) {
      if (!state.pointer || state.pointer.id !== event.pointerId) return;
      state.pointer = null;
      viewport.classList.remove("is-panning");
      if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
    }

    function handleViewportKeydown(event) {
      if (event.target !== viewport) return;
      const panStep = event.shiftKey ? 80 : 36;
      if (event.key === "+" || event.key === "=") zoomIn();
      else if (event.key === "-") zoomOut();
      else if (event.key === "0") fit();
      else if (event.key === "1") reset();
      else if (event.key.toLowerCase() === "f") toggleFullscreen();
      else if (event.key === "ArrowLeft") state.x += panStep;
      else if (event.key === "ArrowRight") state.x -= panStep;
      else if (event.key === "ArrowUp") state.y += panStep;
      else if (event.key === "ArrowDown") state.y -= panStep;
      else if (event.key === "Escape" && state.pseudoFullscreen) setPseudoFullscreen(false);
      else return;
      event.preventDefault();
      applyTransform();
    }

    function handleFullscreenChange() {
      updateControls();
      global.requestAnimationFrame(() => state.mode === "fit" && fit());
    }

    function handleDocumentKeydown(event) {
      if (event.key === "Escape" && state.pseudoFullscreen) {
        setPseudoFullscreen(false);
        fullscreenButton.focus();
      }
    }

    toolbar.addEventListener("click", handleToolbarClick);
    viewport.addEventListener("wheel", handleWheel, { passive: false });
    viewport.addEventListener("dblclick", handleDoubleClick);
    viewport.addEventListener("pointerdown", handlePointerDown);
    viewport.addEventListener("pointermove", handlePointerMove);
    viewport.addEventListener("pointerup", handlePointerEnd);
    viewport.addEventListener("pointercancel", handlePointerEnd);
    viewport.addEventListener("keydown", handleViewportKeydown);
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    document.addEventListener("keydown", handleDocumentKeydown);

    const resizeObserver = global.ResizeObserver
      ? new global.ResizeObserver(() => state.mode === "fit" && fit())
      : null;
    if (resizeObserver) resizeObserver.observe(viewport);

    const view = {
      viewer,
      toolbar,
      viewport,
      stage,
      svg,
      fit,
      reset,
      zoomIn,
      zoomOut,
      zoomAt,
      toggleFullscreen,
      getScale: () => state.scale,
      destroy() {
        if (state.destroyed) return;
        state.destroyed = true;
        if (resizeObserver) resizeObserver.disconnect();
        document.removeEventListener("fullscreenchange", handleFullscreenChange);
        document.removeEventListener("keydown", handleDocumentKeydown);
        if (state.pseudoFullscreen) setPseudoFullscreen(false);
        mermaidViews.delete(container);
      }
    };
    mermaidViews.set(container, view);
    updateControls();
    global.requestAnimationFrame(fit);
    return view;
  }

  async function renderMermaid(target, definition, bindings = {}, options = {}) {
    const container = asElement(target);
    initializeMermaid(options.mermaidConfig);
    const renderId = `architecture-mermaid-${Date.now()}-${renderCounter++}`;
    const result = await global.mermaid.render(renderId, definition);
    const view = createMermaidViewport(container, result.svg, options);
    if (result.bindFunctions) result.bindFunctions(container);
    const svg = view.svg;
    if (svg) {
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", options.ariaLabel || "Mermaid diagram");
    }
    if (options.kind === "sequence") bindSequenceInteractions(container, bindings, options);
    else bindFlowInteractions(container, bindings, options);
    return { container, svg, definition, view };
  }

  function architectureElements(data) {
    const layers = Array.isArray(data.layers) ? data.layers : [];
    const modules = Array.isArray(data.modules) ? data.modules : [];
    const edges = Array.isArray(data.edges) ? data.edges : [];
    const elements = [];
    const palette = [
      { line: "#3b82f6", tint: "#eff6ff" },
      { line: "#0f9f8f", tint: "#ecfdf8" },
      { line: "#7c5ce0", tint: "#f4f1ff" },
      { line: "#d97706", tint: "#fff8eb" },
      { line: "#dc5a71", tint: "#fff1f4" },
      { line: "#4f6f8f", tint: "#f1f5f9" }
    ];
    const orderedLayers = layers.map((layer, index) => ({ layer, index })).sort((a, b) => {
      const levelA = Number.isFinite(Number(a.layer.level)) ? Number(a.layer.level) : a.index;
      const levelB = Number.isFinite(Number(b.layer.level)) ? Number(b.layer.level) : b.index;
      return levelA - levelB || a.index - b.index;
    });
    const visuals = new Map(orderedLayers.map(({ layer }, index) => [layer.id, palette[index % palette.length]]));
    const moduleById = new Map(modules.map((module) => [module.id, module]));

    layers.forEach((layer) => {
      const visual = visuals.get(layer.id) || palette[0];
      elements.push({ data: { ...layer, id: layer.id, label: layer.name || layer.id, entityType: "layer", layerColor: visual.line, layerTint: visual.tint } });
    });
    modules.forEach((module) => {
      const visual = visuals.get(module.layerId) || palette[0];
      elements.push({ data: { ...module, id: module.id, parent: module.layerId, label: module.name || module.id, entityType: "module", layerColor: visual.line, layerTint: visual.tint } });
    });
    edges.forEach((edge) => {
      const sourceLayer = moduleById.get(edge.sourceId)?.layerId || "";
      const targetLayer = moduleById.get(edge.targetId)?.layerId || "";
      elements.push({ data: { ...edge, id: edge.id, source: edge.sourceId, target: edge.targetId, label: edge.name || edge.label || "", entityType: "edge", routing: sourceLayer && sourceLayer === targetLayer ? "same-layer" : "cross-layer" } });
    });
    return elements;
  }

  function architectureStyle() {
    return [
      { selector: "node[entityType = 'layer']", style: { "background-color": "data(layerTint)", "background-opacity": 0.62, "border-color": "data(layerColor)", "border-opacity": 0.58, "border-style": "dashed", "border-width": 1, label: "data(label)", color: "#334155", "font-size": 14, "font-weight": 700, "text-valign": "top", "text-halign": "left", "text-margin-x": 12, "text-margin-y": 12, padding: "30px", shape: "roundrectangle" } },
      { selector: "node[entityType = 'module']", style: { "background-color": "data(layerTint)", "border-color": "data(layerColor)", "border-opacity": 0.72, "border-width": 1, label: "data(label)", color: "#172033", "font-size": 12.5, "font-weight": 600, width: 174, height: 72, "text-valign": "center", "text-halign": "center", "text-margin-x": 0, "text-margin-y": 0, "text-wrap": "wrap", "text-max-width": 148, shape: "roundrectangle" } },
      { selector: "edge", style: { width: 0.9, opacity: 0.32, "line-color": "#64748b", "target-arrow-color": "#64748b", "target-arrow-shape": "triangle", "curve-style": "taxi", "taxi-direction": "auto", "taxi-turn": "50%", "taxi-turn-min-distance": 18, label: "data(label)", "font-size": 9.5, color: "#475569", "text-opacity": 0.22, "text-background-color": "#ffffff", "text-background-opacity": 0.88, "text-background-padding": 3, "arrow-scale": 0.68, "overlay-opacity": 0 } },
      { selector: "edge[routing = 'same-layer']", style: { "curve-style": "bezier", "control-point-step-size": 34 } },
      { selector: "edge[relationType = 'hierarchy']", style: { "line-style": "dashed", width: 0.8 } },
      { selector: ":selected, .is-highlighted", style: { "border-color": "#2563eb", "border-width": 2, opacity: 1, "line-color": "#2563eb", "target-arrow-color": "#2563eb", "text-opacity": 1, width: 2.2, "z-index": 999 } },
      { selector: ".is-dimmed", style: { opacity: 0.12 } }
    ];
  }

  function createKeyboardList(container, cy, options) {
    const list = document.createElement("details");
    list.className = "architecture-keyboard-list";
    list.setAttribute("aria-label", options.keyboardListLabel || "Architecture diagram items");
    if (options.keyboardListOpen) list.open = true;
    const summary = document.createElement("summary");
    summary.textContent = options.keyboardListSummary || "键盘导航：架构模块与关系";
    const grid = document.createElement("div");
    grid.className = "architecture-keyboard-grid";
    cy.elements().forEach((item) => {
      if (item.isParent()) return;
      const button = document.createElement("button");
      const kind = item.isEdge() ? "architecture-edge" : "architecture-node";
      const data = item.data();
      button.type = "button";
      button.className = "architecture-keyboard-item";
      button.textContent = item.isEdge() ? `${data.source} → ${data.target}: ${data.label || data.id}` : data.label;
      button.dataset.entityId = data.id;
      button.addEventListener("focus", () => item.addClass("is-highlighted"));
      button.addEventListener("blur", () => item.removeClass("is-highlighted"));
      button.addEventListener("click", (event) => options.onActivate && options.onActivate({ kind, id: data.id, data, element: button, event }));
      grid.appendChild(button);
    });
    list.append(summary, grid);
    container.insertAdjacentElement("afterend", list);
    return list;
  }

  function architectureLayout(data, options = {}) {
    const sourceLayers = Array.isArray(data.layers) ? data.layers : [];
    const modules = Array.isArray(data.modules) ? data.modules : [];
    const edges = Array.isArray(data.edges) ? data.edges : [];
    const layerSourceIndex = new Map(sourceLayers.map((layer, index) => [layer.id, index]));
    const layers = [...sourceLayers].sort((a, b) => {
      const indexA = layerSourceIndex.get(a.id) || 0;
      const indexB = layerSourceIndex.get(b.id) || 0;
      const levelA = Number.isFinite(Number(a.level)) ? Number(a.level) : indexA;
      const levelB = Number.isFinite(Number(b.level)) ? Number(b.level) : indexB;
      return levelA - levelB || indexA - indexB;
    });
    const moduleSourceIndex = new Map(modules.map((module, index) => [module.id, index]));
    const moduleById = new Map(modules.map((module) => [module.id, module]));
    const groups = new Map(layers.map((layer) => [layer.id, modules.filter((module) => module.layerId === layer.id).sort((a, b) => {
      const orderA = Number.isFinite(Number(a.order)) ? Number(a.order) : Number.POSITIVE_INFINITY;
      const orderB = Number.isFinite(Number(b.order)) ? Number(b.order) : Number.POSITIVE_INFINITY;
      return orderA - orderB || (moduleSourceIndex.get(a.id) || 0) - (moduleSourceIndex.get(b.id) || 0);
    })]));
    const neighbors = new Map(modules.map((module) => [module.id, []]));
    edges.forEach((edge) => {
      if (!moduleById.has(edge.sourceId) || !moduleById.has(edge.targetId)) return;
      neighbors.get(edge.sourceId).push(edge.targetId);
      neighbors.get(edge.targetId).push(edge.sourceId);
    });
    const orderPosition = new Map();
    const updatePositions = (items) => items.forEach((item, index) => orderPosition.set(item.id, index));
    groups.forEach(updatePositions);

    function reorderLayer(layerId, referenceLayerId) {
      const items = groups.get(layerId) || [];
      const referenceIds = new Set((groups.get(referenceLayerId) || []).map((item) => item.id));
      const score = (item) => {
        const positions = (neighbors.get(item.id) || []).filter((id) => referenceIds.has(id)).map((id) => orderPosition.get(id)).filter(Number.isFinite);
        return positions.length ? positions.reduce((sum, value) => sum + value, 0) / positions.length : null;
      };
      items.sort((a, b) => {
        const explicitA = Number.isFinite(Number(a.order)) ? Number(a.order) : null;
        const explicitB = Number.isFinite(Number(b.order)) ? Number(b.order) : null;
        if (explicitA != null || explicitB != null) return (explicitA ?? Number.POSITIVE_INFINITY) - (explicitB ?? Number.POSITIVE_INFINITY);
        const scoreA = score(a);
        const scoreB = score(b);
        if (scoreA != null && scoreB != null && scoreA !== scoreB) return scoreA - scoreB;
        if (scoreA != null && scoreB == null) return -1;
        if (scoreA == null && scoreB != null) return 1;
        return (moduleSourceIndex.get(a.id) || 0) - (moduleSourceIndex.get(b.id) || 0);
      });
      updatePositions(items);
    }

    const sweeps = Math.max(1, Number(options.sweeps) || 2);
    for (let sweep = 0; sweep < sweeps; sweep += 1) {
      for (let index = 1; index < layers.length; index += 1) reorderLayer(layers[index].id, layers[index - 1].id);
      for (let index = layers.length - 2; index >= 0; index -= 1) reorderLayer(layers[index].id, layers[index + 1].id);
    }

    const maxColumns = Math.max(2, Number(options.maxColumns) || 5);
    const columnGap = Math.max(190, Number(options.columnGap) || 220);
    const rowGap = Math.max(96, Number(options.rowGap) || 112);
    const layerGap = Math.max(90, Number(options.layerGap) || 118);
    const topPadding = Math.max(130, Number(options.topPadding) || 150);
    const columnsFor = (count) => count <= 4 ? Math.max(1, count) : Math.min(maxColumns, count <= 8 ? 4 : 5);
    const globalColumns = Math.max(1, ...layers.map((layer) => columnsFor((groups.get(layer.id) || []).length)));
    const largestLayer = Math.max(0, ...layers.map((layer) => (groups.get(layer.id) || []).length));
    const useSerpentine = options.layerArrangement === "serpentine" || (
      options.layerArrangement !== "vertical" && layers.length >= 4 && largestLayer <= 6
    );
    const positions = {};
    let cursorY = topPadding;

    if (useSerpentine) {
      const innerColumns = Math.min(2, maxColumns);
      const largestRows = Math.max(1, ...layers.map((layer) => Math.ceil(Math.max(1, (groups.get(layer.id) || []).length) / innerColumns)));
      const slotWidth = innerColumns * columnGap + 118;
      const slotHeight = Math.max(260, largestRows * rowGap + layerGap + 38);
      layers.forEach((layer, layerIndex) => {
        const children = groups.get(layer.id) || [];
        const pairRow = Math.floor(layerIndex / 2);
        const pairColumn = layerIndex % 2;
        const column = pairRow % 2 === 0 ? pairColumn : 1 - pairColumn;
        const baseX = 180 + column * slotWidth;
        const baseY = topPadding + pairRow * slotHeight;
        children.forEach((module, moduleIndex) => {
          positions[module.id] = {
            x: baseX + (moduleIndex % innerColumns) * columnGap,
            y: baseY + 72 + Math.floor(moduleIndex / innerColumns) * rowGap
          };
        });
        if (!children.length) positions[layer.id] = { x: baseX + columnGap / 2, y: baseY + 72 };
      });
      cursorY = topPadding + Math.ceil(layers.length / 2) * slotHeight;
    } else {
      layers.forEach((layer) => {
        const children = groups.get(layer.id) || [];
        const columns = columnsFor(children.length || 1);
        const rows = Math.max(1, Math.ceil((children.length || 1) / columns));
        const offsetColumns = (globalColumns - columns) / 2;
        children.forEach((module, moduleIndex) => {
          const column = moduleIndex % columns;
          const row = Math.floor(moduleIndex / columns);
          positions[module.id] = { x: 190 + (offsetColumns + column) * columnGap, y: cursorY + 76 + row * rowGap };
        });
        if (!children.length) positions[layer.id] = { x: 190 + (globalColumns - 1) * columnGap / 2, y: cursorY + 76 };
        cursorY += Math.max(205, rows * rowGap + layerGap + 34);
      });
    }

    const unassigned = modules.filter((module) => !positions[module.id]);
    unassigned.forEach((module, index) => {
      positions[module.id] = { x: 190 + (index % globalColumns) * columnGap, y: cursorY + Math.floor(index / globalColumns) * rowGap };
    });
    return { name: "preset", positions, fit: true, padding: 42, animate: false };
  }

  function renderArchitecture(target, data, options = {}) {
    const container = asElement(target);
    if (!global.cytoscape) throw new Error("cytoscape.min.js must be loaded before diagram-runtime.js");
    if (container.nextElementSibling?.classList.contains("architecture-keyboard-list")) {
      container.nextElementSibling.remove();
    }
    container.classList.add("cytoscape-architecture");
    const cy = global.cytoscape({
      container,
      elements: architectureElements(data),
      style: options.style || architectureStyle(),
      layout: options.layout || architectureLayout(data, options.layoutOptions),
      minZoom: 0.35,
      maxZoom: 2.2,
      boxSelectionEnabled: false
    });

    const payload = (event, kind) => ({ kind, id: event.target.id(), data: event.target.data(), element: container, event });
    cy.on("tap", "node", (event) => options.onActivate && options.onActivate(payload(event, event.target.isParent() ? "architecture-layer" : "architecture-node")));
    cy.on("tap", "edge", (event) => options.onActivate && options.onActivate(payload(event, "architecture-edge")));
    cy.on("mouseover", "node, edge", (event) => {
      event.target.addClass("is-highlighted");
      if (options.onHover) options.onHover(payload(event, event.target.isEdge() ? "architecture-edge" : "architecture-node"));
    });
    cy.on("mouseout", "node, edge", (event) => {
      event.target.removeClass("is-highlighted");
      if (options.onLeave) options.onLeave(payload(event, event.target.isEdge() ? "architecture-edge" : "architecture-node"));
    });

    cy.ready(() => {
      cy.fit(undefined, 34);
      container.setAttribute("role", "img");
      container.setAttribute("aria-label", options.ariaLabel || "System architecture diagram");
    });
    const keyboardList = options.keyboardList === false ? null : createKeyboardList(container, cy, options);
    return { cy, keyboardList };
  }

  global.ArchitectureDiagrams = Object.freeze({
    buildFlowchart,
    buildSequence,
    initializeMermaid,
    createMermaidViewport,
    renderMermaid,
    renderArchitecture,
    architectureLayout
  });
})(window);
