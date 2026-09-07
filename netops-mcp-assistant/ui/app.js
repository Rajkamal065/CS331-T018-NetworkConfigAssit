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
    <div class="message-bubble">${escapeHtml(text)}</div>
    <div class="avatar user-av">U</div>
  `;
  stream.appendChild(row);
  scrollToBottom();
}

function appendLoadingCard(id) {
  const stream = document.getElementById("chat-stream");
  const row = document.createElement("div");
  row.className = "message-row";
  row.id = id;
  row.innerHTML = `
    <div class="avatar ai">AI</div>
    <div class="message-bubble">
      <div class="ai-card">
        <div class="ai-meta">Processing Network Request</div>
        <div class="step-indicator" style="flex-direction: row; gap: 8px; align-items: center;">
          <span class="step-dot running"></span>
          <span style="font-size: 0.85rem; color: var(--text-secondary);">Resolving intent, applying policy, and executing through MCP...</span>
        </div>
      </div>
    </div>
  `;
  stream.appendChild(row);
  scrollToBottom();
}

function removeElement(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}
function renderExecutionTerminal(execution) {
  if (!execution || typeof execution !== "object") return "";

  const command = execution.command;
  const stdout = execution.stdout || "";
  const stderr = execution.stderr || "";

  const returncode =
    execution.returncode !== undefined
      ? execution.returncode
      : execution.exit_code !== undefined
        ? execution.exit_code
        : null;

  // If no real command was executed, do not fabricate terminal output.
  if (!command) return "";

  const success = returncode === 0;
  const exitText =
    returncode === null ? "EXIT CODE —" : `EXIT CODE ${returncode}`;

  let output = "";

  if (stdout) {
    output += `
      <div class="terminal-output">${escapeHtml(stdout)}</div>
    `;
  }

  if (stderr) {
    output += `
      <div class="terminal-stderr">${escapeHtml(stderr)}</div>
    `;
  }

  if (!stdout && !stderr) {
    output = `
      <div class="terminal-empty">No command output.</div>
    `;
  }

  const mode = execution.execution_mode
    ? `<span class="execution-mode">${escapeHtml(execution.execution_mode)}</span>`
    : "";

  return `
    <div class="terminal-panel">

      <div class="terminal-header">
        <span class="terminal-title">Network Operation</span>

        <span class="terminal-exit ${success ? "success" : "failure"}">
          ${exitText}${mode}
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
function renderAssistantResponse(res) {
  const stream = document.getElementById("chat-stream");
  const row = document.createElement("div");
  row.className = "message-row";

  let bodyHtml = "";

  // 1. AI conversational response
  const aiText = res.ai_response || res.content;
  if (aiText) {
    bodyHtml += `<div class="ai-text">${escapeHtml(aiText)}</div>`;
  }

  // 2. Execution Timeline
  if (res.timeline && res.timeline.length > 0) {
    bodyHtml += `<div class="timeline-container">
      <div class="timeline-title">Execution & Verification Trace</div>`;

    res.timeline.forEach((step, idx) => {
      let dotClass = "completed";
      if (step.status === "REJECTED" || step.status === "FAILED") dotClass = "rejected";
      else if (step.status === "RUNNING") dotClass = "running";
      else if (step.status === "WARNING") dotClass = "warning";

      const isLast = idx === res.timeline.length - 1;

      bodyHtml += `
        <div class="timeline-step">
          <div class="step-indicator">
            <div class="step-dot ${dotClass}"></div>
            ${!isLast ? '<div class="step-line"></div>' : ''}
          </div>
          <div class="step-body">
            <div class="step-name">${escapeHtml(step.title || step.step)}</div>
            ${step.detail ? `<div class="step-detail">${escapeHtml(step.detail)}</div>` : ''}
          </div>
        </div>
      `;
    });

    bodyHtml += `</div>`;
  }

  // 3. Real command execution output.
  // This comes directly from NetworkOps.
  // No terminal output is generated or fabricated by the frontend.
  if (res.execution) {
    bodyHtml += renderExecutionTerminal(res.execution);
  }

  // 4. Verification Card or Rejection Card
  if (res.type === "policy_rejection") {
    bodyHtml += `
      <div class="verification-box rejected">
        <div class="verif-header">
          <span class="verif-status">Authoritative Policy Rejection</span>
          <span class="badge badge-danger">Blocked by FastMCP</span>
        </div>
        <div class="verif-summary">
          <strong>Security Violation:</strong>
          ${escapeHtml(res.error || "Action prohibited by security policies")}
          <br>
          <strong>No network command was executed.</strong>
        </div>
      </div>
    `;
  } else if (res.verification) {
    const v = res.verification;
    const isVerified = v.status === "VERIFIED" || v.status === "PASS";
    const boxClass = isVerified ? "verified" : "warning";
    const statusText = isVerified
      ? "Independently Verified"
      : "Verification Caution";
    bodyHtml += `
      <div class="verification-box ${boxClass}">
        <div class="verif-header">
          <span class="verif-status">${statusText}</span>
          <span class="badge ${isVerified ? 'badge-success' : 'badge-warning'}">${escapeHtml(v.status || 'CHECKED')}</span>
        </div>
        <div class="verif-summary">${escapeHtml(v.summary || JSON.stringify(v))}</div>
      </div>
    `;
  }

  // Diagnostic metrics card (ping / iperf)
  if (res.result && (res.result.packet_loss_percent !== undefined || res.result.throughput_mbps !== undefined)) {
    const r = res.result;
    const isPass = r.status === "PASS";
    const statusClass = isPass ? "badge-success" : (r.status === "DEGRADED" ? "badge-warning" : "badge-danger");
    bodyHtml += `
      <div class="verification-box ${isPass ? 'verified' : 'warning'}" style="margin-top: 10px;">
        <div class="verif-header">
          <span class="verif-status">Diagnostic Reachability Metrics</span>
          <span class="badge ${statusClass}">${escapeHtml(r.status || 'DONE')}</span>
        </div>
        <div class="verif-summary">
          <strong>Target:</strong> ${escapeHtml(r.target || '127.0.0.1')} &nbsp;|&nbsp;
          <strong>Packet Loss:</strong> ${r.packet_loss_percent !== undefined ? r.packet_loss_percent + '%' : 'N/A'} &nbsp;|&nbsp;
          <strong>Avg Latency (RTT):</strong> ${r.avg_rtt_ms !== undefined ? r.avg_rtt_ms + ' ms' : 'N/A'}
          ${r.throughput_mbps !== undefined ? `&nbsp;|&nbsp; <strong>Throughput:</strong> ${r.throughput_mbps} Mbps` : ''}
        </div>
      </div>
    `;
  }

  // 4. Raw Output if available (e.g. firewall rules table or ports)
  if (res.result && res.result.rules) {
    bodyHtml += `
      <div>
        <span class="section-title">Active Firewall Rules Table</span>
        <pre class="code-block">${escapeHtml(res.result.rules)}</pre>
      </div>
    `;
  } else if (res.result && res.result.raw) {
    bodyHtml += `
      <div>
        <span class="section-title">Active Listening Sockets</span>
        <pre class="code-block">${escapeHtml(res.result.raw)}</pre>
      </div>
    `;
  }

  row.innerHTML = `
    <div class="avatar ai">AI</div>
    <div class="message-bubble">
      <div class="ai-card">
        <div class="ai-header">
          <span class="ai-meta">NetOps Orchestration Result</span>
        </div>
        ${bodyHtml}
      </div>
    </div>
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
