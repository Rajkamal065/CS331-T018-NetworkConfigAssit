/**
 * ui/app.js — Desktop Frontend Controller for NetOps MCP Assistant
 * Bridges HTML/CSS/JS frontend to Python NetOpsBridge via window.pywebview.api
 */

let isProcessing = false;

async function callBridge(method, ...args) {
  if (window.pywebview && window.pywebview.api && typeof window.pywebview.api[method] === "function") {
    return await window.pywebview.api[method](...args);
  }
  // Web fallback via local HTTP API
  if (method === "get_status") {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }
  if (method === "send_message") {
    const res = await fetch("/api/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: args[0] })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }
  if (method === "list_tools") {
    const res = await fetch("/api/tools");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }
  throw new Error(`Unknown method: ${method}`);
}

document.addEventListener("DOMContentLoaded", () => {
  // Check pywebview API readiness
  if (window.pywebview) {
    initApp();
  } else {
    window.addEventListener("pywebviewready", initApp);
    // Timeout check if running outside pywebview (e.g. testing in standard browser)
    setTimeout(() => {
      initApp();
    }, 600);
  }

  // Auto-resize input textarea
  const input = document.getElementById("user-input");
  if (input) {
    input.addEventListener("input", () => {
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 120) + "px";
    });
  }
});

function initApp() {
  refreshStatus();
  setInterval(refreshStatus, 8000);
}

async function refreshStatus() {
  try {
    const status = await callBridge("get_status");
    updateStatusUI(status);
  } catch (err) {
    console.warn("Status fetch fallback:", err);
    const pill = document.getElementById("agent-mode-text");
    if (pill && pill.textContent.includes("Connecting")) {
      pill.textContent = "Connecting to NetOps Bridge...";
    }
  }
}

function updateStatusUI(status) {
  if (!status) return;

  // LLM Status
  const llmDesc = document.getElementById("llm-model-desc");
  const llmBadge = document.getElementById("llm-badge");
  if (status.llm) {
    if (status.llm.connected) {
      llmDesc.textContent = `${status.llm.provider.toUpperCase()} (${status.llm.model})`;
      llmBadge.textContent = "Online";
      llmBadge.className = "badge badge-success";
    } else {
      llmDesc.textContent = status.llm.provider || "Offline";
      llmBadge.textContent = "Offline";
      llmBadge.className = "badge badge-danger";
    }
  }

  // MCP Status
  const mcpBadge = document.getElementById("mcp-badge");
  const mcpDesc = document.getElementById("mcp-transport-desc");
  const toolsCount = document.getElementById("registered-tools-count");
  if (status.mcp) {
    if (status.mcp.connected) {
      mcpBadge.textContent = "Connected";
      mcpBadge.className = "badge badge-success";
      mcpDesc.textContent = `FastMCP (stdio, ${status.mcp.tools_count} tools)`;
      if (toolsCount) toolsCount.textContent = `${status.mcp.tools_count} MCP Tools Registered`;
    } else {
      mcpBadge.textContent = "Disconnected";
      mcpBadge.className = "badge badge-danger";
      mcpDesc.textContent = "Server unreachable";
    }
  }

  // Agent Mode Pill
  const pillText = document.getElementById("agent-mode-text");
  if (pillText) {
    const p = status.llm && status.llm.connected
      ? status.llm.provider.toUpperCase()
      : "OFFLINE";
    pillText.textContent = `NetOps Agent [${p} + FastMCP stdio]`;
  }
}

function handleKeyDown(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submitMessage();
  }
}

function handlePreset(text) {
  const input = document.getElementById("user-input");
  if (input) {
    input.value = text;
    submitMessage();
  }
}

async function submitMessage() {
  if (isProcessing) return;

  const input = document.getElementById("user-input");
  const text = (input ? input.value : "").trim();
  if (!text) return;

  // Clear input
  input.value = "";
  input.style.height = "auto";

  // Hide welcome hero on first message
  const hero = document.getElementById("welcome-hero");
  if (hero) hero.style.display = "none";

  // Append user message
  appendUserMessage(text);

  // Append loading card
  const loadingId = "loading-" + Date.now();
  appendLoadingCard(loadingId);

  setProcessing(true);

  try {
    const response = await callBridge("send_message", text);
    removeElement(loadingId);
    renderAssistantResponse(response);
  } catch (err) {
    removeElement(loadingId);
    appendErrorMessage("Execution error: " + (err.message || String(err)));
  } finally {
    setProcessing(false);
  }
}

