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

        # Record in history
        self.conversation_history.append({"role": "user", "content": message})

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

        # Synthesize clear conversational response for operation_success
        final_ai_msg = ai_response
        if not final_ai_msg or final_ai_msg.startswith("[Pattern"):
            if tool_name == "configure_firewall":
                final_ai_msg = mcp_data.get("message") or f"Firewall rule {tool_args.get('action')} applied."
            elif tool_name == "run_diagnostics":
                loss = mcp_data.get("packet_loss_percent", 0.0)
                rtt = mcp_data.get("avg_rtt_ms", 0.0)
                target = mcp_data.get("target", "")
                final_ai_msg = f"Diagnostics complete: target {target} reachable with {loss}% packet loss and {rtt}ms avg latency."
            elif tool_name == "set_bandwidth_limit":
                final_ai_msg = mcp_data.get("message") or f"Bandwidth limit applied."
            elif tool_name == "list_firewall_rules":
                final_ai_msg = "Retrieved active firewall rules table below."
            elif tool_name == "check_listening_ports":
                final_ai_msg = "Retrieved active listening sockets and services below."
            else:
                final_ai_msg = mcp_data.get("message") or f"Executed tool: {tool_name}"

        return {
            "type": "operation_success",
            "tool": tool_name,
            "arguments": tool_args,
            "result": mcp_data,
            "execution": mcp_data.get("execution"),
            "verification": verification_data,
            "timeline": timeline,
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
