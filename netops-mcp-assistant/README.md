# 🛡️ NetOps MCP Assistant

> **Intelligent Network Operations Assistant** — configure firewalls, set bandwidth limits, and run diagnostics through natural language commands powered by FastMCP and a beautiful Copilot-like web interface.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastMCP](https://img.shields.io/badge/FastMCP-latest-purple)](https://github.com/jlowin/fastmcp)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-green?logo=fastapi)](https://fastapi.tiangolo.com)
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
  - [Local (venv)](#option-1-local-with-venv-recommended-for-development)
  - [Docker](#option-2-docker-recommended-for-production)
- [Web UI](#-web-ui)
- [MCP Tools Reference](#-mcp-tools-reference)
- [Example Commands](#-example-commands)
- [Policy Rules](#-policy-rules)
- [Test Cases & Validation](#-test-cases--validation)
- [Troubleshooting](#-troubleshooting)

---

## 🌐 Overview

NetOps MCP Assistant bridges the gap between human intent and network configuration. Instead of remembering complex `iptables` or `tc` commands, you type natural language:

> *"Block port 8080"* → validates policy → runs `iptables -A INPUT -p tcp --dport 8080 -j DROP`

The assistant enforces **security policies** (protected ports, allowed actions, bandwidth limits) before executing any command, and streams each step live in the UI — just like GitHub Copilot's activity panel.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   Browser (localhost:8000)                    │
│  ┌─────────────┐   SSE stream   ┌──────────────────────────┐ │
│  │  Chat UI    │ ◄──────────── │  Activity Panel (live)   │ │
│  │ (index.html)│               │  🧠 Parsing...            │ │
│  │  app.js     │ POST /chat     │  🛡️ Policy check...       │ │
│  └──────┬──────┘               │  ⚡ Executing cmd...      │ │
│         │                      │  ✅ Done                  │ │
└─────────┼────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────┐
│     FastAPI Bridge (ui_server.py│  port 8000
│  • Rule-based command parser    │
│  • SSE event streaming          │
│  • Policy enforcement           │
└──────────┬──────────────────────┘
           │  direct function calls
           ▼
┌─────────────────────────────────┐
│     MCP Server (server.py)      │
│  FastMCP · 4 registered tools   │
└────────┬──────────┬─────────────┘
         │          │
         ▼          ▼
┌──────────────┐  ┌──────────────────┐
│ tools/       │  │ tools/           │
│ net_ops.py   │  │ verifier.py      │
│ iptables, tc │  │ ping, iperf3     │
└──────────────┘  └──────────────────┘
         │
         ▼
  Linux Kernel (NET_ADMIN)
```

---

## ✨ Features

| Feature | Details |
|---------|---------|
| 🔥 **Firewall Management** | Apply ACCEPT/DROP/REJECT rules via iptables |
| 📡 **Bandwidth Limiting** | Shape traffic with `tc qdisc tbf` |
| 🌐 **Network Diagnostics** | Run `ping` and `iperf3` tests |
| 📋 **Rule Listing** | View all active iptables INPUT rules |
| 🛡️ **Policy Enforcement** | Pre-execution validation against YAML policies |
| ⚡ **Live Activity Stream** | Server-Sent Events (SSE) for real-time step display |
| 🎨 **Copilot-like UI** | Dark glassmorphism UI with animated activity panel |
| 🐳 **Docker Ready** | Full containerized deployment with `NET_ADMIN` capability |

---

## 📁 Project Structure

```
netops-mcp-assistant/
│
├── server.py              # MCP server — 4 FastMCP tools registered
├── ui_server.py           # FastAPI bridge — serves UI + SSE stream
│
├── tools/
│   ├── __init__.py
│   ├── net_ops.py         # NetworkOps class — iptables, tc, subprocess
│   └── verifier.py        # DiagnosticVerifier — ping, iperf3 parsing
│
├── rules/
│   └── policies.yaml      # Security & bandwidth policy definitions
│
├── static/                # Web UI assets
│   ├── index.html         # Copilot-like chat interface
│   ├── style.css          # Dark glassmorphism design
│   └── app.js             # SSE handler, markdown renderer, activity panel
│
├── tests/
│   └── test_assistant.py  # pytest test suite (7 tests)
│
├── Dockerfile             # Python 3.11-slim + iptables + iproute2 + ping + iperf3
├── compose.yaml           # Docker Compose (mcp-server + netops-ui)
└── requirements.txt       # Python dependencies
```

---

## 🔧 Prerequisites

### Local Development
- **Python 3.11+**  
- **pip** / **venv**
- **iptables** — `sudo apt install iptables`  
- **iproute2 (tc)** — `sudo apt install iproute2`  
- **iputils-ping** — `sudo apt install iputils-ping`  
- **iperf3** (optional, for bandwidth tests) — `sudo apt install iperf3`

### Docker Deployment
- **Docker Engine 24+** — `sudo apt install docker.io`
- **Docker Compose v2** — `sudo apt install docker-compose-v2`

> **Note:** `iptables` and `tc` require `root` (or `CAP_NET_ADMIN`). Docker handles this automatically with `cap_add: NET_ADMIN`. For local runs, prefix with `sudo`.

---

## 🚀 Setup & Running

### Option 1: Local Terminal CLI (recommended)

```bash
# 1. Navigate to project
cd /home/set-iitgn-vm/Desktop/netops-mcp-assistant

# 2. Install all dependencies
pip install -r requirements.txt

# 3. Run tests (no sudo needed — policy tests only)
pytest tests/ -v

# 4. Launch the interactive terminal assistant
#    ⚠️  sudo required for iptables/tc to actually execute
sudo python3 assistant.py

#    OR without sudo (diagnostics & policy tests still work):
python3 assistant.py
```

### Option 2: Docker (recommended for production)

```bash
# Build and start
sudo docker compose up --build

# View logs
sudo docker compose logs -f netops-ui

# Stop
sudo docker compose down
```

### Run Only the MCP Server (stdio mode)

```bash
python3 server.py
```

---

## 🖥️ Terminal Interface

Run `python3 assistant.py` (or `sudo python3 assistant.py` for full iptables/tc access).

### Session Flow

```
╔══════════════════════════════════════════════════════════╗
║  🛡️  NetOps MCP Assistant                               ║
║  Type help for commands · exit to quit                  ║
╚══════════════════════════════════════════════════════════╝

netops> block port 8080
────────────────────────────────────────────────────────
  🧠  Parsing command          → "block port 8080"
  🔍  Intent identified        → firewall → DROP port 8080/tcp
  🛡️   Validating policy        → protected ports: 22, 53, 5000
  ✅  Policy check passed      → port 8080 is not protected
  ⚡  Executing firewall command
     $ iptables -A INPUT -p tcp --dport 8080 -j DROP
  ✅  Rule applied successfully
╭──────────────── Firewall Rule Applied ────────────────╮
│  Action      DROP                                     │
│  Port        8080/tcp                                 │
│  Source IP   any                                      │
╰───────────────────────────────────────────────────────╯

netops> block port 22
────────────────────────────────────────────────────────
  🧠  Parsing command          → "block port 22"
  🔍  Intent identified        → firewall → DROP port 22/tcp
  🛡️   Validating policy        → protected ports: 22, 53, 5000
  🚫  POLICY REJECTED          → Port 22 is PROTECTED (prevents lockouts)

  ✘  Port 22 is PROTECTED by security policy.
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

**Policy constraints:** Ports 22, 53, 5000 are protected and cannot be changed.

---

### 2. `set_bandwidth_limit`
Apply traffic shaping on a network interface using `tc`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `interface` | str | Interface name e.g. `eth0`, `ens3` |
| `rate_mbps` | int | Speed limit in Mbps (must be 1–100) |

**Policy constraints:** Rate must be between `min_bandwidth_mbps` (1) and `max_bandwidth_mbps` (100).

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

No parameters required.

---

## 💬 Example Commands

Type these directly into the UI or use the sidebar chips:

```
# Firewall rules
Block port 8080
Allow port 443
Drop UDP traffic on port 9090
Block port 8080 from 192.168.1.100
Reject TCP port 3306

# Bandwidth limiting
Limit bandwidth to 10 Mbps on eth0
Throttle eth0 to 50 mbps
Set bandwidth cap to 100 Mbps

# Diagnostics
Ping 127.0.0.1
Check connectivity to 8.8.8.8
Run iperf3 test to 192.168.1.10

# List rules
List firewall rules
Show all iptables rules

# Policy rejection examples (try these!)
Block port 22       → POLICY REJECTION: SSH is protected
Block port 53       → POLICY REJECTION: DNS is protected
Limit bandwidth to 500 Mbps → POLICY REJECTION: out of range
```

---

## 📜 Policy Rules

Defined in `rules/policies.yaml`:

```yaml
security_policy:
  protected_ports: [22, 53, 5000]   # SSH, DNS, MCP — cannot be modified
  allowed_actions: [ACCEPT, DROP, REJECT]
  forbidden_commands:
    - "FLUSH_ALL"
    - "iptables -F"
    - "tc qdisc del dev eth0 root"

bandwidth_policy:
  min_bandwidth_mbps: 1             # Minimum allowed rate
  max_bandwidth_mbps: 100           # Maximum allowed rate
  default_latency_ms: 20
  allowed_qdisc: [tbf, htb]        # Allowed queuing disciplines

verification:
  ping_count: 4
  max_allowed_loss_percent: 0.0
  iperf_duration_seconds: 5
```

To modify policies, edit `rules/policies.yaml` and restart the server.

---

## 🧪 Test Cases & Validation

### Running Tests

```bash
source venv/bin/activate
pytest tests/test_assistant.py -v
```

### Test Coverage

| Test | Description | Expected |
|------|-------------|----------|
| `test_protected_port_ssh` | Try to DROP port 22 | `POLICY REJECTION` |
| `test_protected_port_dns` | Try to DROP port 53 | `POLICY REJECTION` |
| `test_invalid_action` | Use unknown action `DESTROY` | `POLICY REJECTION` |
| `test_bandwidth_too_high` | Set 500 Mbps | `POLICY REJECTION` |
| `test_bandwidth_too_low` | Set 0 Mbps | `POLICY REJECTION` |
| `test_invalid_diagnostic_mode` | Use `traceroute` mode | `Invalid mode` |
| `test_ping_localhost` | Ping 127.0.0.1 | `PASS` |

### Expected Output

```
tests/test_assistant.py::test_protected_port_ssh       PASSED
tests/test_assistant.py::test_protected_port_dns       PASSED
tests/test_assistant.py::test_invalid_action           PASSED
tests/test_assistant.py::test_bandwidth_too_high       PASSED
tests/test_assistant.py::test_bandwidth_too_low        PASSED
tests/test_assistant.py::test_invalid_diagnostic_mode  PASSED
tests/test_assistant.py::test_ping_localhost           PASSED

7 passed in X.Xs
```

### Validation Results

All policy tests pass without `sudo` — they never reach `iptables`. The `ping` test requires network access to localhost (always available). `iperf3` tests require a running iperf3 server.

---

## 🔴 Troubleshooting

### `Permission denied` on iptables/tc
```bash
# Run with sudo
sudo python ui_server.py
# OR use Docker (handles permissions automatically)
sudo docker compose up --build
```

### `ModuleNotFoundError: fastmcp`
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### `Address already in use` on port 8000
```bash
# Find and kill the process
lsof -ti:8000 | xargs kill -9
# OR use a different port
uvicorn ui_server:app --port 8001
```

### `iperf3: error - unable to connect`
iperf3 mode requires a running iperf3 server on the target:
```bash
# On the target machine:
iperf3 -s
# Then test from the UI
```

### Docker: `Cannot connect to the Docker daemon`
```bash
sudo systemctl start docker
# Add yourself to docker group (requires logout):
sudo usermod -aG docker $USER
```

---

## 📊 Technology Stack

| Component | Technology |
|-----------|-----------|
| MCP Server | [FastMCP](https://github.com/jlowin/fastmcp) |
| UI Backend | [FastAPI](https://fastapi.tiangolo.com) + [Uvicorn](https://uvicorn.org) |
| Streaming | Server-Sent Events (SSE) |
| Frontend | Vanilla HTML/CSS/JS (no framework) |
| Firewall | `iptables` (Linux netfilter) |
| Bandwidth | `tc` (Linux traffic control) |
| Diagnostics | `ping`, `iperf3` |
| Config | YAML (`pyyaml`) |
| Testing | `pytest` |
| Deployment | Docker + Docker Compose |

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built for the NetOps MCP Assistant project — demonstrating intelligent, policy-enforced network automation with a modern Copilot-style interface.*
