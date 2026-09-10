# CS331 — Computer Networks (Midsem Project Report)
# Team: T018 | Project: NetOps MCP Assistant
# An AI-Powered Autonomous Linux Network Configuration Assistant

---

## Abstract

Network configuration on Linux systems requires expertise in low-level kernel parameters (`sysctl`), traffic shaping tools (`tc`, `iptables`), and diagnostic utilities (`ss`, `ping`, `iperf3`). Manual tuning is error-prone, non-reproducible, and inaccessible to non-specialist users. This project presents **NetOps MCP Assistant**, a conversational AI agent that exposes Linux networking operations as structured, policy-validated Model Context Protocol (MCP) tools. Users express high-level intent ("optimize for gaming") and the system autonomously selects, applies, and benchmarks the appropriate kernel-level configuration, returning an empirical before/after parameter comparison and performance evaluation with automated checkpoint and rollback safety.

---

## 1. Introduction

### 1.1 Problem Statement

Modern operating systems ship with conservative, general-purpose TCP/IP defaults that are not optimal for any specific workload:

- **Gaming** requires sub-10 ms jitter, low bufferbloat, and fast socket teardown.
- **Video streaming** requires a large TCP receive window ($rwnd$) to sustain CDN download throughput and eliminate stalling between video segments.
- **Live broadcasting** (OBS, Twitch, Zoom upload) requires stable upload pacing to prevent dropped video frames during scene transitions and keyframe bursts.

Manually tuning `sysctl` for each workload requires reading kernel documentation and understanding the interaction between TCP congestion algorithms, queue disciplines, and buffer autotuning. Furthermore, manual kernel parameter modifications risk misconfiguration with no automated rollback mechanism.

### 1.2 Solution Overview

NetOps MCP Assistant wraps these operations in an AI-driven, policy-checked architecture:

```
User (Natural Language)
       │ "optimize for gaming" / "benchmark my gaming"
       ▼
  LLM Agent (Groq / Llama 3.1 & GPT-OSS)
       │ tool_call: apply_network_profile("gaming")
       ▼
  Automatic Checkpoint Saved (/app/results/checkpoint.json)
       │
       ▼
  MCP Tool Layer (Python / FastMCP)
       │ sysctl -w net.ipv4.tcp_congestion_control=bbr ...
       ▼
  Linux Kernel (Docker Container / Host)
       │
       ▼
  Before vs After Parameters Table & Empirical Benchmark
       │
       ▼
  User Response + Reversible via restore_network_defaults()
```

---

## 2. Theoretical Background

### 2.1 Model Context Protocol (MCP)

MCP (Anthropic, 2024) is a JSON-RPC 2.0 over stdio specification that standardises how AI assistants call external tools. Each tool is declared with a name, description, and JSON Schema for its parameters. The LLM selects and invokes tools autonomously based on user intent, then incorporates tool output into its response. This project uses **FastMCP** (Python) as the server with stdio communication.

### 2.2 TCP Congestion Control: CUBIC vs BBR

TCP congestion control algorithms govern how fast a sender injects packets into the network:

| Algorithm | Year | Strategy | Best For |
|:---|:---|:---|:---|
| CUBIC | 2008 | Loss-based, cubic window growth | General default |
| BBR | 2016 | Model-based (bandwidth + RTT) | High BDP paths, loss-prone WiFi, gaming & streaming |

**BBR (Bottleneck Bandwidth and RTT)** is a state-machine that continuously estimates the true bottleneck bandwidth using a probing cycle, rather than reacting to packet loss events. This avoids the aggressive 30–50% window reduction that CUBIC applies on random packet loss events on WiFi links.

### 2.3 Queue Disciplines (qdisc) & Bufferbloat

The Linux traffic control subsystem (`tc`) attaches a queue discipline to each network interface, determining packet scheduling:

| qdisc | Description | Use Case |
|:---|:---|:---|
| `pfifo_fast` | Default FIFO with 3 priority bands | General (no specific latency optimisation) |
| `fq` | Per-flow Fair Queuing with pacing | Optimal with BBR for throughput |
| `fq_codel` | Fair Queue + Controlled Delay | Bufferbloat elimination (gaming) |

