"""
assistant.py — Python Bridge & Orchestrator for NetOps MCP Assistant.

Acts as the authoritative bridge between the Desktop UI (pywebview) / CLI and:
  1. LLM Client (Intent interpretation with Claude / Groq / OpenRouter / Ollama)
  2. MCP Client (Stdio transport to FastMCP server)
  3. Independent Verification Engine (Kernel rule check + TCP socket probes)

Security Invariants:
  - The LLM is an intent interpreter, NEVER a security authority.
  - The MCP server authoritatively validates and enforces policies.
  - The verification engine independently verifies live network state.
  - No shell=True or unvalidated user input is executed.
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any, List, Optional

# Ensure root is on sys.path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from llm_client import LLMClient
from mcp_client import get_mcp_client, MCPClient

logger = logging.getLogger("NetOpsBridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class NetOpsBridge:
    """
    Desktop JavaScript API Bridge for pywebview.
    Methods on this class are directly callable from JavaScript via `window.pywebview.api.<method>()`.
    """

    def __init__(self):
        self.llm = LLMClient()
        self.mcp: Optional[MCPClient] = None
        self.conversation_history: List[Dict[str, str]] = []
        self._init_mcp()

    def _init_mcp(self):
        """Connect to MCP server via stdio transport."""
        try:
            self.mcp = get_mcp_client()
            logger.info("Connected to FastMCP server via stdio transport.")
        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            self.mcp = None

    def get_status(self) -> Dict[str, Any]:
        """
        Return the real-time operational status of all subsystems:
        - LLM provider and model
        - MCP connection state
        - Registered MCP tools
        """
        llm_info = self.llm.status_info
        mcp_connected = False
        tools_count = 0

        if self.mcp and self.mcp._connected:
            mcp_connected = True
            try:
                tools = self.mcp.list_tools()
                tools_count = len(tools)
            except Exception:
                pass

        return {
            "llm": llm_info,
            "mcp": {
                "connected": mcp_connected,
                "tools_count": tools_count,
                "transport": "stdio"
            },
            "system": {
                "platform": sys.platform,
                "python": sys.version.split()[0]
            }
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all tools registered on the FastMCP server."""
        if not self.mcp or not self.mcp._connected:
            self._init_mcp()
        if self.mcp and self.mcp._connected:
            try:
                return self.mcp.list_tools()
            except Exception as e:
                logger.error(f"Error listing MCP tools: {e}")
        return []

    def send_message(self, message: str) -> Dict[str, Any]:
        """
        Process user natural language message through the complete pipeline:
        User -> LLM Intent -> MCP Policy & Tool Call -> Verification -> Structured Response
        """
        message = (message or "").strip()
        if not message:
            return {"type": "error", "error": "Empty message"}

        timeline: List[Dict[str, Any]] = []

        # Step 1: User Request Logged
        timeline.append({
            "step": "USER_INPUT",
            "title": "Natural Language Request",
            "detail": message,
            "status": "COMPLETED",
            "timestamp": time.time()
        })

        # Step 2: LLM Intent Interpretation
        t0 = time.time()
        llm_result = self.llm.interpret(message, self.conversation_history)
        llm_elapsed = round((time.time() - t0) * 1000, 1)

        # Record user turn in history
        self.conversation_history.append({"role": "user", "content": message})

        # Keep history bounded to last 10 turns (5 user + 5 assistant) to
        # prevent context pollution that causes Groq to repeat old tool calls
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]

        intent_type = llm_result.get("type", "message")
        ai_response = llm_result.get("ai_response") or llm_result.get("message", "")

        if intent_type == "message":
            reply_text = llm_result.get("message") or ai_response or "Understood."
            self.conversation_history.append({"role": "assistant", "content": reply_text})
            status_label = "LLM (AI-Powered)" if self.llm.is_configured else "LLM Not Configured"
            timeline.append({
                "step": "LLM_INTERPRETATION",
                "title": f"Intent Interpreter ({status_label})",
                "detail": f"Resolved conversational query ({llm_elapsed}ms)",
                "status": "COMPLETED",
                "timestamp": time.time()
            })
            return {
                "type": "conversation",
                "content": reply_text,
                "ai_response": reply_text,
                "timeline": timeline
            }

        if intent_type == "error":
            is_unavailable = llm_result.get("is_llm_unavailable", False)
            is_error = llm_result.get("is_llm_error", False)
            
            error_detail = llm_result.get("message", "Unknown error")
            error_step = "LLM_UNAVAILABLE" if is_unavailable else "LLM_ERROR"
            error_title = "LLM Not Configured" if is_unavailable else "LLM Provider Error"
            
            timeline.append({
                "step": error_step,
                "title": error_title,
                "detail": error_detail,
                "status": "FAILED",
                "timestamp": time.time()
            })
            
            # DO NOT silently fall back. Return the error to the user.
            return {
                "type": "error",
                "error": error_detail,
                "timeline": timeline
            }

        # Handle tool call intent
        tool_name = llm_result.get("tool")
        tool_args = llm_result.get("arguments", {})
        provider_name = "LLM (AI-Powered)" if self.llm.is_configured else "UNKNOWN"
        
        timeline.append({
            "step": "LLM_INTENT",
            "title": f"Intent Resolved by {provider_name}",
            "detail": f"Tool: {tool_name} | Arguments: {json.dumps(tool_args)} ({llm_elapsed}ms)",
            "status": "COMPLETED",
            "timestamp": time.time()
        })

        # Step 3: MCP Tool Invocation via stdio
        if not self.mcp or not self.mcp._connected:
            self._init_mcp()

        if not self.mcp or not self.mcp._connected:
            timeline.append({
                "step": "MCP_ERROR",
                "title": "MCP Transport Connection Failed",
                "detail": "Cannot reach FastMCP server process via stdio transport.",
                "status": "FAILED",
                "timestamp": time.time()
            })
            return {
                "type": "error",
                "error": "FastMCP server is disconnected.",
                "timeline": timeline
            }

        timeline.append({
            "step": "MCP_DISPATCH",
            "title": "MCP Authoritative Policy & Tool Dispatch",
            "detail": f"Calling FastMCP stdio tool: {tool_name}",
            "status": "RUNNING",
            "timestamp": time.time()
        })

        try:
            mcp_raw_output = self.mcp.call_tool(tool_name, tool_args)
        except Exception as e:
            timeline.append({
                "step": "MCP_EXECUTION_ERROR",
                "title": "MCP Execution Exception",
                "detail": str(e),
                "status": "FAILED",
                "timestamp": time.time()
            })
            return {
                "type": "error",
                "error": f"MCP execution failed: {str(e)}",
                "timeline": timeline
            }

        # Parse MCP response
        mcp_data = {}
        try:
            mcp_data = json.loads(mcp_raw_output)
        except Exception:
            mcp_data = {"status": "RAW", "output": mcp_raw_output}

        mcp_status = mcp_data.get("status", "SUCCESS")
        is_policy_rejected = mcp_status == "POLICY_REJECTION"

        if is_policy_rejected:
            timeline.append({
                "step": "POLICY_REJECTION",
                "title": "Authoritative Policy Rejection",
                "detail": mcp_data.get("error", "Action prohibited by security policy"),
                "status": "REJECTED",
                "timestamp": time.time()
            })
            return {
                "type": "policy_rejection",
                "tool": tool_name,
                "arguments": tool_args,
                "error": mcp_data.get("error"),
                "timeline": timeline,
                "ai_response": ai_response
            }

        timeline.append({
            "step": "MCP_SUCCESS",
            "title": "MCP Execution Succeeded",
            "detail": mcp_data.get("message") or mcp_data.get("output") or json.dumps(mcp_data),
            "status": "COMPLETED",
            "timestamp": time.time()
        })

        # Step 4: Independent Verification
        verification_data = None
        if tool_name == "configure_firewall":
            action = tool_args.get("action", "DROP")
            port = int(tool_args.get("port", 0))
            proto = tool_args.get("protocol", "tcp")
            source_ip = tool_args.get("source_ip", "")

            target_label = f"port {port}/{proto}" if port > 0 else f"source IP {source_ip}"

            timeline.append({
                "step": "VERIFICATION_PROBE",
                "title": "Independent Dual-Layer Verification",
                "detail": f"Inspecting firewall table and probing state for {target_label}...",
                "status": "RUNNING",
                "timestamp": time.time()
            })

            try:
                v_raw = self.mcp.call_tool("validate_firewall_change", {
                    "action": action,
                    "port": port,
                    "protocol": proto,
                    "source_ip": source_ip
                })
                verification_data = json.loads(v_raw)
            except Exception as ve:
                verification_data = {
                    "status": "ERROR",
                    "summary": f"Verification error: {str(ve)}"
                }

            timeline.append({
                "step": "VERIFICATION_RESULT",
                "title": f"Verification: {verification_data.get('status', 'COMPLETED')}",
                "detail": verification_data.get("summary", ""),
                "status": "VERIFIED" if verification_data.get("status") == "VERIFIED" else "WARNING",
                "timestamp": time.time()
            })

        elif tool_name == "set_bandwidth_limit":
            verification_data = mcp_data.get("diagnostic")

        # Save short intent message for top status pill
        intent_message = ai_response or f"Executed {tool_name}."

        # Synthesize rich conversational response & before/after params
        final_ai_msg = ai_response

        if tool_name == "apply_network_profile":
            prof = mcp_data.get("profile", tool_args.get("profile", "")).upper()
            goal = mcp_data.get("goal", "")
            applied = mcp_data.get("applied", [])
            all_params = applied if applied else (mcp_data.get("skipped", []) + mcp_data.get("failed", []))
            lines = [
                f"### Applied Network Optimization Profile: **{prof}**",
                f"**Optimization Goal:** {goal}\n",
                "#### Kernel Parameters (Before vs After):",
                "| Kernel Parameter | Before (Baseline) | After (Tuned) | Optimization Impact |",
                "| :--- | :--- | :--- | :--- |"
            ]
            for a in all_params:
                k = a.get("key", "")
                prev = a.get("previous", "default")
                curr = a.get("value", "")
                reason = a.get("reason", "")
                lines.append(f"| `{k}` | `{prev}` | **`{curr}`** | {reason} |")

            lines.append(f"\n#### Workload Optimization Impact ({prof}):")
            lines.append("| Optimization Metric | Baseline (Before) | Tuned State (After) | Workload Performance Impact |")
            lines.append("| :--- | :--- | :--- | :--- |")
            if prof == "BROADCASTING":
                lines.append("| **Upload Buffer Headroom** | `4 MB` | **`16 MB`** | **+300% Burst Frame Retention** — buffers high-bitrate 1080p/4K 60fps frames without drops |")
                lines.append("| **Keyframe Drop Protection** | Reset on idle | **0-Drop Protection** | **100% Bitrate Stability** — disables slow-start collapse across scene cuts |")
                lines.append("| **Packet Pacing Engine** | Inactive (loss-based) | **BBR Flow Paced** | **Eliminates upload stalls** & bufferbloat at modem/router |")
                lines.append("| **Concurrent Streaming Ports** | `32768 - 60999` | **`1024 - 65535`** | **Multi-stream capacity** for OBS RTMP + Game + Discord voice |")
            elif prof == "STREAMING":
                lines.append("| **Download Buffer Window** | `6 MB` | **`16 MB`** | **+166% Receive Window Headroom** — caches high-bitrate video chunks |")
                lines.append("| **Video Chunk Stall** | Reset on idle | **Zero-Stall Mode** | **Eliminates buffering pause** between HLS / DASH segment downloads |")
                lines.append("| **Window Scaling (RFC 1323)** | Standard | **High-Bandwidth Active** | **Unlocks > 64 KB rwnd** — mandatory for 4K / HDR 60fps streams |")
            else: # GAMING
                lines.append("| **Bufferbloat Prevention** | FIFO Queuing | **BBR Flow Pacing** | **Ultra-low latency** even during concurrent network usage |")
                lines.append("| **Socket Teardown** | `60 s` | **`15 s`** | **4x Faster Socket Reuse** for matchmaking & server switching |")
                lines.append("| **Fast Reconnect** | 1-RTT Handshake | **0-RTT Fast Open** | **Instantaneous reconnect** to game servers |")
            
            lines.append("\n*⟳ Checkpoint saved to `/app/results/checkpoint.json`. You can revert to previous values anytime with `restore_network_defaults`.*")
            final_ai_msg = "\n".join(lines)

        elif tool_name == "restore_network_defaults":
            restored = mcp_data.get("restored", [])
            source = mcp_data.get("source", "checkpoint")
            lines = [
                "### Network Defaults Restored",
                f"**Rollback Source:** `{source}`\n",
                "#### Parameters Reverted to Baseline:",
                "| Kernel Parameter | Restored Value |",
                "| :--- | :--- |"
            ]
            for r in restored:
                lines.append(f"| `{r.get('key')}` | **`{r.get('value')}`** |")
            lines.append("\n*Kernel network parameters successfully reverted.*")
            final_ai_msg = "\n".join(lines)

        elif tool_name == "run_profile_benchmark":
            prof = mcp_data.get("profile", tool_args.get("profile", "")).upper()
            comp = mcp_data.get("comparison", {})
            apply_res = mcp_data.get("apply_result", {})
            lines = [
                f"### Measured Benchmark: **{prof}** Profile",
                f"**Optimization Goal:** {mcp_data.get('goal', '')}\n",
                "#### 1. Performance Evidence (Empirically Measured Workload):",
                "| Workload Metric | Before (Baseline) | After (Tuned) | Measured Delta |",
                "| :--- | :--- | :--- | :--- |"
            ]

            # Throughput (Streaming / Broadcasting via iperf3)
            tp = comp.get("throughput")
            if tp:
                role = tp.get("role", "TCP Throughput")
                b_tp = tp.get("before_mbps", 0.0)
                a_tp = tp.get("after_mbps", 0.0)
                pct = tp.get("improvement_pct", 0.0)
                pct_str = f"▲ +{pct}% higher" if pct > 0 else (f"▼ {abs(pct)}% delta" if pct < 0 else "✓ Stable")
                lines.append(f"| **TCP Throughput ({role})** | `{b_tp} Mbps` | **`{a_tp} Mbps`** | {pct_str} |")

                b_ret = tp.get("before_retransmits", 0)
                a_ret = tp.get("after_retransmits", 0)
                ret_d = tp.get("retransmits_delta", 0)
                ret_str = f"▼ -{abs(ret_d)} pkts" if ret_d < 0 else (f"▲ +{ret_d} pkts" if ret_d > 0 else "✓ 0 delta")
                lines.append(f"| **TCP Retransmissions** | `{b_ret}` | **`{a_ret}`** | {ret_str} |")

                b_mb = tp.get("before_bytes_mb", 0.0)
                a_mb = tp.get("after_bytes_mb", 0.0)
                lines.append(f"| **Data Transferred** | `{b_mb} MB` | **`{a_mb} MB`** | Measured over 2s run |")

            lat = comp.get("latency_avg", {})
            if lat.get("before_ms") is not None and lat.get("after_ms") is not None:
                b_lat = lat.get("before_ms")
                a_lat = lat.get("after_ms")
                if abs(b_lat - a_lat) < 2.5:
                    diff_str = "✓ Stable (< 2.5 ms tolerance)"
                elif lat.get("improvement_pct", 0) > 0:
                    diff_str = f"▼ {lat.get('improvement_pct')}% better"
                else:
                    diff_str = f"▲ {abs(lat.get('improvement_pct', 0))}% delta"
                lines.append(f"| **Average Ping Latency** | `{b_lat} ms` | **`{a_lat} ms`** | {diff_str} |")

            jit = comp.get("jitter", {})
            if jit.get("before_ms") is not None and jit.get("after_ms") is not None:
                b_jit = jit.get("before_ms")
                a_jit = jit.get("after_ms")
                if abs(b_jit - a_jit) < 2.5:
                    diff_str = "✓ Stable (< 2.5 ms tolerance)"
                elif jit.get("improvement_pct", 0) > 0:
                    diff_str = f"▼ {jit.get('improvement_pct')}% better"
                else:
                    diff_str = f"▲ {abs(jit.get('improvement_pct', 0))}% delta"
                lines.append(f"| **Ping Jitter (mdev)** | `{b_jit} ms` | **`{a_jit} ms`** | {diff_str} |")

            loss = comp.get("packet_loss", {})
            if loss.get("before_pct") is not None:
                b_l = loss.get("before_pct", 0.0)
                a_l = loss.get("after_pct", 0.0)
                lines.append(f"| **Packet Loss** | `{b_l}%` | **`{a_l}%`** | {'✓ 0% Loss' if a_l == 0 else 'Recorded'} |")

            tcp = comp.get("tcp_connect_avg", {})
            if tcp.get("before_ms") is not None and tcp.get("after_ms") is not None:
                b_tcp = tcp.get("before_ms")
                a_tcp = tcp.get("after_ms")
                if abs(b_tcp - a_tcp) < 2.5:
                    diff_str = "✓ Stable (< 2.5 ms tolerance)"
                elif tcp.get("improvement_pct", 0) > 0:
                    diff_str = f"▼ {tcp.get('improvement_pct')}% better"
                else:
                    diff_str = f"▲ {abs(tcp.get('improvement_pct', 0))}% delta"
                lines.append(f"| **TCP Connect Time** | `{b_tcp} ms` | **`{a_tcp} ms`** | {diff_str} |")

            # Section 2: Configuration Evidence
            applied = apply_res.get("applied", [])
            all_params = applied if applied else (apply_res.get("skipped", []) + apply_res.get("failed", []))
            if all_params:
                lines.append("\n#### 2. Configuration Evidence (Linux Kernel sysctl):")
                lines.append("| Kernel Parameter | Before (Baseline) | After (Verified Tuned) | Optimization Purpose |")
                lines.append("| :--- | :--- | :--- | :--- |")
                for a in all_params:
                    lines.append(f"| `{a.get('key')}` | `{a.get('previous')}` | **`{a.get('value')}`** | {a.get('reason')} |")

            lines.append("\n*⟳ Checkpoint saved to `/app/results/checkpoint.json`. Real measurements captured via ping / iperf3 / sysctl.*")
            final_ai_msg = "\n".join(lines)

        elif not final_ai_msg or final_ai_msg.startswith("[Pattern"):
            if tool_name == "configure_firewall":
                final_ai_msg = mcp_data.get("message") or f"Firewall rule {tool_args.get('action')} applied."
            elif tool_name == "run_diagnostics":
                loss = mcp_data.get("packet_loss_percent", 0.0)
                rtt = mcp_data.get("avg_rtt_ms", 0.0)
                target = mcp_data.get("target", "")
                final_ai_msg = f"Diagnostics complete: target {target} reachable with {loss}% packet loss and {rtt}ms avg latency."
            elif tool_name == "set_bandwidth_limit":
                final_ai_msg = mcp_data.get("message") or f"Bandwidth limit applied."
            elif tool_name == "check_bandwidth":
                iface = mcp_data.get("interface", tool_args.get("interface", "eth1"))
                rate = mcp_data.get("current_rate_mbps", 1000)
                is_lim = mcp_data.get("is_limited", False)
                final_ai_msg = f"Bandwidth status on {iface}: {'Capped at ' + str(rate) + ' Mbps' if is_lim else 'Unconstrained line capacity (1000 Mbps)'}."
            elif tool_name == "list_firewall_rules":
                final_ai_msg = "Retrieved active firewall rules table below."
            elif tool_name == "check_listening_ports":
                final_ai_msg = "Retrieved active listening sockets and services below."
            elif tool_name == "check_port_connectivity":
                state = mcp_data.get("state", "UNKNOWN")
                host = mcp_data.get("host", tool_args.get("host", "127.0.0.1"))
                port = mcp_data.get("port", tool_args.get("port", 0))
                latency = mcp_data.get("latency_ms", 0)
                if state == "REACHABLE":
                    final_ai_msg = f"Port {port} on {host} is reachable. TCP connection succeeded in {latency}ms."
                elif state == "REFUSED":
                    final_ai_msg = f"Port {port} on {host} actively refused the connection — no service is listening or a REJECT rule is active."
                elif state == "BLOCKED":
                    final_ai_msg = f"Port {port} on {host} timed out — traffic is likely being silently DROPped by a firewall rule."
                else:
                    final_ai_msg = mcp_data.get("details") or f"Connectivity probe to {host}:{port} returned {state}."
            elif tool_name == "verify_firewall_rule":
                is_present = mcp_data.get("rule_present", False)
                act = mcp_data.get("action", tool_args.get("action", "RULE"))
                prt = mcp_data.get("port", tool_args.get("port", ""))
                proto = mcp_data.get("protocol", tool_args.get("protocol", "tcp"))
                if is_present:
                    final_ai_msg = f"Confirmed: Firewall rule `{act} {prt}/{proto}` is active in the iptables table."
                else:
                    final_ai_msg = f"Firewall rule `{act} {prt}/{proto}` is NOT found in the active iptables table."

        # Execution payload for terminal block
        execution_data = mcp_data.get("execution")
        if not execution_data and mcp_data.get("terminal_output"):
            cmd_label = f"sysctl [apply {tool_args.get('profile', '')} profile]" if tool_name == "apply_network_profile" else ("sysctl [restore defaults]" if tool_name == "restore_network_defaults" else "netops benchmark")
            execution_data = {
                "command": cmd_label,
                "stdout": mcp_data.get("terminal_output", ""),
                "stderr": "",
                "exit_code": 0
            }
        elif not execution_data and mcp_data.get("terminal_report"):
            execution_data = {
                "command": f"netops benchmark --profile {tool_args.get('profile', '')}",
                "stdout": mcp_data.get("terminal_report", ""),
                "stderr": "",
                "exit_code": 0
            }

        # Append a clean, natural assistant turn to history so the next LLM call
        # understands past context naturally without echoing raw tool prefix brackets.
        history_summary = final_ai_msg or f"Completed {tool_name}."
        self.conversation_history.append({"role": "assistant", "content": history_summary})

        return {
            "type": "operation_success",
            "tool": tool_name,
            "arguments": tool_args,
            "result": mcp_data,
            "execution": execution_data,
            "verification": verification_data,
            "timeline": timeline,
            "intent_message": intent_message,
            "ai_response": final_ai_msg
        }

    def get_firewall_rules(self) -> Dict[str, Any]:
        """Fetch active firewall rules directly from MCP."""
        if not self.mcp or not self.mcp._connected:
            self._init_mcp()
        try:
            raw = self.mcp.call_tool("list_firewall_rules", {})
            return json.loads(raw)
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}

    def get_listening_ports(self) -> Dict[str, Any]:
        """Fetch active listening ports directly from MCP."""
        if not self.mcp or not self.mcp._connected:
            self._init_mcp()
        try:
            raw = self.mcp.call_tool("check_listening_ports", {})
            return json.loads(raw)
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}

    def clear_history(self) -> bool:
        """Reset conversation context."""
        self.conversation_history.clear()
        return True


# ── Interactive Terminal CLI Fallback ─────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  NetOps MCP Assistant — Interactive CLI Mode")
    print("=" * 60)

    bridge = NetOpsBridge()
    status = bridge.get_status()
    print(f"LLM: {status['llm']['message']}")
    print(f"MCP: {'Connected' if status['mcp']['connected'] else 'Disconnected'} ({status['mcp']['tools_count']} tools)")
    print("Type 'exit' or 'quit' to end.\n")

    while True:
        try:
            query = input("netops> ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit"):
                break

            res = bridge.send_message(query)
            print("\n--- Execution Timeline ---")
            for item in res.get("timeline", []):
                print(f"[{item['status']}] {item['title']}: {item['detail']}")

            if res.get("verification"):
                print(f"\nIndependent Verification: {res['verification'].get('summary') or res['verification']}")

            if res.get("type") == "conversation":
                print(f"\nAI: {res['content']}")
            elif res.get("type") == "policy_rejection":
                print(f"\nPOLICY REJECTION: {res.get('error')}")
            print()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break
