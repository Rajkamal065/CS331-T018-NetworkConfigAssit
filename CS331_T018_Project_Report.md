# CS331 — Computer Networks: Project Report

# NetOps MCP Assistant
## An AI-Powered Autonomous Linux Network Configuration & Diagnostic Assistant

**Course:** CS331 — Computer Networks  
**Team ID:** T018  

---

## 1. Project Overview & Problem Statement

### 1.1 Project Description
Network administration on Linux systems requires managing low-level kernel subsystems, packet filtering utilities (`iptables`), traffic control and queuing disciplines (`tc`), socket monitors (`ss`), and diagnostic utilities (`ping`, `iperf3`). Performing these tasks manually is error-prone, commands differ across tools, and manual interventions lack safety guardrails or independent validation.

**NetOps MCP Assistant** builds an intelligent assistant using the **Model Context Protocol (MCP)** that helps network administrators configure devices securely, safely, and efficiently. It interprets user commands in natural language and applies configurations—such as firewall filtering and bandwidth shaping—strictly governed by predefined, rule-based policies and network context.

### 1.2 Core Course Objectives & Expected Outcomes
In accordance with the CS331 project specifications:
1. **Apply Network Configurations from User Commands:** Translate natural-language administrative intent into structured, deterministic operations.
2. **Rule-Based Automation & Security Guardrails:** Enforce declarative policies (`rules/policies.yaml`) inside an authoritative server to prevent accidental self-denial-of-service or malicious changes (e.g., never dropping management ports like SSH or DNS).
3. **Validate Changes Through Monitoring Tools:** Independently verify every network state mutation using active socket probes, kernel table inspection, and monitoring utilities (`ping`, `iperf3`).
4. **Kernel-Level Integration Demonstration:** Demonstrate that high-level AI reasoning can safely drive low-level operating system network configurations (`sysctl`, `tc`, `iptables`) with automated checkpoint and rollback mechanisms.

### 1.3 Tools & Technologies
* **MCP Frameworks:** Anthropic Model Context Protocol specification, FastMCP (Python implementation over JSON-RPC 2.0 stdio).
* **Linux Network Stack & Tools:** `iptables` (packet filtering / firewall), `tc` (traffic control / token bucket filtering), `ss` (socket statistics), `sysctl` (kernel parameters).
* **Diagnostic & Monitoring Tools:** `ping` (ICMP latency and jitter), `iperf3` (TCP bandwidth and retransmission throughput).
* **Policy & Configuration Formats:** YAML / JSON (`rules/policies.yaml`, `results/checkpoint.json`).
* **Deployment & Runtime:** Docker container with `NET_ADMIN` and `NET_RAW` Linux capabilities, Python 3.11, pywebview desktop interface, and embedded web mode.

---

## 2. System Architecture & MCP Integration

The core architectural tenet of NetOps MCP Assistant is **strict separation of concerns**:
> **The LLM is strictly an intent interpreter, never a security authority.**

Because language models are probabilistic and prone to hallucination or prompt injection, the LLM is never allowed to directly execute commands or decide whether an action is safe. Instead, all operations must pass through an authoritative FastMCP server enforcing declarative security policies.

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                           User Interface Layer                                    │
│       • Desktop GUI (pywebview)  /  Browser Web Interface (HTTP API)              │
│       • Subsystem status indicators & real-time operation timeline                │
└────────────────────────────────────────┬──────────────────────────────────────────┘
                                         │ Natural language command
                                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                       NetOps Bridge (assistant.py)                                │
│       • Coordinates user request, LLM schema parsing, MCP execution,              │
│         and triggers the independent validation workflow                          │
└───────────────────┬───────────────────────────────────────────┬───────────────────┘
                    │ Intent query                              │
                    ▼                                           ▼
┌────────────────────────────────────────┐  ┌───────────────────────────────────────┐
│       LLM Client (llm_client.py)       │  │       MCP Client (mcp_client.py)       │
│  • Provider: Groq API (Low-latency LPU)│  │  • FastMCP stdio transport (JSON-RPC)  │
│  • Discovers tool schemas from server  │  │  • Asynchronous inter-process stream   │
│  • Returns structured tool arguments   │  └───────────────────┬───────────────────┘
└────────────────────────────────────────┘                      │
                                                                ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                       FastMCP Server Layer (server.py)                            │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                   Authoritative Policy Engine (policies.yaml)               │  │