function setProcessing(val) {
  isProcessing = val;
  const btn = document.getElementById("send-button");
  if (btn) btn.disabled = val;
}

function appendUserMessage(text) {
  const stream = document.getElementById("chat-stream");

  const row = document.createElement("div");
  row.className = "message-row user";

  row.innerHTML = `
    <div class="message-bubble">
      ${escapeHtml(text)}
    </div>

    <div class="avatar user-av">U</div>
  `;

  stream.appendChild(row);
  scrollToBottom();
}

function appendLoadingCard(id) {
  const stream = document.getElementById("chat-stream");

  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.id = id;

  row.innerHTML = `
    <div class="avatar ai">AI</div>

    <div class="message-bubble">
      <div class="processing-live">

        <div class="processing-header">
          <span class="processing-label">Processing</span>
          <span class="processing-spinner"></span>
        </div>

        <div class="processing-live-text" id="${id}-text">
          Understanding your request...
        </div>

      </div>
    </div>
  `;

  stream.appendChild(row);
  scrollToBottom();

  // These are user-facing progress messages while the real
  // backend operation is running.
  const stages = [
    "Understanding your request...",
    "Mapping the request to the correct network operation...",
    "Checking the applicable security policy...",
    "Applying the network change...",
    "Verifying the result independently..."
  ];

  let index = 0;

  const interval = setInterval(() => {
    const textElement = document.getElementById(`${id}-text`);

    if (!textElement) {
      clearInterval(interval);
      return;
    }

    index = (index + 1) % stages.length;
    textElement.textContent = stages[index];
  }, 850);

  const element = document.getElementById(id);

  if (element) {
    element.dataset.progressTimer = String(interval);
  }
}
function removeElement(id) {
  const el = document.getElementById(id);

  if (!el) return;

  if (el.dataset.progressTimer) {
    clearInterval(Number(el.dataset.progressTimer));
  }

  el.remove();
}

function renderExecutionTerminal(execution) {
  if (!execution || typeof execution !== "object") {
    return "";
  }

  const command = execution.command;

  if (!command) {
    return "";
  }

  const stdout = execution.stdout || "";
  const stderr = execution.stderr || "";

  const returncode =
    execution.returncode !== undefined
      ? execution.returncode
      : execution.exit_code !== undefined
        ? execution.exit_code
        : null;

  const success = returncode === 0;

  const exitText =
    returncode === null
      ? "EXIT —"
      : `EXIT ${returncode}`;

  let output = "";

  if (stdout) {
    output += `
      <div class="terminal-output">
        ${escapeHtml(stdout)}
      </div>
    `;
  }

  if (stderr) {
    output += `
      <div class="terminal-stderr">
        ${escapeHtml(stderr)}
      </div>
    `;
  }

  if (!stdout && !stderr) {
    output = `
      <div class="terminal-empty">
        No command output.
      </div>
    `;
  }

  return `
    <div class="terminal-panel">

      <div class="terminal-header">
        <span class="terminal-title">
          Network Operation
        </span>

        <span class="terminal-exit ${success ? "success" : "failure"}">
          ${exitText}
        </span>
      </div>

      <div class="terminal-body">

        <div class="terminal-command">
          <span class="terminal-prompt">$ </span>${escapeHtml(command)}
        </div>

        ${output}

      </div>

    </div>
  `;
}
function renderProcessingDrawer(res) {
  if (!res.timeline || res.timeline.length === 0) {
    return "";
  }

  const meaningfulSteps = res.timeline.filter((step) => {
    const text = String(
      step.title || step.step || ""
    ).toLowerCase();

    return (
      !text.includes("natural language request") &&
      !text.includes("intent interpreter") &&
      !text.includes("tool:") &&
      !text.includes("calling fastmcp") &&
      !text.includes("mcp execution") &&
      !text.includes("resolved conversational")
    );
  });

  if (meaningfulSteps.length === 0) {
    return "";
  }

  const completedCount = meaningfulSteps.filter(
    (step) =>
      step.status !== "REJECTED" &&
      step.status !== "FAILED" &&
      step.status !== "WARNING"
  ).length;

  let stepsHtml = "";

  meaningfulSteps.forEach((step) => {
    let symbol = "✓";

    if (
      step.status === "REJECTED" ||
      step.status === "FAILED"
    ) {
      symbol = "×";
    }

    stepsHtml += `
      <div class="processing-step">

        <span class="processing-step-icon">
          ${symbol}
        </span>

        <div class="processing-step-content">

          <div class="processing-step-title">
            ${escapeHtml(
              friendlyProcessingTitle(
                step.title || step.step
              )
            )}
          </div>

          ${
            step.detail
              ? `
                <div class="processing-step-detail">
                  ${escapeHtml(step.detail)}
                </div>
              `
              : ""
          }

        </div>

      </div>
    `;
  });

  return `
    <div class="processing-drawer expanded">

      <button
        class="processing-toggle"
        type="button"
        onclick="toggleProcessing(this)"
      >

        <span class="processing-toggle-left">

          <span class="processing-name">
            Processing
          </span>

          <span class="processing-count">
            ${completedCount} steps completed
          </span>

        </span>

        <span class="processing-arrow">
          ›
        </span>

      </button>

      <div class="processing-details">
        ${stepsHtml}
      </div>

    </div>
  `;
}


