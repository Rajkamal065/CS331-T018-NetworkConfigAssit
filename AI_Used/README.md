# AI Usage Document
**Course:** CS331 — Computer Networks  
**Team ID:** T018  
**Project:** NetOps MCP Assistant

This document outlines how Artificial Intelligence was integrated into the development workflow of the NetOps MCP Assistant. Rather than relying on AI to blindly write code, our team used AI as a pair-programming partner, architectural sounding board, and diagnostic assistant to accelerate development while maintaining strict control over the system's security and logic.

---

## 1. TOOLS: AI Tools Utilized

The following AI tools were employed during the project lifecycle:

* **ChatGPT (GPT-4o)**: Used primarily for high-level architectural brainstorming, understanding the nuances of the Model Context Protocol (MCP), and generating complex Mermaid sequence diagrams.
* **Claude 3.5 Sonnet / Cursor**: Used for in-depth code generation, specifically for the Python networking submodules (`tc`, `iptables`) and generating the automated `pytest` suite.
* **GitHub Copilot**: Used within the IDE for inline code completion, rapid boilerplate generation, and writing repetitive docstrings.
* **Groq API (Llama 3 / OSS Models)**: While this is the AI engine integrated *into* the final product for intent interpretation, we also used it during development to test prompt boundaries and structured JSON outputs.

---

## 2. PROMPTS: Examples of Prompts Given

To guide the AI effectively, we used highly specific, context-rich prompts. Here are examples of key prompts used across different components:

**Architecture & Security:**
> *"Design a Python architecture using FastMCP to manage Linux network configurations (`iptables` and `tc`). The LLM should only generate structured tool calls, and a separate policy engine must intercept the calls to ensure ports 22, 53, and 5000 are never blocked. How should we structure this to guarantee zero command injection?"*

**Core Networking Implementation:**
> *"Write a Python subprocess wrapper to execute `tc qdisc` commands for bandwidth throttling on a specific interface. It must use array-based argument passing without `shell=True`. Include error handling for missing network interfaces."*

**Independent Verification Engine:**
> *"I need a dual-layer verification script in Python. Layer 1 should check the kernel tables to see if an iptables rule exists. Layer 2 should actively probe the socket (TCP handshake) to confirm if the port is actually reachable or blocked. Return a unified boolean result."*

**Frontend & UI Development:**
> *"Create a responsive, modern web interface using Vanilla HTML, CSS, and JS. Use a dark 'slate' theme with glassmorphism effects. It needs to communicate with a Flask backend on port 5000 and display live subsystem health cards for the LLM, MCP Server, and Kernel."*

**Testing & QA:**
> *"Generate a `pytest` suite for a policy engine `policies.yaml`. Write test cases that assert exceptions are raised when a tool tries to throttle the `eth0` interface or block port 22."*

---

## 3. THOUGHT PROCESS: Integration into the Workflow

The integration of AI was heavily structured to prevent hallucinated logic from compromising the system. Our thought process followed a **"Generate, Inspect, Refine"** loop:

1. **Conceptualization & Research:** We started by asking ChatGPT to explain the official Model Context Protocol (MCP) specification and how it differs from standard REST APIs. This informed our decision to use the `FastMCP` library.
2. **Component Isolation:** Recognizing that AI models can write insecure bash scripts, we deliberately used AI to write *declarative policy engines* instead of raw bash execution. We asked the AI to design the system so that the LLM only acts as an "intent interpreter", while deterministic Python code handles the execution.
3. **Iterative Refinement:** When the AI generated network configuration code (e.g., `sysctl` parameter tuning), we did not blindly execute it. We manually cross-referenced the suggested `tcp_rmem` and `fq_codel` settings with Linux networking documentation, then asked the AI to refine the script to include pre-change checkpointing (`checkpoint.json`).
4. **Debugging:** When we encountered issues (e.g., `pywebview` cross-origin errors or `iptables` privilege escalation issues in Docker), we pasted the stack traces into Claude/ChatGPT to rapidly identify the missing capabilities (like `NET_ADMIN` and `NET_RAW`) required in our `compose.yaml`.

---

## 4. STEP-BY-STEP: AI Contribution at Each Stage

### Stage 1: Planning and Architecture
* **Contribution:** AI helped structure the initial directory layout and conceptualize the strict boundary between the Orchestrator (`assistant.py`) and the Execution layer (`server.py`). 
* **Result:** The system design detailed in `ARCHITECTURE.md` (including the Mermaid sequence diagrams) was heavily accelerated by AI brainstorming sessions.

### Stage 2: Core Development & Tool Building
* **Contribution:** AI was used to draft the 12 specific FastMCP tools. For instance, generating the boilerplate JSON-RPC schemas required for the tools to register correctly with the MCP client.
* **Result:** Rapid implementation of `net_ops.py`, `profiles.py`, and `benchmark.py`. The AI provided the specific syntax for `ss -tlnp` and token bucket filters (`tbf`) which saved hours of manual syntax lookup.

### Stage 3: Security & Verification
* **Contribution:** We prompted the AI to act as a "Red Team" attacker trying to break the system. Based on its feedback, we used AI to write the strict regex sanitization in the policy engine and the independent dual-layer socket verifier (`verifier.py`).
* **Result:** A robust security posture where ports 22, 53, and 5000 are hardcoded as protected, and command execution is strictly sanitized.

### Stage 4: UI Development
* **Contribution:** AI generated the foundational CSS and JavaScript for the `index.html` frontend, specifically helping to implement the real-time visual cards and the logic for the `pywebview` desktop window wrapping.
* **Result:** A clean, professional user interface deployed seamlessly across both Desktop and Web modes.

### Stage 5: Testing and Documentation
* **Contribution:** We provided the AI with our final Python classes and asked it to generate corresponding unit tests using `pytest`. We also used AI to format our final markdown reports (`README.md`, `CS331_T018_Project_Report.md`) for clarity and consistency.
* **Result:** 34 automated tests passing out-of-the-box, ensuring policy boundaries hold, alongside comprehensive, professional documentation.
