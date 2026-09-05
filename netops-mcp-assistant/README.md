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

## 🚀 Setup & Installation

### Prerequisites
- Python 3.11 or 3.12
- Linux environment or Docker (for real `iptables` / `tc` execution; Windows supported for GUI/CLI/mock development)

### 1. Install Dependencies
```bash
cd netops-mcp-assistant
pip install -r requirements.txt
```

---

## 🔑 Configuring the LLM

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` to configure your preferred LLM:

### Option A: Anthropic Claude (Recommended)
```ini
LLM_PROVIDER=claude
LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### Option B: Groq (Ultra-Fast Free Tier)
```ini
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=your_groq_api_key_here
```

### Option C: OpenRouter (Free Tier Available)
```ini
LLM_PROVIDER=openrouter
LLM_MODEL=meta-llama/llama-3.1-8b-instruct:free
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

### Option D: Ollama (100% Local & Offline)
```ini
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
OLLAMA_BASE_URL=http://localhost:11434
```

> **Note**: If no API key is provided, the assistant transparently falls back to its deterministic pattern-matching engine and clearly indicates this in the UI.

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