function friendlyProcessingTitle(title) {
  const text = String(title || "").toLowerCase();

  if (text.includes("natural language")) {
    return "Request understood";
  }

  if (text.includes("intent")) {
    return "Intent mapped";
  }

  if (text.includes("policy")) {
    return "Security policy checked";
  }

  if (
    text.includes("dispatch") ||
    text.includes("calling fastmcp") ||
    text.includes("tool")
  ) {
    return "Network operation selected";
  }

  if (
    text.includes("execution") ||
    text.includes("succeeded") ||
    text.includes("applied")
  ) {
    return "Network operation completed";
  }

  if (text.includes("verification")) {
    return "Independent verification completed";
  }

  return title;
}


function toggleProcessing(button) {
  const drawer = button.closest(".processing-drawer");

  if (!drawer) {
    return;
  }

  drawer.classList.toggle("expanded");
}
function renderAssistantResponse(res) {
  const stream = document.getElementById("chat-stream");
  const row = document.createElement("div");
  row.className = "message-row assistant";

  let bodyHtml = "";

  // ── Pure conversational reply (no tool was called) ────────────
  if (res.type === "conversation") {
    const text = res.content || res.ai_response || "";
    row.innerHTML = `
      <div class="avatar ai">AI</div>
      <div class="message-bubble">
        <div class="ai-text md-body">${renderMarkdown(text)}</div>
      </div>
    `;
    stream.appendChild(row);
    scrollToBottom();
    return;
  }

  // ── Operation / policy-rejection / error ─────────────────────

  // 1. Intent-confirmation pill (natural AI message at the top)
  const intentMsg = res.ai_response || "";
  if (intentMsg) {
    bodyHtml += `<div class="intent-pill">${escapeHtml(intentMsg)}</div>`;
  }

  // 2. Processing steps drawer (expanded by default for operations)
  if (res.timeline && res.timeline.length > 0) {
    bodyHtml += renderProcessingDrawer(res);
  }

  // 3. Black terminal panel (actual command + stdout/stderr)
  const execution = res.execution || (res.result && res.result.execution);
  if (execution && execution.command) {
    bodyHtml += renderExecutionTerminal(execution);
  }

  // 4. Policy rejection
  if (res.type === "policy_rejection") {
    bodyHtml += `
      <div class="policy-box">
        <div class="policy-box-title">Request blocked by security policy</div>
        <div class="policy-box-text">
          ${escapeHtml(res.error || "This network operation is not permitted.")}
          <br><strong>No network command was executed.</strong>
        </div>
      </div>
    `;
  }

  // 5. Independent verification
  if (res.verification) {
    const v = res.verification;
    const isVerified = v.status === "VERIFIED" || v.status === "PASS";
    bodyHtml += `
      <div class="verification-box ${isVerified ? "verified" : "warning"}">
        <div class="verif-header">
          <span class="verif-status">${isVerified ? "Independently Verified" : "Verification Caution"}</span>
          <span class="badge ${isVerified ? "badge-success" : "badge-warning"}">${escapeHtml(v.status || "CHECKED")}</span>
        </div>
        <div class="verif-summary">${escapeHtml(v.summary || JSON.stringify(v))}</div>
      </div>
    `;
  }

  // 6. Diagnostics result
  if (res.result && (res.result.packet_loss_percent !== undefined || res.result.throughput_mbps !== undefined)) {
    const r = res.result;
    const isPass = r.status === "PASS";
    const statusClass = isPass ? "badge-success" : r.status === "DEGRADED" ? "badge-warning" : "badge-danger";
    bodyHtml += `
      <div class="diagnostic-box">
        <div class="verif-header">
          <span class="verif-status">Network Diagnostics</span>
          <span class="badge ${statusClass}">${escapeHtml(r.status || "DONE")}</span>
        </div>
        <div class="verif-summary">
          <strong>Target:</strong> ${escapeHtml(r.target || "127.0.0.1")}
          &nbsp;|&nbsp;
          <strong>Packet Loss:</strong> ${r.packet_loss_percent !== undefined ? r.packet_loss_percent + "%" : "N/A"}
          &nbsp;|&nbsp;
          <strong>Avg RTT:</strong> ${r.avg_rtt_ms !== undefined ? r.avg_rtt_ms + " ms" : "N/A"}
          ${r.throughput_mbps !== undefined ? `&nbsp;|&nbsp;<strong>Throughput:</strong> ${r.throughput_mbps} Mbps` : ""}
        </div>
      </div>
    `;
  }

  // 7. Firewall rules table
  if (res.result && res.result.rules) {
    bodyHtml += `
      <div class="output-section">
        <div class="output-section-title">Active Firewall Rules</div>
        <pre class="code-block">${escapeHtml(res.result.rules)}</pre>
      </div>
    `;
  }

  // 8. Listening sockets
  if (res.result && res.result.raw) {
    bodyHtml += `
      <div class="output-section">
        <div class="output-section-title">Listening Sockets</div>
        <pre class="code-block">${escapeHtml(res.result.raw)}</pre>
      </div>
    `;
  }

  // 9. Port connectivity probe result
  if (res.result && res.result.state !== undefined) {
    const r = res.result;
    const stateMap = {
      REACHABLE: { label: "Reachable",       cls: "badge-success", boxCls: "verified"  },
      REFUSED:   { label: "Connection Refused", cls: "badge-warning", boxCls: "warning"  },
      BLOCKED:   { label: "Blocked / Dropped",  cls: "badge-danger",  boxCls: "warning"  },
      ERROR:     { label: "Probe Error",       cls: "badge-danger",  boxCls: "warning"  },
    };
    const s = stateMap[r.state] || { label: r.state, cls: "badge-warning", boxCls: "warning" };

    bodyHtml += `
      <div class="verification-box ${s.boxCls}">
        <div class="verif-header">
          <span class="verif-status">TCP Connectivity Probe</span>
          <span class="badge ${s.cls}">${s.label}</span>
        </div>
        <div class="verif-summary">
          <strong>Target:</strong> ${escapeHtml(String(r.host || "127.0.0.1"))}:${escapeHtml(String(r.port || ""))}
          &nbsp;|&nbsp;
          <strong>Latency:</strong> ${r.latency_ms !== undefined ? r.latency_ms + " ms" : "N/A"}
          <br>
          <span style="color:var(--text-muted); font-size:11px;">${escapeHtml(r.details || "")}</span>
        </div>
      </div>
    `;
  }

  // 10. Bandwidth inspection result (from check_bandwidth or set_bandwidth_limit)
  if (res.result && (res.result.current_rate_mbps !== undefined || res.result.bandwidth_audit !== undefined)) {
    const b = res.result.bandwidth_audit || res.result;
    const isLimited = b.is_limited === true;
    bodyHtml += `
      <div class="verification-box ${isLimited ? "warning" : "verified"}">
        <div class="verif-header">
          <span class="verif-status">Bandwidth Inspection (${escapeHtml(b.interface || "eth1")})</span>
          <span class="badge ${isLimited ? "badge-warning" : "badge-success"}">${isLimited ? b.current_rate_mbps + " Mbps (Capped)" : "Full Line (Uncapped)"}</span>
        </div>
        <div class="verif-summary">
          <strong>Active Qdisc:</strong> <code>${escapeHtml(b.qdisc || "pfifo_fast")}</code>
          <br>
          <span style="color:var(--text-muted); font-size:11px;">${escapeHtml(b.details || (isLimited ? "Traffic control rate limit enforced via tc" : "Interface operating at baseline capacity"))}</span>
        </div>
      </div>
    `;
  }

  // 11. Direct rule presence verification (from verify_firewall_rule tool)
  if (res.result && res.result.rule_present !== undefined) {
    const r = res.result;
    const isFound = r.rule_present === true;
    bodyHtml += `
      <div class="verification-box ${isFound ? "verified" : "warning"}">
        <div class="verif-header">
          <span class="verif-status">Firewall Rule Check</span>
          <span class="badge ${isFound ? "badge-success" : "badge-warning"}">${isFound ? "PRESENT" : "NOT FOUND"}</span>
        </div>
        <div class="verif-summary">
          <strong>Rule:</strong> ${escapeHtml(r.action || "")} port ${escapeHtml(String(r.port || ""))} (${escapeHtml(r.protocol || "tcp")})
          <br>
          <span style="color:var(--text-muted); font-size:11px;">${isFound ? "Rule is active in the iptables table." : "Rule does not match any entry in the active firewall table."}</span>
        </div>
      </div>
    `;
  }

  // 11. Final outcome message from AI
  if (res.ai_response && (!intentMsg || res.ai_response.length > intentMsg.length || res.ai_response !== intentMsg)) {
    bodyHtml += `
      <div class="ai-text md-body" style="margin-top: 12px; font-size: 13.5px; line-height: 1.6;">
        ${renderMarkdown(res.ai_response)}
      </div>
    `;
  }

  row.innerHTML = `
    <div class="avatar ai">AI</div>
    <div class="message-bubble">${bodyHtml}</div>
  `;

  stream.appendChild(row);
  scrollToBottom();
}

