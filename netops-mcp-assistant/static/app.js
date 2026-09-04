/**
 * NetOps MCP Assistant — Copilot UI JavaScript
 * Handles: SSE streaming, chat rendering, activity steps, markdown, auto-resize
 */

'use strict';

// ── State ────────────────────────────────────────────────────────────────────
let isProcessing = false;
let messageCount = 0;

// ── DOM refs ─────────────────────────────────────────────────────────────────
const messagesEl   = document.getElementById('messages');
const welcomeEl    = document.getElementById('welcome');
const inputEl      = document.getElementById('messageInput');
const sendBtn      = document.getElementById('sendBtn');
const activityList = document.getElementById('activityList');
const activityDot  = document.getElementById('activityDot');
const activityEmpty= document.getElementById('activityEmpty');
const thinkingBar  = document.getElementById('thinkingBar');
const thinkingText = document.getElementById('thinkingText');

// ── Input auto-resize ────────────────────────────────────────────────────────
inputEl.addEventListener('input', () => {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + 'px';
});

// ── Keyboard handler ─────────────────────────────────────────────────────────
inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// ── Insert chip text into input ───────────────────────────────────────────────
function insertChip(text) {
  inputEl.value = text;
  inputEl.focus();
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + 'px';
}

// ── Clear chat ────────────────────────────────────────────────────────────────
function clearChat() {
  messagesEl.innerHTML = '';
  messagesEl.appendChild(welcomeEl);
  welcomeEl.style.display = 'flex';
  messageCount = 0;
  clearActivity();
}

// ── Clear activity ────────────────────────────────────────────────────────────
function clearActivity() {
  activityList.innerHTML = '';
  activityList.appendChild(activityEmpty);
  activityEmpty.style.display = 'flex';
  setActivityDot(false);
  hideThinking();
}

// ── Run all test scenarios ────────────────────────────────────────────────────
const TEST_COMMANDS = [
  'Block port 22',
  'Block port 8080',
  'Ping 127.0.0.1',
  'List firewall rules',
];

async function runAllTests() {
  for (const cmd of TEST_COMMANDS) {
    await new Promise(resolve => {
      const check = () => { if (!isProcessing) resolve(); else setTimeout(check, 200); };
      check();
    });
    insertChip(cmd);
    await new Promise(r => setTimeout(r, 300));
    await sendMessage();
    await new Promise(r => setTimeout(r, 800));
  }
}

// ── Activity dot state ────────────────────────────────────────────────────────
function setActivityDot(active) {
  activityDot.classList.toggle('active', active);
}

function showThinking(text = 'Processing...') {
  thinkingBar.classList.add('active');
  thinkingText.textContent = text;
  setActivityDot(true);
}

function hideThinking() {
  thinkingBar.classList.remove('active');
  setActivityDot(false);
}

// ── Add activity step ─────────────────────────────────────────────────────────
function addActivityStep(event) {
  // Remove empty state
  if (activityEmpty.parentNode === activityList) {
    activityEmpty.style.display = 'none';
  }

  const step = document.createElement('div');
  const statusClass = event.status || 'thinking';
  step.className = `activity-step ${statusClass}`;

  const now = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

  step.innerHTML = `
    <div class="step-icon-wrap ${statusClass}">
      <span>${event.icon || '⚙️'}</span>
    </div>
    <div class="step-content">
      <div class="step-text">${escHtml(event.text || '')}</div>
      ${event.detail ? `<div class="step-detail">${escHtml(event.detail)}</div>` : ''}
    </div>
    <div class="step-time">${now}</div>
  `;

  activityList.appendChild(step);
  activityList.scrollTop = activityList.scrollHeight;

  // Update thinking text if still thinking
  if (statusClass === 'thinking') {
    showThinking(event.text || 'Processing...');
  }
}

