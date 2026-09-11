# NetOps MCP Assistant — Demo Guide

This demo demonstrates the full end-to-end architecture:
```
User Query (Natural Language)
      ↓
Desktop UI (pywebview)
      ↓
Python Bridge (NetOpsBridge)
      ↓
LLM Client (Claude / Groq / OpenRouter / Ollama)
      ↓
FastMCP Client (stdio transport)
      ↓
FastMCP Server (server.py)
      ↓
Authoritative Security Policy Engine (policies.yaml)
      ↓
Network Operations (iptables / tc / ss)
      ↓
Independent Verification (Dual-layer: kernel table + TCP socket probe)
```

---

## 1. Quick Test: Run the Automated Validation Suite

To verify all architectural invariants without starting background services:
```bash
python demo/validate_firewall.py
```

This automated test executes:
1. **Baseline reachability probe** on port 9999
2. **Protected Port Lockout Prevention**: Attempts to block SSH port 22 &rarr; Authoritatively rejected by FastMCP policy layer.
3. **Arbitrary Port Configuration**: Blocks port 9999 &rarr; Permitted by policy and applied via iptables.
4. **Independent Dual-Layer Verification**: Inspects kernel tables and probes socket state.
5. **Port Restoration**: Allows port 9999 &rarr; Verified restored.

---

## 2. Interactive Live Service Demo

### Step 1: Start the Demo TCP Service on Port 9999
```bash
python demo/start_demo.py --port 9999
```
This starts an echo server listening on `0.0.0.0:9999`.

### Step 2: Launch the Desktop Assistant
In another terminal:
```bash
python app.py
```

### Step 3: Issue Natural Language Commands in the Desktop UI
Try typing:
- `"Check listening ports"` &rarr; Lists open sockets including 9999.
- `"Block port 22"` &rarr; **Authoritative Policy Rejection**: Shows why port 22 is protected from lockouts.
- `"Block port 9999 TCP with DROP"` &rarr; Rule is generated, validated, applied, and verified.
- `"Test reachability to port 9999 on 127.0.0.1"` &rarr; Independent socket probe reports connection timed out / blocked.
- `"Allow port 9999 TCP"` &rarr; Allows traffic again.

### Step 4: Clean up
```bash
python demo/stop_demo.py
```
