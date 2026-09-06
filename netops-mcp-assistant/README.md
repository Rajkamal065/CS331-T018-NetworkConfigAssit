# 🛡️ NetOps MCP Assistant

> **Autonomous AI-Powered Network Operations Desktop Assistant** — configure firewalls, manage bandwidth limits, query listening ports, and run network diagnostics through genuine AI natural language reasoning powered by Claude / Groq / OpenRouter, an authoritative FastMCP server via stdio transport, and independent dual-layer verification.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastMCP](https://img.shields.io/badge/FastMCP-4.0+-purple)](https://github.com/jlowin/fastmcp)
[![pywebview](https://img.shields.io/badge/pywebview-Desktop-emerald)](https://pywebview.flowrl.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-blue?logo=docker)](https://docker.com)
[![Tests](https://img.shields.io/badge/Tests-26%20Passed-success)](tests/)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Subsystems & Security Boundaries](#-subsystems--security-boundaries)
- [Setup & Installation](#-setup--installation)
- [Configuring the LLM (Claude, Groq, etc.)](#-configuring-the-llm)
- [Running the Desktop Assistant](#-running-the-desktop-assistant)
- [Interactive Live Demo & Verification](#-interactive-live-demo--verification)
- [FastMCP Tools Reference](#-fastmcp-tools-reference)
- [Automated Test Suite](#-automated-test-suite)

---

## 🌐 Overview

NetOps MCP Assistant delivers a professional desktop experience for network administrators. Unlike superficial chatbots that match canned keywords, NetOps uses an end-to-end architecture:

1. **Natural Language Reasoning**: The user's request is interpreted by a genuine LLM (Anthropic Claude, Groq, OpenRouter, or Ollama) using structured tool calling schemas.
2. **Authoritative Security Enforcement**: The LLM is strictly an intent interpreter, **never a security authority**. The request is dispatched over stdio to an authoritative FastMCP server which validates policies in `rules/policies.yaml`.
3. **Execution Layer**: Approved actions execute via safe subprocess argument arrays without `shell=True`.
4. **Independent Dual-Layer Verification**: The verification engine independently probes the live socket state and inspects the kernel table to prove whether changes took effect.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│             HTML5 / CSS3 / JavaScript Frontend               │
│     • Modern slate theme with live subsystem health cards     │
│     • Visual operation timeline & independent verification    │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│             pywebview Desktop Application Window             │
│            • Native desktop wrapper (app.py)                 │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│              Python Bridge (NetOpsBridge)                    │
│     • Orchestrates LLM, MCP, and Verification pipelines       │
└──────────────┬───────────────────────────────┬───────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────────┐  ┌────────────────────────────┐
│      LLM Client              │  │      MCP Client            │
│ (Claude / Groq / OpenRouter) │  │ (stdio ClientSession)      │
└──────────────────────────────┘  └────────────┬───────────────┘
                                               │
                                               │ REAL stdio transport
                                               ▼
┌──────────────────────────────────────────────────────────────┐
│                   FastMCP Server (server.py)                 │
│    • Authoritative Security Boundary                         │
│    • 8 registered MCP tools                                  │
│    • Enforces policies.yaml (arbitrary ports, protected IPs) │
└──────────────┬───────────────────────────────┬───────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────────┐  ┌────────────────────────────┐
│ tools/net_ops.py             │  │ tools/verifier.py          │
│ (iptables, tc, ss execution) │  │ (independent socket probe, │
│                              │  │  dual-layer verification)  │
└──────────────┬───────────────┘  └────────────────────────────┘
               │
               ▼
       Linux Kernel (NET_ADMIN)
```

---

## 🔒 Subsystems & Security Boundaries

### 1. Invariants That Are Never Bypassed
- **Protected Ports**: Ports `22` (SSH), `53` (DNS), and `5000` (Agent infrastructure) can **never** be blocked or dropped. Any attempt triggers an immediate `POLICY_REJECTION`.
- **Protected Interfaces**: `eth0` and `lo` can never have bandwidth restrictions applied.
- **Arbitrary Ports**: Ports `1-65535` are permitted unless in the protected list (`allow_arbitrary_ports: true`).
- **No Shell Injection**: All commands execute using argument arrays (`subprocess.run(["iptables", ...])`), never `shell=True`.
- **Independent Verification**: A command returning status code 0 does not mean the port is blocked. The verifier actively tests socket reachability.

---

## 🎯 LLM, MCP, and Verification: Three Separated Concerns

NetOps implements **strict separation of concerns** between three independent layers:

### 1. **LLM = Intent Interpretation (Human Understanding)**
- The LLM is **responsible for understanding natural language**.
- It converts user intent (e.g., `"block ppt 9999"`, `"drop incoming TCP on port 9999"`, `"prevent traffic on 9999"`) into **structured tool calls**.
- The LLM receives schema definitions for all MCP tools and must choose the appropriate tool and arguments.
- **The LLM is NOT a security authority**. It cannot and does not enforce policies.

#### Example: Natural Language Variations
All of these user inputs should resolve to the same structured intent:
```
User: "block port 9999"
User: "drop 9999"
User: "block ppt 9999" (typo)
User: "prevent TCP traffic on 9999"
User: "close port 9999"
User: "stop incoming connections on 9999"

↓ All understood by LLM as ↓

Tool Call: configure_firewall(action="DROP", port=9999, protocol="tcp", source_ip="")
```

**Without an LLM configured**, the assistant cannot interpret natural language and will return an error. There is **no silent regex fallback**.

### 2. **MCP = Authoritative Policy & Execution (Security Authority)**
- The MCP server is the **only entity that can execute network operations**.
- It reads `rules/policies.yaml` and enforces all security policies **server-side**.
- Even if the LLM perfectly understands a user request, the MCP server may reject it if policy forbids it.
- Example: `configure_firewall(action="DROP", port=22, ...)` will be rejected with `POLICY_REJECTION` regardless of how clearly the user requested it.

### 3. **Verification = Independent Proof (Trust But Verify)**
- After the MCP server executes an operation, the verifier independently probes the system.
- It does **not trust** the exit code or MCP output.
- It actively tests socket reachability and inspects kernel rules.
- This ensures that requested changes actually took effect.

#### Example: Complete Pipeline
```
User: "block port 9999"
  ↓
LLM interprets → { tool: "configure_firewall", arguments: { action: "DROP", port: 9999, protocol: "tcp" } }
  ↓
MCP server checks policy → "Port 9999 is arbitrary (allowed)"
  ↓
MCP executes → iptables -I INPUT -p tcp --dport 9999 -j DROP
  ↓
Verifier probes → Attempts TCP connection to port 9999 → Timeout/refused
  ↓
User sees ✓ Verified: Port 9999 is now blocked
```

#### Example: Policy Rejection
```
User: "block SSH"
  ↓
LLM interprets → { tool: "configure_firewall", arguments: { action: "DROP", port: 22, protocol: "tcp" } }
  ↓
MCP server checks policy → "Port 22 is protected. REJECTED."
  ↓
User sees ✗ POLICY_REJECTION: Port 22 (SSH) is protected by policy
```

---

## 🚀 Setup & Installation

### ⚡ Quickest Start: Docker (All-in-One)

Everything bundled and ready. No separate Ollama setup needed!

```bash
# Build the image
docker build -t netops-assistant:latest .

# Run with Docker Compose (recommended)
docker-compose up
```

**That's it!** Access at http://localhost:5000

Features:
- ✅ Ollama (llama3.1) bundled and pre-configured
- ✅ All network tools (iptables, tc, ping, iperf3) included
- ✅ Zero external API dependencies
- ✅ Works on Windows, Mac, Linux
- ✅ Persistent model cache

Or use the convenience scripts:
- **Linux/Mac**: `bash run-docker.sh` → builds, runs, and cleans up
- **Windows**: `run-docker.bat` → same but for Windows CMD

### Prerequisites (Non-Docker)
- Python 3.11 or 3.12
- Linux environment (for real `iptables` / `tc` execution; Windows supported for GUI/CLI development)

### 1. Install Dependencies
```bash
cd netops-mcp-assistant
pip install -r requirements.txt
```

---

## 🔑 Configuring the LLM

### Quick Start (Recommended): Ollama (Free & Local)

Ollama is **completely free**, runs locally on your machine, and requires no API keys.

1. **Download Ollama** from [ollama.ai](https://ollama.ai)

2. **Pull the Llama 3.1 model**:
   ```bash
   ollama pull llama3.1
   ```

3. **Copy `.env.example` to `.env`**:
   ```bash
   cp .env.example .env
   ```

   The default configuration is already set to Ollama:
   ```ini
   LLM_PROVIDER=ollama
   LLM_MODEL=llama3.1
   OLLAMA_BASE_URL=http://localhost:11434
   ```

4. **Start Ollama** (in a separate terminal):
   ```bash
   ollama serve
   ```

5. **Run the assistant**:
   ```bash
   python app.py  # Desktop
   # or
   python assistant.py  # CLI
   ```

---

### Alternative Options

If you prefer a different provider, edit `.env` and uncomment one of these:

#### Option A: Groq (Ultra-Fast Free Tier)
```ini
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=your_free_key_from_console.groq.com
```

#### Option B: Anthropic Claude (Highest Quality, Paid)
```ini
LLM_PROVIDER=claude
LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=your_api_key_from_console.anthropic.com
```

#### Option C: OpenRouter (Free Tier Available)
```ini
LLM_PROVIDER=openrouter
LLM_MODEL=meta-llama/llama-3.1-8b-instruct:free
OPENROUTER_API_KEY=your_free_key_from_openrouter.ai
```

---

> **IMPORTANT**: Configuring an LLM provider is required for AI-powered intent interpretation. If no LLM is configured, the assistant will report "LLM provider not configured" and requests will not be processed.
>
> For development and testing ONLY, there is an offline deterministic pattern parser available explicitly as a test mode (not as a fallback).

---

## 💻 Running the Desktop Assistant

To launch the native desktop application:
```bash
python app.py
```

To run in terminal CLI mode:
```bash
python assistant.py
```

---

## 🧪 Interactive Live Demo & Verification

The repository includes a self-contained demonstration environment in `demo/`:

### Automated Verification Test
Run the end-to-end verification script:
```bash
python demo/validate_firewall.py
```
This tests:
1. Baseline socket reachability
2. Protected port lockout protection (Attempt to block port 22 &rarr; FastMCP policy rejection)
3. Arbitrary port blocking (Block port 9999 &rarr; Permitted and applied)
4. Dual-layer verification (Kernel rule check + TCP socket probe)
5. Port restoration (Allow port 9999)

### Interactive Service Demo
1. Start the demo TCP echo server on port 9999:
   ```bash
   python demo/start_demo.py --port 9999
   ```
2. In the desktop application (`python app.py`), issue commands:
   - `"Block port 9999 TCP with DROP"`
   - `"Check connectivity to port 9999"`
   - `"Allow port 9999 TCP"`
3. Stop the demo service:
   ```bash
   python demo/stop_demo.py
   ```

---

## 🛠️ FastMCP Tools Reference

The FastMCP server exposes 8 specialized tools:

| Tool Name | Parameters | Description |
|---|---|---|
| `configure_firewall` | `action`, `port`, `protocol`, `source_ip` | Apply ACCEPT/DROP/REJECT rules via iptables after authoritative policy check |
| `set_bandwidth_limit` | `interface`, `rate_mbps` | Apply traffic shaping with `tc qdisc tbf` while safeguarding protected interfaces |
| `run_diagnostics` | `target_ip`, `mode` (`ping` / `iperf3`) | Test reachability or throughput against a target host |
| `list_firewall_rules` | _(none)_ | Enumerate all active iptables INPUT chain rules |
| `check_listening_ports` | _(none)_ | Enumerate listening sockets on the host |
| `check_port_connectivity` | `port`, `host` | Actively test TCP connection reachability |
| `verify_firewall_rule` | `action`, `port`, `protocol` | Check kernel iptables table for rule existence |
| `validate_firewall_change` | `action`, `port`, `protocol` | Dual-layer verification: kernel table inspection + socket probe |

---

## 🧪 Automated Test Suite

Run the full pytest suite:
```bash
pytest tests/ -v
```

All 26 tests cover:
- Policy invariants (protected ports 22, 53, 5000; protected interfaces; arbitrary port 9999 acceptance)
- LLM schema validation and pattern-matching fallback parsing
- FastMCP stdio client connection and tool discovery
- Independent diagnostic verification
