#!/usr/bin/env python3
"""
NetOps MCP Assistant — Interactive Terminal CLI
Run: python assistant.py
"""

import os
import re
import sys
import time
import json
import ipaddress

# ── Make sure project root is on the path ────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import yaml
try:
    import readline  # enables arrow keys, history in the prompt
except ImportError:
    pass
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich import box

console = Console()

def set_output(output):
    global console
    console = Console(file=output, force_terminal=False)
# ── Load Policies ─────────────────────────────────────────────────────────────
POLICY_PATH = os.path.join(ROOT, "rules", "policies.yaml")
with open(POLICY_PATH) as f:
    POLICIES = yaml.safe_load(f)

from mcp_client import get_mcp_client


# ── Step printer — the core "live execution" feel ─────────────────────────────
def step(icon: str, label: str, detail: str = "", color: str = "cyan", delay: float = 0.4):
    """Print a single execution step with icon, label, and optional detail."""
    time.sleep(delay)
    line = Text()
    line.append(f"  {icon}  ", style="bold")
    line.append(label, style=f"bold {color}")
    if detail:
        line.append(f"  →  {detail}", style="dim white")
    console.print(line)


def step_cmd(cmd: str, delay: float = 0.3):
    """Print the actual shell command being run."""
    time.sleep(delay)
    console.print(f"     [dim]$ {cmd}[/dim]")


def ok(msg: str):
    console.print(f"\n  [bold green]✔  {msg}[/bold green]\n")


def fail(msg: str):
    console.print(f"\n  [bold red]✘  {msg}[/bold red]\n")


def warn(msg: str):
    console.print(f"\n  [bold yellow]⚠  {msg}[/bold yellow]\n")


def result_box(title: str, lines: list[tuple], success: bool = True):
    """Print a result summary box."""
    color = "green" if success else "red"
    content = "\n".join(f"  [dim]{k}[/dim]  [bold white]{v}[/bold white]" for k, v in lines)
    console.print(Panel(content, title=f"[bold {color}]{title}[/bold {color}]",
                         border_style=color, box=box.ROUNDED, padding=(0, 1)))
    console.print()


# ── Policy helpers ────────────────────────────────────────────────────────────
def validate_firewall_policy(action: str, port: int, protocol: str = "tcp", source_ip: str = ""):
    sec = POLICIES["security_policy"]

    if action not in sec["allowed_actions"]:
        raise ValueError(
            f"Action '{action}' is not permitted. "
            f"Allowed: {sec['allowed_actions']}"
        )

    if port < 1 or port > 65535:
        raise ValueError(
            f"Invalid port {port}. Port must be between 1 and 65535."
        )

    if port in sec["protected_ports"]:
        raise ValueError(
            f"Port {port} is PROTECTED by security policy "
            f"(prevents lockouts)."
        )

    if port not in sec["allowed_ports"]:
        raise ValueError(
            f"Port {port} is not allowed by security policy. "
            f"Allowed ports: {sec['allowed_ports']}"
        )

    if protocol not in {"tcp", "udp"}:
        raise ValueError(
            f"Protocol '{protocol}' is not permitted. "
            f"Use tcp or udp."
        )

    if source_ip:
        try:
            ipaddress.IPv4Address(source_ip)
        except ipaddress.AddressValueError:
            raise ValueError(
                f"Invalid source IP address: {source_ip}"
            )

    return True

def validate_ip_address(ip: str) -> bool:
    """Return True only for a valid IPv4 address."""
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ipaddress.AddressValueError:
        return False