**Bufferbloat** occurs when a router or switch's buffer fills with bulk-download packets, causing latency to spike from ~15 ms to >200 ms. `fq_codel` solves this by maintaining a separate sub-queue per flow and actively dropping or marking packets that have waited longer than a target delay (5 ms default), keeping queue latency bounded.

### 2.4 TCP Receive Window and Streaming

The TCP receive window ($rwnd$) is the maximum amount of unacknowledged data the receiver allows the sender to inject. The maximum throughput achievable by a single TCP connection is bounded by:

$$\text{Throughput}_{\max} = \frac{rwnd}{\text{RTT}}$$

With default Linux settings (`rmem_max = 212992` bytes ≈ 208 KB) on a 40 ms RTT path:

$$\frac{208{,}000 \text{ B}}{0.040 \text{ s}} \approx 41 \text{ Mbps}$$

Enabling TCP Window Scaling (RFC 1323) and increasing `rmem_max` to 16 MB raises this limit to:

$$\frac{16{,}777{,}216 \text{ B}}{0.040 \text{ s}} \approx 3.3 \text{ Gbps}$$

---

## 3. System Architecture & MCP Tool Catalogue

### 3.1 Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   NetOps MCP Assistant                          │
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │  Web UI     │    │  LLM Client  │    │  MCP Server      │   │
│  │  (HTML/JS + │◄──►│  (Groq API / │◄──►│  (FastMCP /      │   │
│  │   CSS)      │    │   Llama 3.1) │    │   Python)        │   │
│  └─────────────┘    └──────────────┘    └──────────────────┘   │
│                                                  │              │
│                         ┌────────────────────────┤              │
│                         ▼                        ▼              │
│              ┌─────────────────┐    ┌─────────────────────┐    │
│              │  tools/         │    │  Linux Kernel       │    │
│              │  net_ops.py     │    │  (Docker Container) │    │
│              │  profiles.py    │    │  sysctl, iptables,  │    │
│              │  benchmark.py   │    │  tc, ss, ping       │    │
│              │  verifier.py    │    └─────────────────────┘    │
│              └─────────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Tool Catalogue (12 Tools)

| # | Tool | Description |
|:---|:---|:---|
| 1 | `configure_firewall` | Apply `iptables` ACCEPT/DROP/REJECT rules |
| 2 | `set_bandwidth_limit` | Apply `tc qdisc tbf` bandwidth throttle |
| 3 | `check_bandwidth` | Query current tc qdisc state |
| 4 | `run_diagnostics` | Ping or iperf3 connectivity test |
| 5 | `list_firewall_rules` | Show active iptables rules |
| 6 | `check_listening_ports` | Enumerate `ss -tlnp` listening sockets |
| 7 | `check_port_connectivity` | TCP reachability probe |
| 8 | `verify_firewall_rule` | Confirm iptables rule is in kernel table |
| 9 | `apply_network_profile` | Apply a named sysctl workload profile (auto-saves checkpoint) |
| 10 | `run_profile_benchmark` | Before/after empirical benchmark + parameter comparison |
| 11 | `restore_network_defaults` | Rollback to saved checkpoint or standard Linux kernel defaults |
| 12 | `validate_firewall_change` | Dual-layer independent verification probe |

---

## 4. Network Optimization Profiles & Parameter Tuning

### 4.1 Gaming Profile (Low Latency & Anti-Bufferbloat)

**Goal:** Minimise latency (ping) and jitter, eliminate bufferbloat.

| Parameter | Baseline (Before) | Tuned (After) | Optimization Impact |
|:---|:---|:---|:---|
| `net.ipv4.tcp_congestion_control` | `cubic` | `bbr` | Model-based congestion control; stable ping under packet loss |
| `net.core.default_qdisc` | `pfifo_fast` | `fq_codel` | Fair queuing, bufferbloat killer |
| `net.ipv4.tcp_low_latency` | `0` | `1` | Disables packet batching; immediate NIC flush |
| `net.core.rmem_max` | 208 KB | 4 MB | Small queues drain rapidly without adding queue delay |
| `net.core.wmem_max` | 208 KB | 4 MB | Small send buffers prevent queue buildup |
| `net.ipv4.tcp_fin_timeout` | 60 s | 15 s | Fast socket reuse for rapid reconnects |
| `net.ipv4.tcp_fastopen` | `1` | `3` | Skip 3-way handshake on reconnect to game servers |

