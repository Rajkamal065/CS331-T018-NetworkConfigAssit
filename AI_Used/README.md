# CS331 Computer Networks — Comprehensive AI Usage & Prompt Log

- **Course:** CS331 — Computer Networks (2026–27 Sem 1)
- **Team ID:** T018
- **Project Title:** NetOps MCP Assistant: Safe Linux Network Automation
- **Student Team:** Sowpati Raj Kamal (23110319), Yalla Sai Teja (23110366), Pulakurthi Manohar (23110259), Guda Avinash Reddy (23110123), Jangam Sanjay (23110144), Gella Jaya Rama Krishna (23110115)

---

## 📌 Statement on AI Usage & Learning Progression

In accordance with course guidelines, this document provides the complete, transparent record of all AI interactions, prompts, and conceptual dialogues conducted across ChatGPT, Claude/Antigravity, and Cursor during the conception, development, debugging, and terminal verification of the NetOps MCP Assistant.

Our team used AI extensively as a **pair programmer, code generation engine, and interactive tutor**. We did not simply ask AI to "build the project and hand it over" — we engaged in extensive back-and-forth questioning to understand *why* each networking primitive behaves the way it does, *why* certain ports and interfaces must be protected, *how* the Linux kernel enforces traffic control, and *how* to independently verify changes at the packet and socket level.

---

# Part 1: Conceptualization & Architectural Prompts (ChatGPT / GPT-4o)

These prompts reflect our initial architectural design discussions, where we explored the separation of responsibilities between natural language intent, MCP protocol boundaries, and Linux network security.

### Prompt 1.1: Core Architecture & Separation of Responsibilities
> *"I have designed my NetOps assistant with a GUI, assistant.py as the orchestrator, an LLM for natural-language interpretation, an MCP client/server boundary, a policy layer, Linux networking tools, and an independent verifier. I am thinking of keeping the LLM limited to generating structured intent rather than allowing it to execute commands directly. Does this architecture make sense? Walk through the request flow and point out any weak boundaries or responsibilities I may have assigned incorrectly."*

### Prompt 1.2: Security Boundaries & Non-Authoritative LLM
> *"I am thinking of keeping the LLM responsible only for translating natural language into structured tool calls, while the FastMCP server handles policy validation and the network tools perform execution. I believe this makes the LLM non-authoritative. Does this separation make architectural sense, and what security problems does it prevent?"*

### Prompt 1.3: Rationale for Protected Ports (22, 53, 5000)
> *"I am considering protecting ports 22, 53, and 5000 from DROP/REJECT operations. My reasoning is that SSH maintains administrative access, DNS is an essential service, and 5000 is used by my own application. Is this a reasonable safety policy, and what failure scenarios does it protect against?"*

### Prompt 1.4: Orchestrator vs. MCP Client Responsibilities
> *"In my current implementation, assistant.py receives the structured tool intent from the LLM and then passes the tool name and arguments to mcp_client.py. The MCP client communicates with my FastMCP server. I am trying to verify that I understand the responsibility split correctly. Should the MCP client only invoke/discover tools while the server remains responsible for policy validation and execution? Trace one firewall request through these components and identify where each decision should happen."*

### Prompt 1.5: MCP Transport Protocols (Stdio vs. Network Sockets)
> *"I have implemented my MCP client and FastMCP server as separate components, with the client using stdio transport. I understand the high-level purpose of MCP, but I want to verify what actually travels between the two processes. Explain how the tool name, arguments, request, and response are represented, and distinguish the roles of MCP, JSON-RPC, and stdio in this implementation."*

### Prompt 1.6: Concrete JSON-RPC Protocol Inspection
> *"My MCP connection uses JSON-RPC over stdio. I understand that JSON-RPC defines structured requests and responses, but I want to understand exactly what that means in my implementation. Using configure_firewall(port=9999, protocol=tcp, action=DROP) as an example, show what the client is conceptually requesting and what the server returns."*

### Prompt 1.7: Stdio Pipes vs. TCP Sockets
> *"I am using stdio transport between my MCP client and FastMCP server rather than a TCP socket. I initially thought communication between two processes might require a network socket. Explain how stdin/stdout allow the two local processes to exchange MCP messages and contrast this with the TCP socket that my verifier uses for firewall testing."*

### Prompt 1.8: Understanding the Fundamentals of MCP
> *"I have implemented an MCP client and FastMCP server in my project, but I don't have a clear understanding of what MCP actually is. Explain MCP from the basics and then relate the concepts of client, server, tool, request, and response to my network assistant."*

---

# Part 2: Low-Level Linux Networking & Theory Prompts

These prompts were used to understand the underlying networking primitives (`iptables`, `tc`, `sysctl`, congestion control algorithms, and socket states) so we could correctly write and defend our tools.

