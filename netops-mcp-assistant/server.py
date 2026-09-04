from fastmcp import FastMCP
import yaml
import os
import ipaddress
from tools.net_ops import NetworkOps
from tools.verifier import DiagnosticVerifier

mcp = FastMCP("Intelligent-Network-Assistant")

# Load policies.yaml
POLICY_PATH = os.path.join(os.path.dirname(__file__), "rules", "policies.yaml")
with open(POLICY_PATH, "r") as f:
    POLICIES = yaml.safe_load(f)

# ─── Policy Validator ───────────────────────────────────────────
def validate_firewall_policy(
    action: str,
    port: int,
    protocol: str = "tcp",
    source_ip: str = ""
):
    sec = POLICIES["security_policy"]

    if action not in sec["allowed_actions"]:
        raise ValueError(
            f"Action '{action}' is not permitted. "
            f"Allowed: {sec['allowed_actions']}"
        )

    if not 1 <= port <= 65535:
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

# ─── Tool 1: Configure Firewall ─────────────────────────────────
@mcp.tool()
def configure_firewall(action: str, port: int, protocol: str = "tcp", source_ip: str = "") -> str:
    """
    Block or allow traffic on a specific port using iptables.
    action: ACCEPT, DROP, or REJECT
    port: port number to apply rule on
    protocol: tcp or udp (default: tcp)
    source_ip: optional - only apply rule to this source IP
    """
    try:
        validate_firewall_policy(
    action,
    port,
    protocol,
    source_ip
)
        res = NetworkOps.apply_iptables_rule(action, port, protocol, source_ip if source_ip else None)
        if res["success"]:
            return f"SUCCESS: Firewall rule applied. [iptables {action} port {port}/{protocol}]"
        return f"FAILED: {res['stderr']}"
    except Exception as e:
        return f"POLICY REJECTION: {str(e)}"

# ─── Tool 2: Set Bandwidth Limit ────────────────────────────────
@mcp.tool()
def set_bandwidth_limit(interface: str, rate_mbps: int) -> str:
    """
    Apply a bandwidth limit on a network interface using tc.
    interface: network interface name e.g. eth0
    rate_mbps: speed limit in Mbps (must be between 1 and 100)
    """
    try:
        sec = POLICIES["security_policy"]

        # Protect critical interfaces
        if interface in sec.get("protected_interfaces", []):
            raise ValueError(
                f"Interface '{interface}' is PROTECTED by security policy."
            )

        # Validate bandwidth range
        bw = POLICIES["bandwidth_policy"]

        if rate_mbps < bw["min_bandwidth_mbps"] or rate_mbps > bw["max_bandwidth_mbps"]:
            raise ValueError(
                f"{rate_mbps} Mbps is outside allowed range "
                f"[{bw['min_bandwidth_mbps']} - {bw['max_bandwidth_mbps']} Mbps]"
            )

        res = NetworkOps.apply_tc_bandwidth_limit(interface, rate_mbps)

        if not res["success"]:
            return f"FAILED: {res['stderr']}"

        verification = POLICIES["verification"]

        diag = DiagnosticVerifier.verify_connectivity(
            "127.0.0.1",
            count=verification["ping_count"],
            max_allowed_loss_percent=verification["max_allowed_loss_percent"]
        )

        return (
            f"SUCCESS: Bandwidth limited to {rate_mbps} Mbps on {interface}. "
            f"Diagnostic: {diag['status']} | "
            f"Loss: {diag['packet_loss']}% | "
            f"RTT: {diag['avg_rtt_ms']}ms"
        )
    except Exception as e:
        return f"POLICY REJECTION: {str(e)}"

# ─── Tool 3: Run Diagnostics ────────────────────────────────────
@mcp.tool()
def run_diagnostics(target_ip: str, mode: str = "ping") -> str:
    """
    Run network diagnostics to verify connectivity or measure bandwidth.
    target_ip: IP address to test against
    mode: ping (check reachability) or iperf3 (measure throughput)
    """

    # Validate target IP
    try:
        ipaddress.IPv4Address(target_ip)
    except ipaddress.AddressValueError:
        return f"Invalid target IP address: {target_ip}"

    # Validate diagnostic mode
    if mode not in {"ping", "iperf3"}:
        return "Invalid mode. Use 'ping' or 'iperf3'."

    if mode == "ping":
        verification = POLICIES["verification"]

        res = DiagnosticVerifier.verify_connectivity(
            target_ip,
            count=verification["ping_count"],
            max_allowed_loss_percent=verification["max_allowed_loss_percent"]
        )

        return (
            f"Ping Result [{target_ip}]: "
            f"Status={res['status']} | "
            f"Loss={res['packet_loss']}% | "
            f"RTT={res['avg_rtt_ms']}ms"
        )
    elif mode == "iperf3":
        verification = POLICIES["verification"]

        res = DiagnosticVerifier.run_bandwidth_test(
            target_ip,
            duration=verification["iperf_duration_seconds"]
        )

        return (
            f"iperf3 Result [{target_ip}]: "
            f"Status={res['status']} | "
            f"Throughput={res['throughput_mbps']} Mbps"
        )
    return "Invalid mode. Use 'ping' or 'iperf3'."

# ─── Tool 4: List Firewall Rules ────────────────────────────────
@mcp.tool()
def list_firewall_rules() -> str:
    """
    Show all currently active iptables firewall rules.
    """
    rules = NetworkOps.list_iptables_rules()
    if not rules:
        return "No active firewall rules found."
    return f"Active Firewall Rules:\n{rules}"

if __name__ == "__main__":
    mcp.run()