// ── Append user message ───────────────────────────────────────────────────────
function appendUserMessage(text) {
  hideWelcome();
  const time = new Date().toLocaleTimeString('en-US', { hour12: true, hour: '2-digit', minute: '2-digit' });
  const msg = document.createElement('div');
  msg.className = 'msg user';
  msg.innerHTML = `
    <div class="msg-avatar">👤</div>
    <div class="msg-body">
      <div class="msg-bubble">${escHtml(text)}</div>
      <div class="msg-time">${time}</div>
    </div>
  `;
  messagesEl.appendChild(msg);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  messageCount++;
}

// ── Append assistant message ──────────────────────────────────────────────────
function appendAssistantMessage(data) {
  const time = new Date().toLocaleTimeString('en-US', { hour12: true, hour: '2-digit', minute: '2-digit' });
  const success = data.success !== false;
  const msg = document.createElement('div');
  msg.className = 'msg assistant';

  const rendered = renderMarkdown(data.message || data.suggestion || '');

  msg.innerHTML = `
    <div class="msg-avatar">🛡️</div>
    <div class="msg-body">
      <div class="msg-bubble ${success ? 'success' : 'error'}">${rendered}</div>
      <div class="msg-time">${time}</div>
    </div>
  `;
  messagesEl.appendChild(msg);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ── Hide welcome screen ───────────────────────────────────────────────────────
function hideWelcome() {
  if (welcomeEl && welcomeEl.parentNode === messagesEl) {
    welcomeEl.style.display = 'none';
  }
}

// ── Simple Markdown renderer ──────────────────────────────────────────────────
function renderMarkdown(text) {
  return text
    // Code blocks
    .replace(/```([\s\S]*?)```/g, (_, code) => `<pre>${escHtml(code.trim())}</pre>`)
    // Inline code
    .replace(/`([^`]+)`/g, (_, code) => `<code>${escHtml(code)}</code>`)
    // Bold
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // Tables — GFM style
    .replace(/(\|.+\|\n?\|[-| :]+\|\n?(?:\|.+\|\n?)*)/g, renderTable)
    // Newlines
    .replace(/\n/g, '<br>');
}

function renderTable(tableStr) {
  const rows = tableStr.trim().split('\n').filter(r => r.trim());
  if (rows.length < 2) return tableStr;
  const headers = rows[0].split('|').map(c => c.trim()).filter(Boolean);
  const dataRows = rows.slice(2); // skip separator

  let html = '<table><thead><tr>';
  headers.forEach(h => { html += `<th>${escHtml(h)}</th>`; });
  html += '</tr></thead><tbody>';
  dataRows.forEach(row => {
    const cells = row.split('|').map(c => c.trim()).filter(Boolean);
    html += '<tr>';
    cells.forEach(c => { html += `<td>${c}</td>`; }); // allow HTML in cells for emoji
    html += '</tr>';
  });
  html += '</tbody></table>';
  return html;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Send message via SSE ──────────────────────────────────────────────────────
async function sendMessage() {
  const message = inputEl.value.trim();
  if (!message || isProcessing) return;

  isProcessing = true;
  sendBtn.disabled = true;
  inputEl.disabled = true;
  inputEl.style.height = '48px';

  appendUserMessage(message);
  inputEl.value = '';

  // Clear previous activity
  activityList.innerHTML = '';
  activityList.appendChild(activityEmpty);
  activityEmpty.style.display = 'none';
  showThinking('Sending command...');

  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop(); // keep incomplete chunk

      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        try {
          const data = JSON.parse(part.slice(6));

          if (data.type === 'activity') {
            addActivityStep(data);
          } else if (data.type === 'result') {
            hideThinking();
            appendAssistantMessage(data);
          } else if (data.type === 'done') {
            hideThinking();
          }
        } catch (e) {
          console.warn('Parse error:', e, part);
        }
      }
    }

  } catch (err) {
    hideThinking();
    addActivityStep({
      icon: '❌',
      status: 'error',
      text: 'Connection error',
      detail: err.message
    });
    appendAssistantMessage({
      success: false,
      message: `**Connection error:** ${err.message}\n\nMake sure the server is running:\n\`\`\`\npython ui_server.py\n\`\`\``
    });
  } finally {
    isProcessing = false;
    sendBtn.disabled = false;
    inputEl.disabled = false;
    inputEl.focus();
  }
}