### 4.2 Streaming Profile (High Sustained Download Throughput)

**Goal:** Maximise download throughput and eliminate stalling between video segments.

| Parameter | Baseline (Before) | Tuned (After) | Optimization Impact |
|:---|:---|:---|:---|
| `net.ipv4.tcp_congestion_control` | `cubic` | `cubic` | Receiver-side default: CDN sender governs transmission cwnd |
| `net.core.default_qdisc` | `pfifo_fast` | `fq` | Smooth ACK pacing |
| `net.core.rmem_max` | 208 KB | 16 MB | Allows CDN servers to advertise large $rwnd$ |
| `net.ipv4.tcp_rmem` | 4K / 87K / 6M | 4K / 87K / 16M | Autotuning receive window bounds for 4K video streams |
| `net.ipv4.tcp_slow_start_after_idle` | `1` | `0` | Disables slow-start reset between chunk downloads |
| `net.ipv4.tcp_window_scaling` | `1` | `1` | RFC 1323 — unlocks $rwnd$ > 64 KB |
| `net.ipv4.tcp_timestamps` | `1` | `1` | Accurate RTT measurement for ACK feedback |

### 4.3 Broadcasting Profile (OBS / Live Stream Upload)

**Goal:** Stable upload throughput; prevent dropped frames during keyframe bursts.

| Parameter | Baseline (Before) | Tuned (After) | Optimization Impact |
|:---|:---|:---|:---|
| `net.ipv4.tcp_congestion_control` | `cubic` | `bbr` | Host controls upload congestion window ($cwnd$) |
| `net.core.default_qdisc` | `pfifo_fast` | `fq` | Packet pacing prevents burst-then-starve upload cycles |
| `net.core.wmem_max` | 208 KB | 16 MB | Large send buffer holds video frames during bursts |
| `net.ipv4.tcp_wmem` | 4K / 16K / 4M | 4K / 65K / 16M | High-bitrate send autotuning |
| `net.ipv4.tcp_slow_start_after_idle` | `1` | `0` | Eliminates bitrate drops between keyframe bursts |
| `net.ipv4.ip_local_port_range` | 32768–60999 | 1024–65535 | Expands local ports for concurrent stream + game + Discord |

---

## 5. Fallback & Safety Architecture

To satisfy safety requirements for production and academic evaluation:

1. **Automatic Pre-Change Checkpoint:** Before applying any kernel sysctl profile, the system reads all keys touched by any profile and writes them to `/app/results/checkpoint.json`.
2. **Instant Rollback Tool:** Invoking `restore_network_defaults()` immediately reads the checkpoint and applies the original values. If no checkpoint exists, it restores hardcoded Linux kernel defaults (`cubic`, `pfifo_fast`, 208 KB buffers).
3. **Non-Destructive Execution:** The checkpoint file is automatically cleaned up upon successful restoration.

---

## 6. Empirical Benchmark Results (Before vs After)

To satisfy rigorous engineering evaluation criteria, the system distinguishes between two independent classes of evidence:
1. **Configuration Evidence:** Verifying that the MCP tool actually mutated the Linux kernel's live networking subsystem (verified through `sysctl` read-backs).
2. **Performance Evidence:** Measuring real network workload metrics before and after profile application using standard Linux diagnostic engines (`ping` and `iperf3`).

No manufactured percentages or decorative claims are used; every number represents genuine, repeatable measurements.

### 6.1 Workload Matrix

| Profile | Workload Engine | Direction | Primary Metrics Measured |
| :--- | :--- | :--- | :--- |
| **Gaming** | ICMP Ping + Socket Connect (`8.8.8.8:53`) | Bidirectional | Latency (avg/min/max), Jitter (`mdev`), Packet Loss, TCP 3-Way Handshake Time |
| **Streaming** | `iperf3 -c 127.0.0.1 -R -t 2` | Server $\rightarrow$ Client (Receiver) | Receive Throughput (Mbps), Retransmissions, Transferred Data (MB) |
| **Broadcasting** | `iperf3 -c 127.0.0.1 -t 2` | Client $\rightarrow$ Server (Sender) | Transmit Throughput (Mbps), Retransmissions, Transferred Data (MB) |