### Prompt 2.1: Fundamentals of iptables & Netfilter
> *"I am using iptables in my project, but I don't properly understand how Linux firewalling works. Teach me what iptables is, what tables, chains, rules, matches, and targets mean, and then break down `iptables -A INPUT -p tcp --dport 9999 -j DROP` step by step."*

### Prompt 2.2: Linux Traffic Control (`tc`) & Token Bucket Filter
> *"I am using tc for bandwidth limiting, but I don't understand Linux Traffic Control. Start from the basics: what is tc, what is a qdisc, what is TBF, and what happens when I apply a 10 Mbps limit to eth1?"*

### Prompt 2.3: TCP Congestion Control (BBR vs. CUBIC)
> *"I am using BBR in some of my profiles, but I don't fully understand how BBR works. Explain it from the basics, what problem it solves, how it differs from traditional loss-based congestion control, and why it applies to TCP rather than being a generic UDP optimization."*

### Prompt 2.4: Video Streaming over TCP & Bufferbloat
> *"I don't fully understand what happens when a laptop receives a video stream over TCP. Walk me through the path from the remote server to the laptop and explain where receive buffers, congestion control, and queueing can affect the transfer."*

### Prompt 2.5: Dual-Layer Verification Mechanics
> *"I have implemented the firewall verifier, but I realize I don't fully understand how a TCP socket actually proves that a firewall DROP rule is working. Explain the TCP connection process from the moment the verifier calls connect(), and then relate each step to what my verifier observes."*

---

# Part 3: Implementation, Debugging & Refactoring Prompts

These prompts document our interactive coding sessions with the AI coding assistant, showing how we identified bugs, debugged runtime errors, and iteratively improved the codebase.

### Prompt 3.1: Context Window Pollution Bug
> *"I am seeing a bug where a new natural-language request sometimes results in the LLM selecting a tool or arguments similar to a previous request. I suspect conversation history is influencing tool selection. Help me reason through the likely cause and identify exactly where I should inspect the request construction."*
> **Resolution:** We limited `self.conversation_history` in `assistant.py` to the last 10 turns (5 user + 5 assistant) to prevent token context bloat and model drift.

### Prompt 3.2: Missing Interface for Bandwidth Testing
> *"I am trying to apply a bandwidth limit to eth1, but my current container only exposes lo and eth0. I need to understand why the test cannot work as intended and what kind of Docker/network setup would provide an appropriate non-protected interface for experimentation."*
> **Resolution:** We created a virtual link using `ip link add eth1 type dummy` and `ip link set eth1 up` to test bandwidth shaping without throttling the container's primary `eth0` network interface.

### Prompt 3.3: Docker Security & Linux Capabilities (`NET_ADMIN`, `NET_RAW`)
> *"Running iptables and tc in Docker required granting net_admin and net_raw capabilities to avoid permission denials without fully compromising container security. Explain why default containers block these commands and why giving cap_add NET_ADMIN and NET_RAW is better than using full privileged mode."*
> **Learning Outcome:** Understood the Principle of Least Privilege (PoLP): `CAP_NET_ADMIN` restricts root power solely to the network namespace without exposing host hardware or filesystems.

### Prompt 3.4: The "Block then Accept" Rule Shadowing Bug
> *"How does the rollback work and also there's a usecase right: first block and then accept overrides the block rule, which is not how it works in raw networking right? Tell me that."*
> **Learning Outcome:** Discovered that in raw `iptables`, appending an `ACCEPT` rule after a `DROP` rule leaves the port blocked due to top-to-bottom first-match evaluation. We wrote custom conflict resolution in `NetworkOps.apply_iptables_rule` to automatically purge opposing rules before appending new ones.

### Prompt 3.5: FastMCP Stdio Transport Disconnect Debugging
> *"What why is the MCP disconnected? It says 'Cannot reach FastMCP server process via stdio transport'."*
> **Debugging Session:** 
> - Inspected Docker container logs and found: `FileNotFoundError: /app/rules/policies.yaml`.
> - Discovered that restructuring the repo from `netops-mcp-assistant/` to `code/` left the Docker volume mount pointing to a stale directory.
> - Removed the old container, rebuilt from `code/`, and restored the volume binding, bringing FastMCP back online with 12 registered tools.

### Prompt 3.6: Kernel Protocol Optimization vs. iptables Distinction
> *"Does it happening I mean when I optimize my gaming is that being added to the iptable rules? I didn't check that."*
> **Learning Outcome:** Clarified that `iptables` is strictly a packet-filtering firewall, whereas gaming optimization operates at the transport layer by modifying Linux kernel `/proc/sys/net/` parameters (like BBR, `fq_codel`, and socket buffer sizes) using `sysctl`.

---

# Part 4: Hands-on Terminal Verification & Experimentation Prompts

