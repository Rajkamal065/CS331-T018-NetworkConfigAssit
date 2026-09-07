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
            "name": "check_bandwidth",
            "description": "Inspect the current bandwidth rate limit, line capacity, and active traffic control qdisc on a network interface. Use when the user wants to check, view, verify, or show bandwidth.",
            "parameters": {
                "type": "object",
                "properties": {
                    "interface": {
                        "type": "string",
                        "description": "Network interface name (e.g. eth1, default: eth1)",
                        "default": "eth1"
                    }
                }
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
            self.base_url = os.environ.get(
                "OLLAMA_BASE_URL",
                "http://localhost:11434"
            ).strip()

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
                "provider": "LLM Not Configured",
                "model": "N/A",
                "message": (
                    "LLM provider not configured. Set LLM_PROVIDER "
                    "and API key to enable AI-powered intent interpretation."
                )
            }

        return {
            "connected": True,
            "provider": self.provider,
            "model": self.model,
            "message": (
                f"Connected to {self.provider} ({self.model}) - "
                "AI-powered intent interpretation active"
            )
        }

    def interpret(
        self,
        user_message: str,
        conversation_history: list = None
    ) -> dict:
        """
        Send user message to LLM for intent interpretation.

        The LLM is the PRIMARY and ONLY intent interpreter when configured.
        When LLM is not configured or fails, return a clear error
        (NOT a silent fallback).

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
            return {
                "type": "error",
                "message": (
                    "LLM provider not configured. Please set LLM_PROVIDER "
                    "and the corresponding API key "
                    "(GROQ_API_KEY, OPENROUTER_API_KEY, "
                    "ANTHROPIC_API_KEY, or OLLAMA_BASE_URL)."
                ),
                "ai_response": None,
                "is_llm_unavailable": True
            }

        try:
            if self.provider == "claude":
                return self._call_claude(
                    user_message,
                    conversation_history
                )

            elif self.provider == "ollama":
                return self._call_ollama(
                    user_message,
                    conversation_history
                )

            else:
                return self._call_openai_compatible(
                    user_message,
                    conversation_history
                )

        except Exception as e:
            logger.error(f"LLM call failed: {e}")

            return {
                "type": "error",
                "message": (
                    f"LLM provider error: {str(e)}. "
                    "Please check your API configuration and try again."
                ),
                "ai_response": None,
                "is_llm_error": True
            }

    def _call_openai_compatible(
        self,
        user_message: str,
        history: list = None
    ) -> dict:
        """Call Groq or OpenRouter using their OpenAI-compatible APIs."""

        import httpx

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

        if history:
            messages.extend(history)

        messages.append({
            "role": "user",
            "content": user_message
        })

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

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
            resp = client.post(
                url,
                json=payload,
                headers=headers
            )

            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]

        # Check for tool calls
        if msg.get("tool_calls"):
            tc = msg["tool_calls"][0]
            fn = tc["function"]

            try:
                args = (
                    json.loads(fn["arguments"])
                    if isinstance(fn["arguments"], str)
                    else fn["arguments"]
                )
            except json.JSONDecodeError:
                args = {}

            tool_name = fn["name"]

            # Normalize optional arguments before passing to MCP
            if tool_name == "configure_firewall":
                args.setdefault("protocol", "tcp")
                args.setdefault("source_ip", "")

            elif tool_name == "verify_firewall_rule":
                args.setdefault("protocol", "tcp")

            elif tool_name == "run_diagnostics":
                args.setdefault("mode", "ping")

            elif tool_name == "check_listening_ports":
                args.pop("port", None)

            return {
                "type": "tool_call",
                "tool": tool_name,
                "arguments": args,
                "ai_response": (
                    msg.get("content")
                    or f"Executing network tool: {tool_name}"
                ),
            }

        # Conversational response
        return {
            "type": "message",
            "message": msg.get("content", ""),
            "ai_response": msg.get("content", ""),
        }

    def _call_ollama(
        self,
        user_message: str,
        history: list = None
    ) -> dict:
        """Call Ollama's native chat API with structured tool definitions."""

        import httpx

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

        if history:
            messages.extend(history)

        messages.append({
            "role": "user",
            "content": user_message
        })

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": MCP_TOOLS_SCHEMA,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 1024
            },
        }

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                headers={
                    "Content-Type": "application/json"
                },
            )

            resp.raise_for_status()
            data = resp.json()

        msg = data.get("message", {})
        tool_calls = msg.get("tool_calls") or []

        if tool_calls:
            fn = tool_calls[0].get("function", {})
            args = fn.get("arguments", {})

            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}

            return {
                "type": "tool_call",
                "tool": fn.get("name", ""),
                "arguments": args,
                "ai_response": (
                    msg.get("content")
                    or f"Executing network tool: {fn.get('name', '')}"
                ),
            }

        return {
            "type": "message",
            "message": msg.get("content", ""),
            "ai_response": msg.get("content", ""),
        }

    def _call_claude(
        self,
        user_message: str,
        history: list = None
    ) -> dict:
        """Call Anthropic Claude API with tool use."""

        import httpx

        messages = []

        if history:
            messages.extend(history)

        messages.append({
            "role": "user",
            "content": user_message
        })

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
            "tool_choice": {
                "type": "auto"
            },
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{self.base_url}/messages",
                json=payload,
                headers=headers
            )

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
                "ai_response": (
                    text_content
                    or f"Executing network tool: {tool_call['name']}"
                ),
            }

        return {
            "type": "message",
            "message": text_content,
            "ai_response": text_content,
        }

    def offline_deterministic_parse(
        self,
        message: str
    ) -> dict:
        """
        OFFLINE TEST MODE ONLY: Deterministic intent parser using regex patterns.

        This is NOT the primary intent interpreter. It exists solely as an explicit
        offline/testing fallback when the LLM provider is not configured.

        DO NOT use this for production. The LLM is the authoritative intent interpreter.

        Provides robust pattern matching for common network operations.
        """

        msg = message.lower().strip()

        # 1. Query available tools / capabilities / help
        if re.search(
            r'\b(what|waht|which|list|show|give|tell)\b.*'
            r'\b(tools?|capabilities|functions|features|commands|help)\b',
            msg
        ) or msg in (
            "tools",
            "list tools",
            "show tools",
            "help",
            "what can you do",
            "commands",
            "?"
        ):
            tool_guide = (
                "Here are the network operations tools available in NetOps MCP:\n\n"
                "1. configure_firewall — Block, allow, or reject traffic on a port or IP "
                "(e.g. 'block port 8080', 'block 8.8.8.8')\n"
                "2. list_firewall_rules — Display all currently active firewall rules\n"
                "3. check_listening_ports — View open listening sockets and services on this machine\n"
                "4. set_bandwidth_limit — Throttle interface speed using traffic control "
                "(e.g. 'limit eth1 to 20 Mbps')\n"
                "5. run_diagnostics — Test reachability and measure latency via ICMP ping "
                "(e.g. 'ping 8.8.8.8')\n"
                "6. check_port_connectivity — Actively probe TCP reachability on a specific port\n"
                "7. validate_firewall_change — Independent dual-layer verification of network rules\n\n"
                "Note: Critical infrastructure ports 22 (SSH), 53 (DNS), and 5000 are authoritatively protected."
            )

            return {
                "type": "message",
                "message": tool_guide,
                "ai_response": tool_guide,
                "is_fallback": True
            }

        # 2. Bare action keywords without parameters
        if msg in (
            "block",
            "drop",
            "reject",
            "deny"
        ):
            guide = (
                "Please specify what you would like to block:\n"
                "- A port number: e.g. 'block port 8080' or 'block 9999'\n"
                "- An IP address: e.g. 'block 8.8.8.8'\n"
                "- Test lockout security: 'block port 22'"
            )

            return {
                "type": "message",
                "message": guide,
                "ai_response": guide,
                "is_fallback": True
            }

        if msg in (
            "allow",
            "accept",
            "permit",
            "open"
        ):
            guide = (
                "Please specify what you would like to allow:\n"
                "- A port number: e.g. 'allow port 8080' or 'allow 9999'\n"
                "- A port from an IP: e.g. 'allow port 80 from 192.168.1.50'"
            )

            return {
                "type": "message",
                "message": guide,
                "ai_response": guide,
                "is_fallback": True
            }

        # 3. View / List firewall rules queries
        if re.search(r'\b(fire\s*wall|iptables)\b', msg) or \
           re.search(
               r'\b(active|current|all|list|show|display|get|view|return|what|fetch|check)\b'
               r'.*\brules?\b',
               msg
           ) or \
           re.search(
               r'\brules?\b.*\b(active|current|table|fire\s*wall)\b',
               msg
           ) or msg in (
               "rules",
               "rule",
               "current rules",
               "active rules"
           ):
            return {
                "type": "tool_call",
                "tool": "list_firewall_rules",
                "arguments": {},
                "ai_response": "Retrieving active firewall configuration table.",
                "is_fallback": True
            }

        # 4. Check listening ports
        if re.search(r'\b(listening|open)\s+ports\b', msg) or \
           re.search(r'\blistening\s+port\b', msg) or \
           re.search(r'\bports?\s+listening\b', msg) or \
           re.search(
               r'\b(what|which|show|list|check)\b.*ports?.*listen',
               msg
           ) or msg in (
               "listening ports",
               "check listening",
               "open ports",
               "listening",
               "sockets"
           ):
            return {
                "type": "tool_call",
                "tool": "check_listening_ports",
                "arguments": {},
                "ai_response": "Querying active listening network ports on the system.",
                "is_fallback": True
            }

        # 5. Firewall configuration
        action_match = re.search(
            r'\b(block|drop|reject|deny|allow|accept|permit|open|close|unblock)\b',
            msg
        )

        if action_match:
            action_verb = action_match.group(1)

            action = (
                "DROP"
                if action_verb in (
                    "block",
                    "drop",
                    "reject",
                    "deny",
                    "close"
                )
                else "ACCEPT"
            )

            # Check for IP address
            ip_match = re.search(
                r'\b(\d{1,3}(?:\.\d{1,3}){3})\b',
                msg
            )

            target_ip = ip_match.group(1) if ip_match else ""

            # Check for port number
            port_match = re.search(
                r'\b(?:port|pprt|prt)?\s*'
                r'(?:is|thats|that\'s|number)?\s*(\d{1,5})\b',
                msg
            )

            candidate_port = None

            if port_match and not target_ip:
                candidate_port = int(port_match.group(1))

            elif target_ip:
                ip_clean = target_ip.replace(".", r"\.")
                without_ip = re.sub(
                    ip_clean,
                    "",
                    msg
                )

                num_match = re.search(
                    r'\b(\d{1,5})\b',
                    without_ip
                )

                if num_match:
                    candidate_port = int(num_match.group(1))

            proto = (
                "udp"
                if re.search(r'\budp\b', msg)
                else "tcp"
            )

            if candidate_port is not None and (
                1 <= candidate_port <= 65535
            ):
                return {
                    "type": "tool_call",
                    "tool": "configure_firewall",
                    "arguments": {
                        "action": action,
                        "port": candidate_port,
                        "protocol": proto,
                        "source_ip": target_ip
                    },
                    "ai_response": (
                        f"Applying firewall rule: {action} "
                        f"{proto} port {candidate_port}"
                        f"{f' from {target_ip}' if target_ip else ''}."
                    ),
                    "is_fallback": True
                }

            elif target_ip:
                return {
                    "type": "tool_call",
                    "tool": "configure_firewall",
                    "arguments": {
                        "action": action,
                        "port": 0,
                        "protocol": proto,
                        "source_ip": target_ip
                    },
                    "ai_response": (
                        f"Applying firewall rule to {action} "
                        f"traffic from source IP {target_ip}."
                    ),
                    "is_fallback": True
                }

        # 6. Bandwidth limit
        if re.search(
            r'\b(bandwidth|traffic|throttle|tc|qdisc)\b',
            msg
        ) or re.search(
            r'\b(limit|cap|restrict)\b.*\b(\d+)\b',
            msg
        ):
            clean_for_rate = re.sub(
                r'\b(etho?\d+|ens\d+|eno\d+|enp\d+s\d+|wlan\d+|lo)\b',
                '',
                msg
            )

            rate_match = re.search(
                r'(\d+)\s*(?:mbps|mbit|mb|m)?\b',
                clean_for_rate
            )

            rate = (
                int(rate_match.group(1))
                if rate_match
                else 20
            )

            rate = max(1, min(100, rate))

            iface_match = re.search(
                r'\b(etho?\d+|ens\d+|eno\d+|enp\d+s\d+|wlan\d+|lo)\b',
                msg
            )

            iface = (
                iface_match.group(1).replace("etho", "eth")
                if iface_match
                else "eth1"
            )

            return {
                "type": "tool_call",
                "tool": "set_bandwidth_limit",
                "arguments": {
                    "interface": iface,
                    "rate_mbps": rate
                },
                "ai_response": (
                    f"Configuring bandwidth limit to "
                    f"{rate} Mbps on interface {iface}."
                ),
                "is_fallback": True
            }

        # 7. Diagnostics
        if re.search(
            r'\b(ping|latency|rtt|reachability|packet\s*loss|iperf|diagnos)\b',
            msg
        ):
            ip_match = re.search(
                r'\b(\d{1,3}(?:\.\d{1,3}){3})\b',
                msg
            )

            target = (
                ip_match.group(1)
                if ip_match
                else "127.0.0.1"
            )

            mode = (
                "iperf3"
                if re.search(
                    r'\b(iperf|throughput|speed)\b',
                    msg
                )
                else "ping"
            )

            return {
                "type": "tool_call",
                "tool": "run_diagnostics",
                "arguments": {
                    "target_ip": target,
                    "mode": mode
                },
                "ai_response": (
                    f"Running network diagnostics "
                    f"({mode}) for {target}."
                ),
                "is_fallback": True
            }

        # 8. Port connectivity probe
        conn_match = re.search(
            r'\b(check|test|probe)\b.*?\bport\s+(\d{1,5})\b',
            msg
        ) or re.search(
            r'\b(connect|reach)\b.*?'
            r'(\d{1,3}(?:\.\d{1,3}){3})?'
            r'[:\s]+(\d{1,5})\b',
            msg
        )

        if conn_match:
            port = int(
                conn_match.group(2)
                if conn_match.group(2)
                else conn_match.group(3)
            )

            host_match = re.search(
                r'\b(\d{1,3}(?:\.\d{1,3}){3})\b',
                msg
            )

            host = (
                host_match.group(1)
                if host_match
                else "127.0.0.1"
            )

            return {
                "type": "tool_call",
                "tool": "check_port_connectivity",
                "arguments": {
                    "host": host,
                    "port": port
                },
                "ai_response": (
                    f"Probing TCP socket reachability "
                    f"for {host}:{port}."
                ),
                "is_fallback": True
            }

        # 9. Friendly greetings & conversation
        if re.match(
            r'^(hi|hello|hey|greetings|hola)\b',
            msg
        ):
            welcome = (
                "Hello! I am your AI Network Operations Assistant. "
                "I can help you configure firewall rules, "
                "limit interface bandwidth, inspect listening sockets, "
                "and test reachability via ICMP ping.\n\n"
                "Try commands like:\n"
                "- 'block port 8080' or 'block 8.8.8.8'\n"
                "- 'block port 22' (tests policy lockout protection)\n"
                "- 'give me firewall rules'\n"
                "- 'what ports are currently listening on this machine?'\n"
                "- 'ping 8.8.8.8'\n"
                "- 'limit eth1 to 20 Mbps'"
            )

            return {
                "type": "message",
                "message": welcome,
                "ai_response": welcome,
                "is_fallback": True
            }

        default_reply = (
            f"I received your request: \"{message}\".\n\n"
            "You can execute network operations by asking:\n"
            "- 'block port 8080' or 'block 8.8.8.8'\n"
            "- 'give me firewall rules'\n"
            "- 'check listening ports'\n"
            "- 'ping 8.8.8.8'\n"
            "- 'limit eth1 to 20 Mbps'\n"
            "- 'what tools can you do' (lists all capabilities)"
        )

        return {
            "type": "message",
            "message": default_reply,
            "ai_response": default_reply,
            "is_fallback": True
        }

    def _fallback_parse(
        self,
        message: str
    ) -> dict:
        """Deprecated: use offline_deterministic_parse() instead."""
        return self.offline_deterministic_parse(message)


# ── Module-level singleton ───────────────────────────────────────────────────

_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client

    if _llm_client is None:
        _llm_client = LLMClient()

    return _llm_client


def validate_tool_call(
    tool_name: str,
    arguments: dict
) -> tuple[bool, str]:
    """Validate that a tool call from the LLM is well-formed before sending to MCP."""

    valid_tools = {
        "configure_firewall",
        "set_bandwidth_limit",
        "run_diagnostics",
        "list_firewall_rules",
        "check_listening_ports",
        "check_port_connectivity",
        "verify_firewall_rule"
    }

    if tool_name not in valid_tools:
        return False, f"Unknown tool: {tool_name}"

    if tool_name == "configure_firewall":
        if "action" not in arguments:
            return False, "Missing required argument: action"

        if "port" not in arguments:
            return False, "Missing required argument: port"

        if arguments["action"] not in (
            "ACCEPT",
            "DROP",
            "REJECT"
        ):
            return False, f"Invalid action: {arguments['action']}"

        try:
            port = int(arguments["port"])

            if not 1 <= port <= 65535:
                return False, (
                    f"Port {port} out of range (1-65535)"
                )

        except (ValueError, TypeError):
            return False, (
                f"Invalid port: {arguments['port']}"
            )

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