# ── Command parser ────────────────────────────────────────────────────────────
def parse_command(message: str) -> dict:
    msg = message.lower().strip()

    # LIST RULES
    if re.search(r"\b(list|show|display|get)\b.*\b(rule|firewall|iptables)\b", msg) or \
       re.search(r"\b(firewall|iptables)\b.*\b(list|show|rules?)\b", msg) or \
       msg in ("list rules", "show rules", "firewall rules", "rules"):
        return {"intent": "list_rules", "params": {}}

    # DIAGNOSTICS
    diag = re.search(
        r"\b(ping|test|check|diagnose|diagnostic|reachability|iperf)\b",
        msg
    )

    if diag:
        # Extract IPv4 address separately
        ip_match = re.search(
            r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
            msg
        )

        if ip_match:
            target = ip_match.group(0)

            # Make sure it is a real IPv4 address
            if not validate_ip_address(target):
                return {
                    "intent": "unknown",
                    "params": {}
                }
        else:
            target = "127.0.0.1"

        if target == "localhost":
            target = "127.0.0.1"

        mode = (
            "iperf3"
            if re.search(r"\b(iperf|throughput|speed)\b", msg)
            else "ping"
        )

        return {
            "intent": "diagnostics",
            "params": {
                "target_ip": target,
                "mode": mode
            }
        }
    # BANDWIDTH
    bw = re.search(
        r"\b(limit|throttle|set|cap|restrict)\b.*\b(bandwidth|speed|rate|bw)\b"
        r".*?(\d+)\s*(mb|mbps|mbit|m)?", msg
    ) or re.search(r"\b(bandwidth|speed|rate)\b.*?(\d+)\s*(mb|mbps|mbit|m)?", msg)
    if bw:
        rate = next((int(g) for g in bw.groups() if g and str(g).isdigit()), None)
        iface = (re.search(r"\b(eth\d+|ens\d+|eno\d+|enp\d+s\d+|lo|wlan\d+)\b", msg) or None)
        iface = iface.group(1) if iface else "eth0"
        if rate:
            return {"intent": "bandwidth", "params": {"interface": iface, "rate_mbps": rate}}

     # FIREWALL
    # Require the word "port" so IPv4 addresses are never
    # mistaken for port numbers.

    fw = re.search(
        r"\b(block|drop|reject|deny|allow|accept|permit|open)\b"
        r".*?\bport\s+(\d{1,5})\b",
        msg
    )

    if fw:
        action_word = fw.group(1)
        port = int(fw.group(2))

        block_words = {
            "block",
            "drop",
            "reject",
            "deny"
        }

        allow_words = {
            "allow",
            "accept",
            "permit",
            "open"
        }

        if action_word in block_words:
            action = "DROP"
        elif action_word in allow_words:
            action = "ACCEPT"
        else:
            action = "DROP"

        protocol_match = re.search(
            r"\b(tcp|udp|icmp)\b",
            msg
        )

        if protocol_match:
            proto = protocol_match.group(1)

            if proto not in {"tcp", "udp"}:
                return {
                    "intent": "unknown",
                    "params": {}
                }
        else:
            proto = "tcp"

        src_match = re.search(
            r"\bfrom\s+(\d{1,3}(?:\.\d{1,3}){3})\b",
            msg
        )

        if src_match:
            src = src_match.group(1)

            if not validate_ip_address(src):
                return {
                    "intent": "unknown",
                    "params": {}
                }
        else:
            src = ""

        if 1 <= port <= 65535:
            return {
                "intent": "firewall",
                "params": {
                    "action": action,
                    "port": port,
                    "protocol": proto,
                    "source_ip": src
                }
            }

    return {"intent": "unknown", "params": {}}

# ── Command handlers ──────────────────────────────────────────────────────────
def handle_firewall(params: dict):
    action     = params["action"]
    port       = params["port"]
    protocol   = params["protocol"]
    source_ip  = params.get("source_ip", "")

    step("🔍", "Intent identified", f"firewall  →  {action} port {port}/{protocol}", "cyan")
    step("🛡️ ", "Checking policy via MCP Server", f"target port: {port}", "yellow", 0.3)
    step("📡", "Invoking MCP tool", f"configure_firewall({action}, {port}, {protocol})", "blue", 0.3)

    client = get_mcp_client()
    res_text = client.call_tool("configure_firewall", {
        "action": action,
        "port": port,
        "protocol": protocol,
        "source_ip": source_ip
    })

    if "POLICY REJECTION" in res_text:
        reason = res_text.replace("POLICY REJECTION:", "").strip()
        step("🚫", "POLICY REJECTED BY MCP SERVER", reason, "red", 0.2)
        fail(reason)
    elif "SUCCESS" in res_text:
        step("✅", "Rule applied by MCP Server", res_text, "green", 0.2)
        result_box("Firewall Rule Applied (via MCP)", [
            ("Action",       action),
            ("Port",         f"{port}/{protocol}"),
            ("Source IP",    source_ip or "any"),
            ("MCP Response", res_text),
        ], success=True)
    else:
        step("❌", "Command failed", res_text, "red", 0.2)
        result_box("Command Failed", [("Error", res_text)], success=False)


def handle_bandwidth(params: dict):
    interface = params["interface"]
    rate_mbps = params["rate_mbps"]

    step("🔍", "Intent identified", f"set bandwidth  →  {rate_mbps} Mbps on {interface}", "cyan")
    step("🛡️ ", "Checking bandwidth policy via MCP Server", f"interface: {interface}, rate: {rate_mbps} Mbps", "yellow", 0.3)
    step("📡", "Invoking MCP tool", f"set_bandwidth_limit({interface}, {rate_mbps})", "blue", 0.3)

    client = get_mcp_client()
    res_text = client.call_tool("set_bandwidth_limit", {
        "interface": interface,
        "rate_mbps": rate_mbps
    })

    if "POLICY REJECTION" in res_text:
        reason = res_text.replace("POLICY REJECTION:", "").strip()
        step("🚫", "POLICY REJECTED BY MCP SERVER", reason, "red", 0.2)
        fail(reason)
    elif "SUCCESS" in res_text:
        step("✅", "Bandwidth limit applied by MCP Server", res_text, "green", 0.2)
        result_box("Bandwidth Limit Applied (via MCP)", [
            ("Interface", interface),
            ("Rate",      f"{rate_mbps} Mbps"),
            ("MCP Result", res_text)
        ], success=True)
    else:
        step("❌", "Command failed", res_text, "red", 0.2)
        fail(res_text)