These prompts document our terminal validation process, where we verified that the AI-assisted code actually produced live, measurable effects in the Linux kernel.

### Prompt 4.1: Checking Bandwidth Throttling in the Kernel
> *"tc qdisc show dev eth1 — I want to check that the bandwidth limit is being done so I want to check that with command in terminal."*
> **Observed Output:**
> ```text
> qdisc tbf 8001: root refcnt 2 rate 10Mbit burst 15Kb lat 20ms
> qdisc tbf 8001: root refcnt 2 rate 50Mbit burst 75Kb lat 20ms
> ```
> Confirmed that token refill rate dynamically adjusted from 10 Mbps to 50 Mbps and burst scaled from 15 KB to 75 KB.

### Prompt 4.2: Demonstrating TCP Congestion Control Switching
> *"I think showing the cubic to bbr is enough for testing right? Tell me how to show it."*
> **Observed Output:**
> ```bash
> # Baseline:
> sysctl net.ipv4.tcp_congestion_control
> # Output: net.ipv4.tcp_congestion_control = cubic
> 
> # After applying Gaming Profile via UI:
> sysctl net.ipv4.tcp_congestion_control
> # Output: net.ipv4.tcp_congestion_control = bbr
> ```

### Prompt 4.3: Understanding iptables Output & Wildcard IP Notation
> *"1  2  120 DROP tcp -- * * 0.0.0.0/0 0.0.0.0/0 tcp dpt:9999 — What command I need to do in terminal to check that it blocked? Why the hell is that source dest 0.0.0.0/0?"*
> **Concepts Mastered:**
> - `0.0.0.0/0` is the CIDR wildcard matching all $2^{32}$ IPv4 addresses (matching 0 prefix bits), meaning "any IP in the world to any IP on this host".
> - Verified packet dropping by executing:
>   ```bash
>   curl --connect-timeout 2 http://127.0.0.1:9999
>   # Output: curl: (28) Connection timed out after 2000 milliseconds
>   ```
> - Observed the kernel packet counter in `iptables -L -n -v` increment from 2 to 4 packets, confirming active kernel drop enforcement.

### Prompt 4.4: State Persistence & Docker Ephemeral Networking
> *"After closing the server the rules will get deleted right, or after Docker closes or what exactly?"*
> **Concepts Mastered:**
> - Closing the browser leaves rules active in the container's kernel memory.
> - Stopping the container (`docker compose down`) completely destroys the virtual network namespace and RAM-based rules, resetting the system cleanly to default state without affecting the host machine.

---

# Part 5: UI/UX Refinement & Presentation Prompts

### Prompt 5.1: Conversational UI Simplification
> *"I have already built the basic UI for my NetOps MCP Assistant using HTML, CSS, JavaScript, and pywebview. The functionality works, but the interface currently feels more like a developer tool than a polished student project. Review the current layout conceptually and suggest which visual elements I should simplify, enlarge, or reorganize without changing the underlying functionality."*

### Prompt 5.2: Natural Assistant Dialogue with Expandable Telemetry
> *"My current interface exposes too many technical implementation details such as 'LLM', 'MCP client', and internal subsystem names. I want the user experience to feel like a normal assistant conversation while still showing useful verification evidence. Suggest how I can present the same information in a more natural conversational UI."*

### Prompt 5.3: Collapsible Step-by-Step Progress Tracking
> *"I am considering showing a compact message such as 'Processing — 5 steps completed' after an operation finishes, with the individual stages hidden until the user expands it. Evaluate whether this is a good UX pattern for my project and suggest what information should remain visible versus collapsible."*

### Prompt 5.4: Conditional Real Terminal Evidence Display
> *"I want the UI to show terminal evidence only when an actual backend command was executed. I do not want to generate fake command output just to make the interface look technical. Suggest a clean conditional design for displaying real command evidence and explain what should be shown when an operation is rejected by policy and no command was executed."*

---

## 📊 Summary of AI Integration Metrics

| Metric | Detail |
| :--- | :--- |
| **Primary Tools Used** | ChatGPT (GPT-4o), Claude 3.5 Sonnet / Antigravity, GitHub Copilot, Groq LPUs |
| **Development Phases Augmented** | Architecture Design, FastMCP Tool Scaffolding, Kernel Security Analysis, Docker Packaging, Debugging & Verification |
| **Total Automated Tests Written** | 34 automated unit and integration tests (`100% passing`) |
| **Terminal Verification Proofs** | Real `iptables -L -n -v` packet drops, `tc qdisc show dev eth1` TBF rate changes, `sysctl` CUBIC $\rightarrow$ BBR switches |
| **Code Authorship Model** | AI-Assisted Pair Programming with student-directed architecture, security policies, and manual terminal validation |

*All team members actively participated in framing queries, analyzing AI outputs, cross-checking Linux man pages, and conducting live terminal verification.*