function appendErrorMessage(err) {
  const stream = document.getElementById("chat-stream");
  const row = document.createElement("div");
  row.className = "message-row";
  row.innerHTML = `
    <div class="avatar ai" style="background: var(--danger);">!</div>
    <div class="message-bubble">
      <div class="ai-card" style="border-color: var(--danger-bg);">
        <div class="ai-meta" style="color: var(--danger);">System Notification</div>
        <div class="ai-text" style="color: #fda4af;">${escapeHtml(err)}</div>
      </div>
    </div>
  `;
  stream.appendChild(row);
  scrollToBottom();
}

function clearChat() {
  const stream = document.getElementById("chat-stream");
  stream.innerHTML = `
    <div class="welcome-card" id="welcome-hero">
      <div class="welcome-badge">AI INTENT · MCP POLICY · INDEPENDENT VERIFICATION</div>
      <h1>Network Operations</h1>
      <p>
        Experience true AI-driven network administration. Natural language commands are parsed into structured MCP tool calls, authoritatively validated against security policies, and independently verified via live kernel inspection and socket probing.
      </p>
      <div class="quick-chip-row">
        <button class="chip-btn" onclick="handlePreset('What is the status of the network firewall?')">"Check firewall status"</button>
        <button class="chip-btn" onclick="handlePreset('Block port 9999 TCP')">"Block port 9999 TCP"</button>
        <button class="chip-btn" onclick="handlePreset('Check connectivity to port 9999 on 127.0.0.1')">"Test port 9999 reachability"</button>
        <button class="chip-btn" onclick="handlePreset('Block port 22')">"Try blocking SSH (22)"</button>
      </div>
    </div>
  `;
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.clear_history();
  }
}

