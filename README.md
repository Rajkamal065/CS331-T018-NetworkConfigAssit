# NetOps MCP Assistant

> **An AI-Powered Linux Network Configuration & Diagnostic Assistant**  
> Built for **CS331 — Computer Networks** | **Team: T018**  

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python)](https://python.org)
[![FastMCP](https://img.shields.io/badge/Protocol-FastMCP%204.0+-purple.svg)](https://modelcontextprotocol.io/)
[![Docker Ready](https://img.shields.io/badge/Docker-NET__ADMIN-2496ED.svg?logo=docker)](https://docker.com)
[![Tests Passing](https://img.shields.io/badge/Tests-Passing-success.svg)](netops-mcp-assistant/tests/)

---

## 📖 Quick Links
- 📄 **[Full Project Report (CS331_T018_Project_Report.md)](CS331_T018_Project_Report.md)**: Final report explaining project problem statement, MCP architecture, setup, and validation results.
- 🏗️ **[System Architecture (ARCHITECTURE.md)](ARCHITECTURE.md)**: Deep dive into the FastMCP server, rule-based policy engine, safe execution, and independent verification.
- 🤖 **[AI Usage Documentation (AI_Used/README.md)](AI_Used/README.md)**: Official course AI usage documentation (Tools, Prompts, Thought Process, and Stage-by-Stage details).
- 🐙 **[GitHub Setup Guide (README_GITHUB.md)](README_GITHUB.md)**: Clone instructions, environment setup, and deployment guide.

---

## 🎯 Project Description

This project builds an intelligent assistant using the **Model Context Protocol (MCP)** that helps network administrators configure devices securely and efficiently. It interprets user commands and applies configurations like firewall rules (`iptables`) and bandwidth limits (`tc`) based on predefined policies and network context.

The core contribution is demonstrating that AI can be safely integrated at the **kernel level** without compromising system stability:
* **The LLM interprets intent only.** It never directly runs bash commands or decides whether an operation is safe.
* **The FastMCP Server enforces strict, rule-based policies** (`rules/policies.yaml`) before any command touches the kernel.
* **All changes are independently validated** using active socket probes, kernel table inspection, and diagnostic monitoring tools (`ping`, `iperf3`).

### Tools & Technologies
* **MCP Frameworks:** FastMCP (Python implementation over JSON-RPC 2.0 stdio transport), Anthropic MCP SDK.
* **Network Tools:** `iptables` (firewall rules), `tc` (traffic control / bandwidth shaping), `ss` (socket enumeration), `sysctl` (kernel parameters).
* **Scripting & Languages:** Python 3.11, Bash.
* **Configuration Formats:** YAML (`rules/policies.yaml`), JSON (`results/checkpoint.json`).
* **Monitoring & Diagnostic Tools:** `ping` (ICMP reachability & latency/jitter), `iperf3` (bandwidth throughput).
* **Deployment:** Docker container with `NET_ADMIN` and `NET_RAW` Linux capabilities.

### Expected Outcomes
1. **Apply Network Configurations from User Commands:** Translates natural language into structured, safe tool execution.
2. **Validate Changes Through Monitoring Tools:** Independently verifies rule application and live socket state.
3. **Structured, Rule-Based Automation:** Protects critical infrastructure (ports 22, 53, 5000; interfaces eth0, lo) from accidental modification.

### Deliverables
* **Working Assistant:** Native desktop app (`pywebview`) and web interface (`python app.py --web`).
* **Rule Files:** Declarative security policies in `rules/policies.yaml`.
* **Deployment Scripts:** One-command Docker deployment (`docker compose up --build`) and Windows/Linux launch scripts.
* **Test Cases:** Full automated test suite in `tests/` (`pytest tests/ -v`).
* **Final Report:** Detailed report ([CS331_T018_Project_Report.md](CS331_T018_Project_Report.md)) explaining setup, use cases, and validation results.

---

## 🏗️ System Architecture

```
User (Natural Language)
        │ "block port 9999"  /  "throttle bandwidth on eth1"
        ▼
NetOpsBridge (assistant.py)
        │
        ├──────────────────────────────┐
        ▼                              ▼
LLM Client (Groq API)          MCP Client (stdio)
        │ Structured tool call         │
        └──────────────────────────────┤
                                       ▼
                         FastMCP Server (server.py)
                                       │
                                       ▼
                         Policy Validation (policies.yaml)
                         [Never blocks ports 22, 53, 5000]
                                       │
                                       ▼
                          Linux Kernel (iptables / tc)
                                       │
                                       ▼
                         Independent Verifier (verifier.py)
                         [Layer 1: Kernel table inspection]
                         [Layer 2: Active socket probe]
                         [Layer 3: ping / iperf3 diagnostics]
```

---

## 🚀 Quick Start Guide

### Running the Assistant Locally

1. **Activate Environment & Install Dependencies:**
   ```bash
   cd netops-mcp-assistant
   python -m venv .venv
   ```
   *Windows (PowerShell):*
   ```powershell
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
   *Linux / macOS:*
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Groq API in `.env`:**
   Ensure your `.env` contains:
   ```env
   LLM_PROVIDER=groq
   GROQ_API_KEY=your_groq_api_key_here
   ```

3. **Launch the Application:**
   * **Desktop App (Native GUI):**
     ```bash
     python app.py
     ```
     *(Or double-click `run_desktop.bat` on Windows)*
   * **Web Browser Mode:**
     ```bash
     python app.py --web
     ```
     Open `http://localhost:5000` in your browser.

---

### Running with Docker

Docker provides a containerized Linux environment with `iptables`, `tc`, and network tools pre-installed:

```bash
cd netops-mcp-assistant
docker compose up --build
```
Access the Web UI at **http://localhost:5000**.

---

## 🛠️ The 12 FastMCP Tools

| Category | Tool | Parameters | Purpose |
|:---|:---|:---|:---|
| **Firewall** | `configure_firewall` | `port`, `action`, `protocol` | Adds `iptables` ACCEPT, DROP, or REJECT rules. |
| | `list_firewall_rules` | `chain` | Formats and outputs active Linux `iptables` rules. |
| | `verify_firewall_rule` | `port`, `action`, `protocol` | Queries kernel filter tables to confirm rule presence. |
| | `validate_firewall_change`| `port`, `action` | Dual-layer active socket reachability probe. |
| **Traffic Control** | `set_bandwidth_limit` | `interface`, `rate`, `burst` | Applies token bucket filter (`tc qdisc tbf`) rate limit. |
| | `check_bandwidth` | `interface` | Queries active queue discipline on network interfaces. |
| **Diagnostics & Monitoring** | `run_diagnostics` | `target`, `test_type`, `count` | Runs ICMP `ping` or `iperf3` bandwidth tests. |
| | `check_listening_ports` | *none* | Discovers open sockets via `ss -tlnp`. |
| | `check_port_connectivity`| `host`, `port`, `timeout` | Active TCP 3-way handshake reachability test. |
| **Kernel Integration** | `apply_network_profile` | `profile_name` | Applies workload sysctl profile with pre-change checkpoint. |
| | `restore_network_defaults`| *none* | Reverts kernel parameters from saved checkpoint. |
| | `run_profile_benchmark`| `profile_name` | Pre/post empirical benchmarks with ping and iperf3. |

---

## 🔒 Security Guardrails & Policy Rules

- **Protected Administrative Ports:** Ports `22` (SSH), `53` (DNS), and `5000` (Management) can **never** be blocked.
- **Protected Network Interfaces:** `eth0` and `lo` are protected from bandwidth throttling.
- **Safe Subprocess Execution:** Commands are executed strictly through list-based argument arrays without `shell=True`, eliminating command injection.
- **Dual-Layer Validation:** Rather than trusting command exit codes, the verifier actively probes live sockets to verify firewall and routing behavior.

---

## 🧪 Automated Testing

Run the automated test suite from `netops-mcp-assistant/`:

```bash
pytest tests/ -v
```

All 26 tests validate policy boundaries, protected port handling, FastMCP tool registrations, LLM structured schema outputs, and verifier probes.

---

## 👥 Course & Team Information

- **Course:** CS331 — Computer Networks
- **Team ID:** T018