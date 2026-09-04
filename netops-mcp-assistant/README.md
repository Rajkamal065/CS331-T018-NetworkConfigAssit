# 🛡️ NetOps MCP Assistant

> **Intelligent Network Operations Assistant** — configure firewalls, set bandwidth limits, and run diagnostics through natural language commands powered by FastMCP, a dedicated stdio MCP Client, and a standalone Desktop GUI.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastMCP](https://img.shields.io/badge/FastMCP-4.0+-purple)](https://github.com/jlowin/fastmcp)
[![Docker](https://img.shields.io/badge/Docker-ready-blue?logo=docker)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Features](#-features)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Setup & Running](#-setup--running)
- [MCP Tools Reference](#-mcp-tools-reference)
- [Example Commands](#-example-commands)
- [Policy Rules](#-policy-rules)
- [Test Cases & Validation](#-test-cases--validation)

---

## 🌐 Overview

NetOps MCP Assistant bridges the gap between human intent and network configuration. Instead of remembering complex `iptables` or `tc` commands, you type natural language:

> *"Block port 8080"* → parses command → calls MCP tool over stdio → server validates policy → runs `iptables -A INPUT -p tcp --dport 8080 -j DROP`

The assistant enforces **security policies** (protected ports, allowed actions, protected interfaces, bandwidth ranges) inside the authoritative **FastMCP Server** before executing any command.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│             Tkinter Desktop GUI (app.py)                     │
│    or Interactive Terminal Assistant (assistant.py)          │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    MCP Client (mcp_client.py)                │
│    • Manages ClientSession over stdio transport              │
│    • Discovers & calls FastMCP server tools                 │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               │  REAL MCP stdio transport
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastMCP Server (server.py)                │
│    • Authoritative Security Boundary                         │
│    • 4 registered MCP tools                                  │
│    • Policy enforcement (rules/policies.yaml)               │
└──────────────┬───────────────────────────────┬───────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────────┐  ┌────────────────────────────┐
│ tools/net_ops.py             │  │ tools/verifier.py          │
│ (iptables, tc execution)     │  │ (ping, iperf3 diagnostic)  │
└──────────────┬───────────────┘  └────────────────────────────┘
               │
               ▼
      Linux Kernel (NET_ADMIN)
```

---

## ✨ Features

| Feature | Details |
|---------|---------|
| 🤖 **Real MCP Transport** | `mcp_client.py` communicates with `server.py` via official MCP `ClientSession` over stdio |
| 🔥 **Firewall Management** | Apply ACCEPT/DROP/REJECT rules via iptables over MCP |
| 📡 **Bandwidth Limiting** | Shape traffic with `tc qdisc tbf` while protecting critical interfaces |
| 🌐 **Network Diagnostics** | Run `ping` and `iperf3` tests with policy-configured parameters |
| 📋 **Rule Listing** | Query active iptables INPUT rules over MCP |
| 🛡️ **Authoritative Security** | Server-side policy enforcement against YAML policies |
| 🎨 **Standalone Desktop GUI** | Tkinter UI with non-blocking MCP execution |
| 🐳 **Docker Ready** | Containerized FastMCP server with `NET_ADMIN` capability |

---

## 📁 Project Structure

```
netops-mcp-assistant/
│
├── server.py              # FastMCP server — authoritative security boundary & 4 tools
├── mcp_client.py          # Dedicated MCP client module (stdio transport & ClientSession)
├── app.py                 # Standalone Tkinter Desktop GUI
├── assistant.py           # Interactive Terminal CLI assistant & natural language parser
│
├── tools/
│   ├── __init__.py
│   ├── net_ops.py         # Low-level NetworkOps class (iptables, tc, subprocess)
│   └── verifier.py        # Low-level DiagnosticVerifier class (ping, iperf3 parsing)
│
├── rules/
│   └── policies.yaml      # Central security & bandwidth policy definitions
│
├── tests/
│   ├── test_assistant.py       # Unit tests for policy validation
│   └── test_mcp_integration.py # Real MCP client/server integration tests
│
├── Dockerfile             # Container setup (Python 3.11-slim + networking tools)
├── compose.yaml           # Docker Compose configuration for FastMCP server
└── requirements.txt       # Dependencies (fastmcp, mcp, rich, pyyaml, pytest)
```

---

## 🔧 Prerequisites

### Local Development
- **Python 3.11+**
- **iptables** — `sudo apt install iptables`
- **iproute2 (tc)** — `sudo apt install iproute2`
- **iputils-ping** — `sudo apt install iputils-ping`
- **iperf3** (optional, for throughput tests) — `sudo apt install iperf3`

### Docker Deployment
- **Docker Engine 24+**
- **Docker Compose v2**

---

## 🚀 Setup & Running

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Tests

```bash
pytest tests/ -v
```

### 3. Launch Desktop GUI

```bash
python3 app.py
```

### 4. Launch Terminal Assistant

```bash
sudo python3 assistant.py
```

### 5. Run FastMCP Server Standalone

```bash
python3 server.py
```

---

## 📚 MCP Tools Reference

### 1. `configure_firewall`
Apply an iptables rule to block or allow traffic on a port.

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `action` | str | `ACCEPT`, `DROP`, or `REJECT` | required |
| `port` | int | Port number (1–65535) | required |
| `protocol` | str | `tcp` or `udp` | `tcp` |
| `source_ip` | str | Optional: restrict to source IP | `""` |

**Policy constraints:** Ports 22, 53, 5000 are protected and cannot be modified.

---

### 2. `set_bandwidth_limit`
Apply traffic shaping on a network interface using `tc`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `interface` | str | Interface name e.g. `eth0`, `ens3` |
| `rate_mbps` | int | Speed limit in Mbps (must be 1–100) |

**Policy constraints:** Rate must be between 1 and 100 Mbps. `eth0` and `lo` are protected interfaces.

---

### 3. `run_diagnostics`
Test network reachability or throughput.

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `target_ip` | str | IP address to test | required |
| `mode` | str | `ping` or `iperf3` | `ping` |

---

### 4. `list_firewall_rules`
Display all currently active iptables INPUT chain rules.

---

## 📜 Policy Rules

Defined in `rules/policies.yaml`:

```yaml
security_policy:
  protected_interfaces: ["eth0", "lo"]
  protected_ports: [22, 53, 5000]
  allowed_ports: [80, 443, 8080, 9090, 5201]
  allowed_actions: [ACCEPT, DROP, REJECT]

bandwidth_policy:
  min_bandwidth_mbps: 1
  max_bandwidth_mbps: 100
  default_latency_ms: 20
```

---

## 🧪 Test Cases & Validation

Run the full unit and real MCP integration test suite:

```bash
pytest tests/ -v
```

Tests verify tool discovery over stdio transport, protected port rejections, protected interface rejections, and diagnostic operations.

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.
