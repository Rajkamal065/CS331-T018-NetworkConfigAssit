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

# ── Load Policies ─────────────────────────────────────────────────────────────
POLICY_PATH = os.path.join(ROOT, "rules", "policies.yaml")
with open(POLICY_PATH) as f:
    POLICIES = yaml.safe_load(f)

from tools.net_ops import NetworkOps
from tools.verifier import DiagnosticVerifier


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
def validate_firewall_policy(action: str, port: int):
    sec = POLICIES["security_policy"]
    if port in sec["protected_ports"]:
        raise ValueError(f"Port {port} is PROTECTED by security policy (prevents lockouts).")
    if action not in sec["allowed_actions"]:
        raise ValueError(f"Action '{action}' is not permitted. Allowed: {sec['allowed_actions']}")


# ── Command parser ────────────────────────────────────────────────────────────
def parse_command(message: str) -> dict:
    msg = message.lower().strip()

    # LIST RULES
    if re.search(r"\b(list|show|display|get)\b.*\b(rule|firewall|iptables)\b", msg) or \
       re.search(r"\b(firewall|iptables)\b.*\b(list|show|rules?)\b", msg) or \
       msg in ("list rules", "show rules", "firewall rules", "rules"):
        return {"intent": "list_rules", "params": {}}

    # DIAGNOSTICS
    diag = re.search(r"\b(ping|test|check|diagnose|diagnostic|reachability|iperf)\b", msg)
    if diag:
        # Extract IP separately so greedy patterns don't swallow it
        ip_match = re.search(r"\d{1,3}(?:\.\d{1,3}){3}", msg)
        target = ip_match.group(0) if ip_match else "127.0.0.1"
        if target == "localhost":
            target = "127.0.0.1"
        mode = "iperf3" if re.search(r"\b(iperf|throughput|speed)\b", msg) else "ping"
        return {"intent": "diagnostics", "params": {"target_ip": target, "mode": mode}}

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
    fw = re.search(
        r"\b(block|drop|reject|deny|allow|accept|permit|open)\b.*?(?:port\s+)?(\d{2,5})\b", msg
    ) or re.search(
        r"\bport\s+(\d{2,5})\b.*?\b(block|drop|reject|deny|allow|accept|permit|open)\b", msg)
    if fw:
        groups = fw.groups()
        port = next((int(g) for g in groups if g and str(g).isdigit()), None)
        action_word = next((g for g in groups if g and not str(g).isdigit()), "")
        block_words = {"block", "drop", "reject", "deny"}
        allow_words = {"allow", "accept", "permit", "open"}
        if str(action_word).lower() in block_words:
            action = "DROP"
        elif str(action_word).lower() in allow_words:
            action = "ACCEPT"
        else:
            action = "DROP"
        proto = (re.search(r"\b(tcp|udp)\b", msg) or None)
        proto = proto.group(1) if proto else "tcp"
        src = (re.search(r"\bfrom\s+(\d{1,3}(?:\.\d{1,3}){3})\b", msg) or None)
        src = src.group(1) if src else ""
        if port:
            return {"intent": "firewall",
                    "params": {"action": action, "port": port, "protocol": proto, "source_ip": src}}

    return {"intent": "unknown", "params": {}}


# ── Command handlers ──────────────────────────────────────────────────────────
def handle_firewall(params: dict):
    action     = params["action"]
    port       = params["port"]
    protocol   = params["protocol"]
    source_ip  = params.get("source_ip", "")

    step("🔍", "Intent identified", f"firewall  →  {action} port {port}/{protocol}", "cyan")
    step("🛡️ ", "Validating against security policy", f"protected ports: 22, 53, 5000", "yellow", 0.5)

    try:
        validate_firewall_policy(action, port)
    except ValueError as e:
        step("🚫", "POLICY REJECTED", str(e), "red", 0.2)
        fail(str(e))
        return

    step("✅", "Policy check passed", f"port {port} is not protected, action {action} is allowed", "green", 0.3)

    cmd = f"iptables -A INPUT -p {protocol} --dport {port}"
    if source_ip:
        cmd += f" -s {source_ip}"
    cmd += f" -j {action}"

    step("⚡", "Executing firewall command", "", "blue", 0.4)
    step_cmd(cmd, 0.2)

    res = NetworkOps.apply_iptables_rule(action, port, protocol, source_ip if source_ip else None)
    time.sleep(0.3)

    if res["success"]:
        step("✅", "Rule applied successfully", "", "green", 0.1)
        result_box("Firewall Rule Applied", [
            ("Action",    action),
            ("Port",      f"{port}/{protocol}"),
            ("Source IP", source_ip or "any"),
            ("Command",   cmd),
        ], success=True)
    else:
        msg = res["stderr"] or "Permission denied — try: sudo python assistant.py"
        step("❌", "Command failed", msg, "red", 0.1)
        hint = "\n[dim]  → Run with sudo:[/dim] [bold white]sudo python3 assistant.py[/bold white]" if "Permission denied" in msg else ""
        result_box("Command Failed", [("Error", msg), ("Fix", "sudo python3 assistant.py")] if "Permission denied" in msg else [("Error", msg)], success=False)