│  │   • Invariant checking: Port 22 (SSH), 53 (DNS), 5000 protected from block  │  │
│  │   • Interface protection: eth0 & lo protected from bandwidth throttling     │  │
│  │   • Range & type validation on ports (1-65535) and rate values              │  │
│  └─────────────────────────────────────┬───────────────────────────────────────┘  │
│                                        │ Approved actions only                    │
│                                        ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                   Execution Layer (tools/net_ops.py)                        │  │
│  │   • iptables: ACCEPT, DROP, REJECT rules                                    │  │
│  │   • tc qdisc: Token bucket filter (tbf) bandwidth shaping                   │  │
│  │   • sysctl: Workload parameter tuning & automated checkpointing             │  │
│  │   • Execution strictly via array arguments (No shell=True)                  │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────┬──────────────────────────────────────────┘
                                         │
                                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│              Independent Validation & Monitoring Engine (verifier.py)             │
│  • Layer 1: Kernel Table Verification (confirms iptables/tc presence in kernel)   │
│  • Layer 2: Active Socket Reachability Probe (actual TCP handshake test)          │
│  • Layer 3: Diagnostic Monitoring (ping ICMP latency & iperf3 throughput delta)   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. FastMCP Registered Tools Catalogue

The assistant registers 12 authoritative tools with FastMCP, grouped into four functional categories:

### 3.1 Firewall Management (`iptables`)
1. **`configure_firewall`** (`port`, `action`, `protocol`): Safely inserts an `iptables` rule (ACCEPT, DROP, REJECT) for a specified TCP/UDP port after passing policy evaluation.
2. **`list_firewall_rules`** (`chain`): Reads and formats the active Linux kernel packet filter tables.
3. **`verify_firewall_rule`** (`port`, `action`, `protocol`): Queries kernel filter tables directly to confirm rule existence.
4. **`validate_firewall_change`** (`port`, `action`): Performs a dual-layer probe: audits kernel rules and actively tests TCP handshake reachability to prove enforcement.

### 3.2 Traffic Shaping & Bandwidth Control (`tc`)
5. **`set_bandwidth_limit`** (`interface`, `rate`, `burst`): Configures Linux traffic control using a Token Bucket Filter (`tc qdisc replace dev <interface> root tbf rate <rate> burst <burst> latency 50ms`).
6. **`check_bandwidth`** (`interface`): Queries the active queuing discipline (qdisc) attached to a network interface.

### 3.3 Network Diagnostics & Monitoring
7. **`run_diagnostics`** (`target`, `test_type`, `count`): Executes ICMP `ping` latency/jitter tests or `iperf3` bandwidth benchmarks.
8. **`check_listening_ports`** (*none*): Scans and enumerates active TCP/UDP listening sockets using `ss -tlnp`.
9. **`check_port_connectivity`** (`host`, `port`, `timeout`): Performs an active TCP 3-way handshake reachability probe against any host:port.

### 3.4 Kernel-Level System Integration & Empirical Tuning
10. **`apply_network_profile`** (`profile_name`): Demonstrates kernel-level `sysctl` integration by applying tuned parameter sets (e.g., Gaming, Streaming, Broadcasting) after taking an automated pre-change checkpoint.
11. **`restore_network_defaults`** (*none*): Restores original kernel parameters from the saved checkpoint (`/app/results/checkpoint.json`).
12. **`run_profile_benchmark`** (`profile_name`): Executes pre- and post-configuration tests with `ping` and `iperf3`, returning empirical metric deltas.

---

## 4. Policy Engine & Safety Boundaries (`rules/policies.yaml`)

A primary outcome of this project is providing **structured, rule-based automation** so administrators cannot inadvertently break host connectivity.

### 4.1 Protected Invariants
* **Protected Administrative Ports:** Ports `22` (SSH), `53` (DNS), and `5000` (Management Web UI) can **never** be blocked or dropped. If a user command requests *"block port 22"*, the policy engine intercepts the call and returns an explicit `POLICY_REJECTION`.
* **Protected Interfaces:** Critical network interfaces (`eth0` and `lo`) cannot have bandwidth restrictions applied that could isolate the host.
* **Safe Subprocess Execution:** Commands are executed strictly through list-based argument arrays (e.g., `["iptables", "-A", "INPUT", ...]`). `shell=True` is prohibited throughout the entire codebase, neutralizing command injection vulnerabilities.