---

### 6.2 Empirical Results Captured from Live Container Runs

#### 1. Gaming Profile (Low-Latency Workload)
```
==============================================================
  MEASURED BENCHMARK — PROFILE: GAMING
==============================================================

  1. PERFORMANCE EVIDENCE (MEASURED WORKLOAD)
--------------------------------------------------------------
  Average Ping Latency             Before: 18.24 ms      After: 17.30 ms      ✓ Stable (< 2.5 ms)
  Ping Jitter (mdev)               Before: 2.21 ms       After: 1.40 ms       ✓ Stable (< 2.5 ms)
  Packet Loss                      Before: 0.0 %         After: 0.0 %         ✓ 0% Loss
  TCP Handshake Time               Before: 18.92 ms      After: 19.82 ms      ✓ Stable (< 2.5 ms)

  2. CONFIGURATION EVIDENCE (LINUX KERNEL SYSCTL)
--------------------------------------------------------------
  ✓ tcp_fastopen                   1                     → 3
  ✓ tcp_fin_timeout                60                    → 15
==============================================================
```

#### 2. Streaming Profile (Video Playback / Receiver Workload)
```
==============================================================
  MEASURED BENCHMARK — PROFILE: STREAMING
==============================================================

  1. PERFORMANCE EVIDENCE (MEASURED WORKLOAD)
--------------------------------------------------------------
  TCP Throughput (Receiver)        Before: 20575.6 Mbps  After: 30164.7 Mbps  ▲ +46.6% higher
  TCP Retransmissions              Before: 0 pkts        After: 0 pkts        ✓ 0 delta
  Data Transferred                 Before: 4908.5 MB     After: 7195.8 MB
  Average Ping Latency             Before: 20.59 ms      After: 18.19 ms      ✓ Stable (< 2.5 ms)
  Packet Loss                      Before: 0.0 %         After: 0.0 %         ✓ 0% Loss

  2. CONFIGURATION EVIDENCE (LINUX KERNEL SYSCTL)
--------------------------------------------------------------
  ✓ tcp_wmem                       4096 16384 4194304    → 4096 65536 16777216
  ✓ tcp_rmem                       4096 131072 6291456   → 4096 87380 16777216
  ✓ tcp_slow_start_after_idle      1                     → 0
==============================================================
```

#### 3. Broadcasting Profile (OBS / Upload Sender Workload)
```
==============================================================
  MEASURED BENCHMARK — PROFILE: BROADCASTING
==============================================================

  1. PERFORMANCE EVIDENCE (MEASURED WORKLOAD)
--------------------------------------------------------------
  TCP Throughput (Sender)          Before: 18364.3 Mbps  After: 21585.9 Mbps  ▲ +17.5% higher
  Data Transferred                 Before: 4396.0 MB     After: 5152.5 MB
  Average Ping Latency             Before: 17.88 ms      After: 17.75 ms      ✓ Stable (< 2.5 ms)
  Ping Jitter (mdev)               Before: 0.90 ms       After: 1.07 ms       ✓ Stable (< 2.5 ms)
  Packet Loss                      Before: 0.0 %         After: 0.0 %         ✓ 0% Loss

  2. CONFIGURATION EVIDENCE (LINUX KERNEL SYSCTL)
--------------------------------------------------------------
  ✓ tcp_congestion_control         cubic                 → bbr
  ✓ tcp_rmem                       4096 87380 16777216   → 4096 87380 4194304
  ✓ ip_local_port_range            32768 60999           → 1024 65535
==============================================================
```

---

## 7. Conclusion

NetOps MCP Assistant proves that complex operating system network optimization can be achieved autonomously and safely through Model Context Protocol agents. The system provides clear before/after parameter reporting, empirical benchmark verification, and full safety rollback, delivering an accessible network operations tool suitable for both student and enterprise environments.