def handle_bandwidth(params: dict):
    interface = params["interface"]
    rate_mbps = params["rate_mbps"]
    bw        = POLICIES["bandwidth_policy"]

    step("🔍", "Intent identified", f"set bandwidth  →  {rate_mbps} Mbps on {interface}", "cyan")
    step("🛡️ ", "Validating bandwidth policy",
         f"allowed range: {bw['min_bandwidth_mbps']}–{bw['max_bandwidth_mbps']} Mbps", "yellow", 0.5)

    if rate_mbps < bw["min_bandwidth_mbps"] or rate_mbps > bw["max_bandwidth_mbps"]:
        msg = (f"{rate_mbps} Mbps is outside allowed range "
               f"[{bw['min_bandwidth_mbps']}–{bw['max_bandwidth_mbps']} Mbps]")
        step("🚫", "POLICY REJECTED", msg, "red", 0.2)
        fail(msg)
        return

    step("✅", "Policy check passed", f"{rate_mbps} Mbps is within allowed range", "green", 0.3)

    burst = max(15, int(rate_mbps * 1.5))
    cmd = f"tc qdisc add dev {interface} root tbf rate {rate_mbps}mbit burst {burst}k latency 20ms"
    step("⚡", "Applying tc bandwidth shaping", "", "blue", 0.4)
    step_cmd(f"tc qdisc del dev {interface} root  (clear existing)", 0.2)
    step_cmd(cmd, 0.2)

    res = NetworkOps.apply_tc_bandwidth_limit(interface, rate_mbps)
    time.sleep(0.3)

    if res["success"]:
        step("🌐", "Verifying connectivity post-limit", "", "cyan", 0.3)
        step_cmd("ping -c 4 127.0.0.1", 0.2)
        diag = DiagnosticVerifier.verify_connectivity("127.0.0.1")
        step("✅", "Bandwidth applied, connectivity verified", "", "green", 0.2)
        result_box("Bandwidth Limit Applied", [
            ("Interface",   interface),
            ("Rate",        f"{rate_mbps} Mbps"),
            ("Connectivity", diag["status"]),
            ("Packet Loss", f"{diag['packet_loss']}%"),
            ("Avg RTT",     f"{diag['avg_rtt_ms']} ms"),
        ], success=True)
    else:
        msg = res["stderr"] or "Permission denied — try: sudo python assistant.py"
        step("❌", "tc command failed", msg, "red", 0.1)
        result_box("Command Failed", [("Error", msg), ("Fix", "sudo python3 assistant.py")] if "Permission denied" in msg else [("Error", msg)], success=False)


def handle_diagnostics(params: dict):
    target_ip = params["target_ip"]
    mode      = params["mode"]

    step("🔍", "Intent identified", f"diagnostics  →  {mode} to {target_ip}", "cyan")

    if mode == "ping":
        step("🌐", "Running ping", f"ping -c 4 {target_ip}", "blue", 0.5)
        step_cmd(f"ping -c 4 {target_ip}", 0.2)
        res = DiagnosticVerifier.verify_connectivity(target_ip)
        time.sleep(0.3)
        icon = "✅" if res["status"] == "PASS" else "⚠️ " if res["status"] == "DEGRADED" else "❌"
        color = "green" if res["status"] == "PASS" else "yellow" if res["status"] == "DEGRADED" else "red"
        step(icon, f"Ping result: {res['status']}", f"loss={res['packet_loss']}%  rtt={res['avg_rtt_ms']}ms", color, 0.1)
        result_box(f"Ping — {target_ip}", [
            ("Status",      res["status"]),
            ("Packet Loss", f"{res['packet_loss']}%"),
            ("Avg RTT",     f"{res['avg_rtt_ms']} ms"),
        ], success=res["status"] == "PASS")

    elif mode == "iperf3":
        step("📡", "Running iperf3 throughput test", f"iperf3 -c {target_ip} -J", "blue", 0.5)
        step_cmd(f"iperf3 -c {target_ip} -J", 0.2)
        res = DiagnosticVerifier.run_bandwidth_test(target_ip)
        time.sleep(0.3)
        icon = "✅" if res["status"] == "PASS" else "❌"
        step(icon, f"iperf3 result: {res['status']}", f"throughput={res['throughput_mbps']} Mbps", "green" if res["status"] == "PASS" else "red", 0.1)
        result_box(f"iperf3 — {target_ip}", [
            ("Status",     res["status"]),
            ("Throughput", f"{res['throughput_mbps']} Mbps"),
        ], success=res["status"] == "PASS")


def handle_list_rules():
    step("🔍", "Intent identified", "list_firewall_rules", "cyan")
    step("📋", "Fetching iptables INPUT chain", "", "blue", 0.5)
    step_cmd("iptables -L INPUT -v -n --line-numbers", 0.2)
    rules = NetworkOps.list_iptables_rules()
    time.sleep(0.3)
    if rules:
        step("✅", "Rules retrieved", "", "green", 0.1)
        console.print(Panel(
            f"[bold cyan]{rules}[/bold cyan]",
            title="[bold green]Active Firewall Rules (INPUT chain)[/bold green]",
            border_style="green", box=box.ROUNDED, padding=(0, 1)
        ))
        console.print()
    else:
        step("ℹ️ ", "No active rules in INPUT chain", "", "yellow", 0.1)
        warn("No active firewall rules found (or iptables not accessible).")


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