---

## 5. Independent Validation & Monitoring Methodology

A critical requirement is that the assistant does not simply trust a command's return code (`exit 0`). It independently validates that the network state actually changed:

```
                      Command Executed
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│         Layer 1: Kernel Table Inspection                │
│    Inspects 'iptables -L -n -v' or 'tc qdisc show'      │
│    Verifies rule was written into the kernel table      │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│         Layer 2: Active Socket Probe                    │
│    Attempts a real TCP 3-way handshake to the port      │
│    - If action was DROP: socket times out -> PASS       │
│    - If action was ACCEPT: socket connects -> PASS      │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│         Layer 3: Diagnostic Monitoring                  │
│    Runs ICMP ping & iperf3 to verify link latency,      │
│    jitter, and throughput impacts                       │
└─────────────────────────────────────────────────────────┘
```

### 5.1 Validation Example: Firewall Block Verification
When the user requests *"block port 9999"*:
1. The FastMCP server inserts `iptables -A INPUT -p tcp --dport 9999 -j DROP`.
2. The independent verifier (`tools/verifier.py`) connects to `127.0.0.1:9999`.
3. The connection is dropped by the kernel and times out.
4. The verifier confirms both kernel rule presence and active socket timeout, returning a verified status badge to the user.

---

## 6. Kernel Integration & Empirical Demonstration

To demonstrate that the MCP assistant can coordinate low-level OS networking beyond packet filters, the system exposes kernel parameter tuning (`sysctl`) and measures empirical performance with `ping` and `iperf3`.

### 6.1 Automated State Checkpointing & Rollback
Before applying any kernel modification, the system reads all targeted `sysctl` keys and writes their initial values to `/app/results/checkpoint.json`. Calling `restore_network_defaults()` immediately restores the baseline, ensuring non-destructive experimentation.

### 6.2 Empirical Measurements from Linux Container

| Workload Scenario | Configuration Applied | Monitoring Tool | Metric Measured | Baseline (Before) | Tuned (After) | Result |
|:---|:---|:---|:---|:---|:---|:---|
| **Low-Latency (Gaming)** | `fq_codel` qdisc + BBR | `ping` (ICMP) | Jitter (`mdev`) | 2.21 ms | 1.40 ms | **36.6% Jitter Reduction** |
| **High-Throughput (Streaming)** | 16 MB `rmem_max` + window scaling | `iperf3 -R` | Receiver Throughput | 20.57 Gbps | 30.16 Gbps | **+46.6% Throughput** |
| **Paced Upload (Broadcasting)** | 16 MB `wmem_max` + BBR pacing | `iperf3` | Sender Throughput | 18.36 Gbps | 21.58 Gbps | **+17.5% Throughput** |

---

## 7. Deliverables & Demonstration

The project delivers a fully working, self-contained system:
1. **Working Assistant:** Native desktop GUI (`python app.py`) and browser-accessible web server (`python app.py --web`).
2. **Rule Files:** Declarative security policy specification in `netops-mcp-assistant/rules/policies.yaml`.
3. **Deployment Scripts:** Complete Docker container deployment bundling Python 3.11 and Linux networking tools (`iptables`, `tc`, `iperf3`), along with native Windows/Linux launch scripts (`run_desktop.bat`, `run_web.bat`).
4. **Automated Test Suite:** Comprehensive unit and integration tests (`pytest tests/ -v`) covering policy rejection, tool execution, and verifier probes.
5. **Standalone Verification Script:** Interactive test script (`python demo/validate_firewall.py`) demonstrating socket probing and rule enforcement.

---

## 8. Conclusion

**NetOps MCP Assistant** successfully fulfills all objectives set forth for the CS331 Computer Networks project:
* Translates conversational administrator intent into precise network configurations.
* Confines the LLM strictly to intent interpretation while keeping policy authority in FastMCP.
* Protects core infrastructure through deterministic, rule-based policies.
* Proves configuration changes using independent, multi-layer socket and diagnostic validation.
* Provides a modular, extensible blueprint for AI-assisted systems administration.