function scrollToBottom() {
  const stream = document.getElementById("chat-stream");
  if (stream) {
    setTimeout(() => {
      stream.scrollTop = stream.scrollHeight;
    }, 50);
  }
}

function escapeHtml(str) {
  if (typeof str !== "string") str = JSON.stringify(str);
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/**
 * Lightweight markdown-to-HTML renderer for Groq conversational replies.
 * Handles: headers, bold/italic, inline code, fenced code blocks, tables, lists.
 */
function renderMarkdown(text) {
  if (typeof text !== "string") text = String(text);

  // 1. Fenced code blocks  ```lang\n...\n```
  text = text.replace(/```[\w]*\n?([\s\S]*?)```/g, (_, code) =>
    `<pre class="md-code-block"><code>${escapeHtml(code.trim())}</code></pre>`
  );

  // 2. Process line by line for tables, headings, lists
  const lines = text.split("\n");
  let html = "";
  let inTable = false;
  let inList = false;
  let tableRows = [];

  const flushTable = () => {
    if (tableRows.length < 2) { html += tableRows.join("\n"); tableRows = []; inTable = false; return; }
    let tHtml = `<table class="md-table"><thead><tr>`;
    const headers = tableRows[0].split("|").filter((_, i, a) => i > 0 && i < a.length - 1);
    headers.forEach(h => tHtml += `<th>${inlineMarkdown(h.trim())}</th>`);
    tHtml += `</tr></thead><tbody>`;
    for (let i = 2; i < tableRows.length; i++) {
      const cells = tableRows[i].split("|").filter((_, j, a) => j > 0 && j < a.length - 1);
      tHtml += `<tr>${cells.map(c => `<td>${inlineMarkdown(c.trim())}</td>`).join("")}</tr>`;
    }
    tHtml += `</tbody></table>`;
    html += tHtml;
    tableRows = []; inTable = false;
  };

  const flushList = () => { if (inList) { html += `</ul>`; inList = false; } };

  lines.forEach(line => {
    // Table row detection
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      flushList();
      inTable = true;
      tableRows.push(line.trim());
      return;
    }
    if (inTable) { flushTable(); }

    // Separator line (---)
    if (/^[-*_]{3,}$/.test(line.trim())) { flushList(); html += `<hr class="md-hr">`; return; }

    // Headings
    const h3 = line.match(/^###\s+(.*)/);
    const h2 = line.match(/^##\s+(.*)/);
    const h1 = line.match(/^#\s+(.*)/);
    if (h3) { flushList(); html += `<h3 class="md-h3">${inlineMarkdown(h3[1])}</h3>`; return; }
    if (h2) { flushList(); html += `<h2 class="md-h2">${inlineMarkdown(h2[1])}</h2>`; return; }
    if (h1) { flushList(); html += `<h1 class="md-h1">${inlineMarkdown(h1[1])}</h1>`; return; }

    // Bullet list items (- or *)
    const li = line.match(/^[-*]\s+(.*)/);
    if (li) {
      if (!inList) { html += `<ul class="md-list">`; inList = true; }
      html += `<li>${inlineMarkdown(li[1])}</li>`;
      return;
    }
    flushList();

    // Empty line → paragraph break
    if (line.trim() === "") { html += `<div class="md-spacer"></div>`; return; }

    // Normal paragraph line
    html += `<p class="md-p">${inlineMarkdown(line)}</p>`;
  });

  if (inTable) flushTable();
  flushList();
  return html;
}

function inlineMarkdown(text) {
  // Escape HTML first
  text = text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  // Bold **text** or __text__
  text = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/__(.*?)__/g, "<strong>$1</strong>");
  // Italic *text* or _text_
  text = text.replace(/\*(.*?)\*/g, "<em>$1</em>");
  text = text.replace(/_(.*?)_/g, "<em>$1</em>");
  // Inline code `text`
  text = text.replace(/`([^`]+)`/g, `<code class="md-inline-code">$1</code>`);
  return text;
}

