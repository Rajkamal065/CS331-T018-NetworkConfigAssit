"""
llm_client.py — LLM integration for genuine AI-powered intent interpretation.

Supports multiple providers:
  - Groq     (free tier available, fast inference)
  - OpenRouter (access to many models)
  - Ollama   (local models, fully offline)

The LLM converts natural language into structured tool calls.
It is an intent interpreter, NOT a security authority.
All security validation happens in the MCP server.
"""

import os
import re
import json
import logging
from typing import Optional

logger = logging.getLogger("llm_client")

# ── Tool definitions given to the LLM ────────────────────────────────────────

MCP_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "configure_firewall",
            "description": "Block or allow traffic on a specific port using iptables. Use this when the user wants to block, drop, reject, allow, accept, or open a port.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["ACCEPT", "DROP", "REJECT"],
                        "description": "Firewall action: ACCEPT to allow traffic, DROP to silently block, REJECT to block with response"
                    },
                    "port": {
                        "type": "integer",
                        "description": "Port number (1-65535)"
                    },
                    "protocol": {
                        "type": "string",
                        "enum": ["tcp", "udp"],
                        "description": "Network protocol",
                        "default": "tcp"
                    },
                    "source_ip": {
                        "type": "string",
                        "description": "Optional source IP to restrict the rule to",
                        "default": ""
                    }
                },
                "required": ["action", "port"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_bandwidth_limit",
            "description": "Apply a bandwidth limit on a network interface using tc (traffic control). Use when the user wants to limit, throttle, cap, or restrict bandwidth/speed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "interface": {
                        "type": "string",
                        "description": "Network interface name (e.g. eth1, ens3)"
                    },
                    "rate_mbps": {
                        "type": "integer",
                        "description": "Speed limit in Mbps (1-100)"
                    }
                },
                "required": ["interface", "rate_mbps"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_diagnostics",
            "description": "Run network diagnostics — ping for reachability or iperf3 for throughput testing. Use when the user wants to ping, test connectivity, check reachability, or measure speed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_ip": {
                        "type": "string",
                        "description": "IP address to test"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["ping", "iperf3"],
                        "description": "Diagnostic mode",
                        "default": "ping"
                    }
                },
                "required": ["target_ip"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_firewall_rules",
            "description": "Show all currently active iptables firewall rules. Use when the user wants to see, list, show, or display firewall rules.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_listening_ports",
            "description": "Check which ports are currently listening on the system. Use when the user wants to see listening ports or check if a specific port is in use.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_port_connectivity",
            "description": "Test TCP connectivity to a specific host and port. Use when the user wants to check if a port is reachable or test a connection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Target host/IP address",
                        "default": "127.0.0.1"
                    },
                    "port": {
                        "type": "integer",
                        "description": "Port number to test"
                    }
                },
                "required": ["port"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verify_firewall_rule",
            "description": "Verify that a specific firewall rule exists in iptables. Use after applying a firewall rule to confirm it was actually created.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["ACCEPT", "DROP", "REJECT"]
                    },
                    "port": {
                        "type": "integer"
                    },
                    "protocol": {
                        "type": "string",
                        "enum": ["tcp", "udp"],
                        "default": "tcp"
                    }
                },
                "required": ["action", "port"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are NetOps MCP Assistant, an AI that helps manage Linux network configuration.

You interpret natural language requests and convert them into structured tool calls.
You NEVER generate shell commands directly. You ONLY use the provided tools.

IMPORTANT RULES:
- For blocking/dropping ports, use configure_firewall with action="DROP"
- For allowing ports, use configure_firewall with action="ACCEPT"
- For rejecting ports, use configure_firewall with action="REJECT"
- Default protocol is "tcp" unless the user specifies otherwise
- Default source_ip is "" (any source) unless the user specifies one
- For bandwidth limits, identify the interface name and rate
- For diagnostics, identify the target IP and mode (ping or iperf3)
- For listing rules, use list_firewall_rules with no arguments
- When the user asks to check ports or listening services, use check_listening_ports
- When checking connectivity to a port, use check_port_connectivity

You are an intent interpreter. Security validation is handled by the MCP server.
Respond conversationally when appropriate, but always call the relevant tool for network operations."""


class LLMClient:
    """Unified LLM client supporting multiple providers."""

    def __init__(self):
        self.provider = os.environ.get("LLM_PROVIDER", "").lower().strip()
        self.model = os.environ.get("LLM_MODEL", "").strip()
        self.api_key = None
        self.base_url = None
        self._configured = False

        self._detect_config()

    def _detect_config(self):
        """Auto-detect available LLM configuration."""
        if self.provider == "groq":
            self.api_key = os.environ.get("GROQ_API_KEY", "").strip()
            self.base_url = "https://api.groq.com/openai/v1"
            if not self.model:
                self.model = "llama-3.1-8b-instant"
            self._configured = bool(self.api_key)

        elif self.provider == "openrouter":
            self.api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
            self.base_url = "https://openrouter.ai/api/v1"
            if not self.model:
                self.model = "meta-llama/llama-3.1-8b-instruct:free"
            self._configured = bool(self.api_key)

        elif self.provider == "claude":
            self.api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            self.base_url = "https://api.anthropic.com/v1"
            if not self.model:
                self.model = "claude-sonnet-4-20250514"
            self._configured = bool(self.api_key)

        elif self.provider == "ollama":
            self.base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").strip()
            if not self.model:
                self.model = "llama3.1"
            self.api_key = "ollama"
            self._configured = True

        else:
            # Try auto-detection from available API keys
            if os.environ.get("GROQ_API_KEY", "").strip():
                self.provider = "groq"
                self._detect_config()
            elif os.environ.get("OPENROUTER_API_KEY", "").strip():
                self.provider = "openrouter"
                self._detect_config()
            elif os.environ.get("ANTHROPIC_API_KEY", "").strip():
                self.provider = "claude"
                self._detect_config()

    @property
    def is_configured(self) -> bool:
        return self._configured

    @property
    def status_info(self) -> dict:
        if not self._configured:
            return {
                "connected": False,
                "provider": None,
                "model": None,
                "message": "No LLM configured. Set LLM_PROVIDER and API key in .env file."
            }
        return {
            "connected": True,
            "provider": self.provider,
            "model": self.model,
            "message": f"Connected to {self.provider} ({self.model})"
        }

    def interpret(self, user_message: str, conversation_history: list = None) -> dict:
        """
        Send user message to LLM and get structured tool call or conversational response.

        Returns:
            {
                "type": "tool_call" | "message" | "error",
                "tool": str (if tool_call),
                "arguments": dict (if tool_call),
                "message": str (if message or error),
                "ai_response": str (the AI's conversational text)
            }
        """
        if not self._configured:
            return self._fallback_parse(user_message)

        try:
            if self.provider == "claude":
                return self._call_claude(user_message, conversation_history)
            else:
                return self._call_openai_compatible(user_message, conversation_history)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {
                "type": "error",
                "message": f"LLM error: {str(e)}. Falling back to pattern matching.",
                "fallback": self._fallback_parse(user_message)
            }

    def _call_openai_compatible(self, user_message: str, history: list = None) -> dict:
        """Call Groq/OpenRouter/Ollama using OpenAI-compatible API."""
        import httpx

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        headers = {"Content-Type": "application/json"}
        if self.provider != "ollama":
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Build the URL
        if self.provider == "ollama":
            url = f"{self.base_url}/v1/chat/completions"
        else:
            url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": MCP_TOOLS_SCHEMA,
            "tool_choice": "auto",
            "temperature": 0.1,
            "max_tokens": 1024,
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]

        # Check for tool calls
        if msg.get("tool_calls"):
            tc = msg["tool_calls"][0]
            fn = tc["function"]
            try:
                args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
            except json.JSONDecodeError:
                args = {}

            return {
                "type": "tool_call",
                "tool": fn["name"],
                "arguments": args,
                "ai_response": msg.get("content", ""),
            }

        # Conversational response
        return {
            "type": "message",
            "message": msg.get("content", ""),
            "ai_response": msg.get("content", ""),
        }

    def _call_claude(self, user_message: str, history: list = None) -> dict:
        """Call Anthropic Claude API with tool use."""
        import httpx

        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Convert tools to Claude format
        claude_tools = []
        for t in MCP_TOOLS_SCHEMA:
            fn = t["function"]
            claude_tools.append({
                "name": fn["name"],
                "description": fn["description"],
                "input_schema": fn["parameters"]
            })

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": messages,
            "tools": claude_tools,
            "tool_choice": {"type": "auto"},
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{self.base_url}/messages", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text_content = ""
        tool_call = None

        for block in data.get("content", []):
            if block["type"] == "text":
                text_content += block["text"]
            elif block["type"] == "tool_use":
                tool_call = {
                    "name": block["name"],
                    "arguments": block["input"]
                }

        if tool_call:
            return {
                "type": "tool_call",
                "tool": tool_call["name"],
                "arguments": tool_call["arguments"],
                "ai_response": text_content,
            }

        return {
            "type": "message",
            "message": text_content,
            "ai_response": text_content,
        }

    def _fallback_parse(self, message: str) -> dict:
        """
        Regex-based fallback parser when no LLM is available.
        Clearly labeled as pattern matching, not AI.
        """
        msg = message.lower().strip()

        # List rules
        if re.search(r'\b(list|show|display|get)\b.*\b(rule|firewall|iptables)\b', msg) or \
           re.search(r'\b(firewall|iptables)\b.*\b(list|show|rules?)\b', msg) or \
           msg in ("list rules", "show rules", "firewall rules", "rules"):
            return {
                "type": "tool_call",
                "tool": "list_firewall_rules",
                "arguments": {},
                "ai_response": "[Pattern matching — no LLM configured]",
                "is_fallback": True
            }

        # Firewall configuration (block/allow/open specific port)
        fw = re.search(
            r'\b(block|drop|reject|deny|allow|accept|permit|open)\b'
            r'.*?\bport\s+(\d{1,5})\b', msg
        )
        if fw:
            action_word = fw.group(1)
            port = int(fw.group(2))
            block_words = {"block", "drop", "reject", "deny"}
            action = "DROP" if action_word in block_words else "ACCEPT"

            proto_match = re.search(r'\b(tcp|udp)\b', msg)
            proto = proto_match.group(1) if proto_match else "tcp"

            src_match = re.search(r'\bfrom\s+(\d{1,3}(?:\.\d{1,3}){3})\b', msg)
            src = src_match.group(1) if src_match else ""

            if 1 <= port <= 65535:
                return {
                    "type": "tool_call",
                    "tool": "configure_firewall",
                    "arguments": {"action": action, "port": port, "protocol": proto, "source_ip": src},
                    "ai_response": "[Pattern matching — no LLM configured]",
                    "is_fallback": True
                }

        # Check listening ports (generic check, without specific port configuration)
        if re.search(r'\b(listening|open)\s+(ports|sockets)\b', msg) or \
           re.search(r'\blistening\s+port\b', msg) or \
           re.search(r'(what|which).*port.*listen', msg):
            return {
                "type": "tool_call",
                "tool": "check_listening_ports",
                "arguments": {},
                "ai_response": "[Pattern matching — no LLM configured]",
                "is_fallback": True
            }

        # Port connectivity check
        conn_match = re.search(r'\b(check|test|connect)\b.*?(\d{1,3}(?:\.\d{1,3}){3})?[:\s]+(\d{1,5})\b', msg)
        if conn_match:
            host = conn_match.group(2) or "127.0.0.1"
            port = int(conn_match.group(3))
            return {
                "type": "tool_call",
                "tool": "check_port_connectivity",
                "arguments": {"host": host, "port": port},
                "ai_response": "[Pattern matching — no LLM configured]",
                "is_fallback": True
            }

        # Bandwidth limit
        bw_rate_match = re.search(r'(\d+)\s*(?:mbps|mbit|mb)\b', msg) or re.search(r'\bto\s+(\d+)\b', msg)
        if (re.search(r'\b(limit|throttle|cap|restrict|bandwidth)\b', msg)) and bw_rate_match:
            rate = int(bw_rate_match.group(1))
            iface_match = re.search(r'\b(eth\d+|ens\d+|eno\d+|enp\d+s\d+|wlan\d+)\b', msg)
            iface = iface_match.group(1) if iface_match else "eth1"
            return {
                "type": "tool_call",
                "tool": "set_bandwidth_limit",
                "arguments": {"interface": iface, "rate_mbps": rate},
                "ai_response": "[Pattern matching — no LLM configured]",
                "is_fallback": True
            }

        # Diagnostics (ping / iperf)
        diag = re.search(r'\b(ping|test|check|diagnose|diagnostic|iperf)\b', msg)
        if diag:
            ip_match = re.search(r'\b(\d{1,3}(?:\.\d{1,3}){3})\b', msg)
            target = ip_match.group(1) if ip_match else "127.0.0.1"
            mode = "iperf3" if re.search(r'\b(iperf|throughput|speed)\b', msg) else "ping"
            return {
                "type": "tool_call",
                "tool": "run_diagnostics",
                "arguments": {"target_ip": target, "mode": mode},
                "ai_response": "[Pattern matching — no LLM configured]",
                "is_fallback": True
            }

        return {
            "type": "message",
            "message": "I couldn't understand that command. Try something like 'block port 8080' or 'ping 8.8.8.8'.",
            "ai_response": "[Pattern matching — no LLM configured]",
            "is_fallback": True
        }


# ── Module-level singleton ───────────────────────────────────────────────────

_llm_client: Optional[LLMClient] = None

def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client

def validate_tool_call(tool_name: str, arguments: dict) -> tuple[bool, str]:
    """Validate that a tool call from the LLM is well-formed before sending to MCP."""
    valid_tools = {
        "configure_firewall", "set_bandwidth_limit", "run_diagnostics",
        "list_firewall_rules", "check_listening_ports", "check_port_connectivity",
        "verify_firewall_rule"
    }

    if tool_name not in valid_tools:
        return False, f"Unknown tool: {tool_name}"

    if tool_name == "configure_firewall":
        if "action" not in arguments:
            return False, "Missing required argument: action"
        if "port" not in arguments:
            return False, "Missing required argument: port"
        if arguments["action"] not in ("ACCEPT", "DROP", "REJECT"):
            return False, f"Invalid action: {arguments['action']}"
        try:
            port = int(arguments["port"])
            if not 1 <= port <= 65535:
                return False, f"Port {port} out of range (1-65535)"
        except (ValueError, TypeError):
            return False, f"Invalid port: {arguments['port']}"

    if tool_name == "set_bandwidth_limit":
        if "interface" not in arguments:
            return False, "Missing required argument: interface"
        if "rate_mbps" not in arguments:
            return False, "Missing required argument: rate_mbps"

    if tool_name == "run_diagnostics":
        if "target_ip" not in arguments:
            return False, "Missing required argument: target_ip"

    if tool_name == "check_port_connectivity":
        if "port" not in arguments:
            return False, "Missing required argument: port"

    return True, "Valid"