def handle_diagnostics(params: dict):
    target_ip = params["target_ip"]
    mode      = params["mode"]

    step("🔍", "Intent identified", f"diagnostics  →  {mode} to {target_ip}", "cyan")
    step("📡", "Invoking MCP tool", f"run_diagnostics({target_ip}, {mode})", "blue", 0.3)

    client = get_mcp_client()
    res_text = client.call_tool("run_diagnostics", {
        "target_ip": target_ip,
        "mode": mode
    })

    is_pass = "PASS" in res_text or "Status=PASS" in res_text
    icon = "✅" if is_pass else "❌"
    color = "green" if is_pass else "red"

    step(icon, f"Diagnostic Result (via MCP)", res_text, color, 0.2)
    result_box(f"Diagnostics — {target_ip} ({mode})", [
        ("Target", target_ip),
        ("Mode", mode),
        ("Result", res_text),
    ], success=is_pass)


def handle_list_rules():
    step("🔍", "Intent identified", "list_firewall_rules", "cyan")
    step("📡", "Invoking MCP tool", "list_firewall_rules()", "blue", 0.3)

    client = get_mcp_client()
    res_text = client.call_tool("list_firewall_rules", {})

    step("✅", "Rules retrieved via MCP Server", "", "green", 0.2)
    console.print(Panel(
        f"[bold cyan]{res_text}[/bold cyan]",
        title="[bold green]Active Firewall Rules (via MCP Server)[/bold green]",
        border_style="green", box=box.ROUNDED, padding=(0, 1)
    ))
    console.print()


def handle_help():
    console.print(Panel(
        """[bold cyan]Firewall[/bold cyan]
  block port 8080
  allow port 443
  drop udp port 9090
  reject port 3306 from 192.168.1.100

[bold cyan]Bandwidth[/bold cyan]
  limit bandwidth to 10 Mbps on eth0
  throttle eth0 to 50 mbps
  set rate to 5 Mbps on ens3

[bold cyan]Diagnostics[/bold cyan]
  ping 127.0.0.1
  check connectivity to 8.8.8.8
  run iperf3 test to 192.168.1.10

[bold cyan]Rules[/bold cyan]
  list firewall rules
  show rules

[bold cyan]Other[/bold cyan]
  help    — show this message
  exit    — quit the assistant""",
        title="[bold white]Available Commands[/bold white]",
        border_style="blue", box=box.ROUNDED, padding=(0, 2)
    ))
    console.print()


# ── Banner ────────────────────────────────────────────────────────────────────
def print_banner():
    console.print()
    console.print(Panel(
        "[bold white]🛡️  NetOps MCP Assistant[/bold white]\n"
        "[dim]Intelligent Network Operations via Natural Language[/dim]\n\n"
        "[dim]Tools:[/dim] [cyan]configure_firewall[/cyan]  [cyan]set_bandwidth_limit[/cyan]  "
        "[cyan]run_diagnostics[/cyan]  [cyan]list_firewall_rules[/cyan]\n"
        "[dim]Type [/dim][bold white]help[/bold white][dim] for command examples · [/dim]"
        "[bold white]exit[/bold white][dim] to quit[/dim]",
        border_style="bright_blue",
        box=box.DOUBLE_EDGE,
        padding=(1, 4),
    ))
    console.print()


# ── Main REPL ─────────────────────────────────────────────────────────────────
def main():
    print_banner()

    while True:
        try:
            # Prompt
            console.print("[bold bright_blue]netops[/bold bright_blue][dim]>[/dim] ", end="")
            message = input().strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye![/dim]")
            break

        if not message:
            continue

        low = message.lower()
        if low in ("exit", "quit", "q"):
            console.print("\n[dim]Bye![/dim]")
            break
        if low in ("help", "h", "?"):
            handle_help()
            continue

        # Separator
        console.print(Rule(style="dim"))

        # Parse
        step("🧠", "Parsing command", f'"{message}"', "white", 0.2)
        parsed = parse_command(message)

        if parsed["intent"] == "unknown":
            step("❓", "Command not recognized", "", "red", 0.2)
            warn("Could not understand that command. Type [bold]help[/bold] for examples.")
            continue

        # Dispatch
        if parsed["intent"] == "firewall":
            handle_firewall(parsed["params"])
        elif parsed["intent"] == "bandwidth":
            handle_bandwidth(parsed["params"])
        elif parsed["intent"] == "diagnostics":
            handle_diagnostics(parsed["params"])
        elif parsed["intent"] == "list_rules":
            handle_list_rules()


if __name__ == "__main__":
    main()
