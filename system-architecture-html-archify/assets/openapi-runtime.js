(function (global) {
  "use strict";

  function showError(domId, message, error) {
    const root = document.querySelector(domId);
    if (root) {
      root.innerHTML = "";
      const panel = document.createElement("section");
      panel.className = "api-docs-error";
      panel.setAttribute("role", "alert");
      const title = document.createElement("h1");
      title.textContent = "API 文档加载失败";
      const detail = document.createElement("p");
      detail.textContent = message;
      panel.append(title, detail);
      root.appendChild(panel);
    }
    console.error(message, error || "");
  }

  function requestedOperationId() {
    const value = decodeURIComponent(global.location.hash.replace(/^#/, "")).replace(/^\/+/, "");
    return value.startsWith("api-") ? value : "";
  }

  function findOperationBlock(operationId) {
    const ids = document.querySelectorAll(".opblock-summary-operation-id");
    for (const idNode of ids) {
      if ((idNode.textContent || "").trim() === operationId) {
        return idNode.closest(".opblock");
      }
    }
    return null;
  }

  function focusOperation(operationId) {
    if (!operationId) return false;
    const block = findOperationBlock(operationId);
    if (!block) return false;
    const summary = block.querySelector(".opblock-summary-control, .opblock-summary");
    if (summary && !block.classList.contains("is-open")) summary.click();
    block.scrollIntoView({ behavior: "smooth", block: "start" });
    block.classList.add("architecture-api-target");
    const previousOutline = block.style.outline;
    const previousOffset = block.style.outlineOffset;
    block.style.outline = "3px solid #2563eb";
    block.style.outlineOffset = "3px";
    global.setTimeout(() => {
      block.classList.remove("architecture-api-target");
      block.style.outline = previousOutline;
      block.style.outlineOffset = previousOffset;
    }, 1800);
    if (summary) {
      summary.focus({ preventScroll: true });
    }
    return true;
  }

  function render(options) {
    const config = options || {};
    const domId = config.domId || "#swagger-ui";
    const specUrl = config.specUrl || "./openapi.json";
    if (!global.SwaggerUIBundle || !global.SwaggerUIStandalonePreset) {
      showError(domId, "Swagger UI 本地资源未加载，请检查 vendor 目录。", null);
      return null;
    }

    try {
      const ui = global.SwaggerUIBundle({
        url: specUrl,
        dom_id: domId,
        deepLinking: true,
        displayOperationId: true,
        filter: true,
        docExpansion: "list",
        defaultModelsExpandDepth: 1,
        persistAuthorization: false,
        tryItOutEnabled: false,
        supportedSubmitMethods: config.enableTryItOut ? undefined : [],
        validatorUrl: null,
        presets: [global.SwaggerUIBundle.presets.apis, global.SwaggerUIStandalonePreset],
        layout: "StandaloneLayout",
        onComplete: function () {
          const operationId = requestedOperationId();
          if (operationId) focusOperation(operationId);
          if (typeof config.onComplete === "function") config.onComplete(ui);
        }
      });
      global.addEventListener("hashchange", function () {
        const operationId = requestedOperationId();
        if (operationId) focusOperation(operationId);
      });
      return ui;
    } catch (error) {
      showError(domId, "无法初始化 Swagger UI，请检查 openapi.json 与本地资源。", error);
      return null;
    }
  }

  global.ArchitectureApiDocs = Object.freeze({ render, focusOperation });
})(window);
