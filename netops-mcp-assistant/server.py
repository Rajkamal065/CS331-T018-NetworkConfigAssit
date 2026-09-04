from fastmcp import FastMCP
import yaml
import os
from tools.net_ops import NetworkOps
from tools.verifier import DiagnosticVerifier

mcp = FastMCP("Intelligent-Network-Assistant")

# Load policies.yaml
POLICY_PATH = os.path.join(os.path.dirname(__file__), "rules", "policies.yaml")
with open(POLICY_PATH, "r") as f:
    POLICIES = yaml.safe_load(f)

# ─── Policy Validator ───────────────────────────────────────────
def validate_firewall_policy(action: str, port: int):
    sec = POLICIES["security_policy"]
    if port in sec["protected_ports"]:
        raise ValueError(f"Port {port} is PROTECTED by security policy (Prevents lockouts).")
    if action not in sec["allowed_actions"]:
        raise ValueError(f"Action '{action}' is not permitted.")
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
        validate_firewall_policy(action, port)
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
    bw = POLICIES["bandwidth_policy"]
    if rate_mbps < bw["min_bandwidth_mbps"] or rate_mbps > bw["max_bandwidth_mbps"]:
        return (f"POLICY REJECTION: {rate_mbps} Mbps is outside allowed range "
                f"[{bw['min_bandwidth_mbps']} - {bw['max_bandwidth_mbps']} Mbps]")
    res = NetworkOps.apply_tc_bandwidth_limit(interface, rate_mbps)
    if not res["success"]:
        return f"FAILED: {res['stderr']}"
    diag = DiagnosticVerifier.verify_connectivity("127.0.0.1")
    return (f"SUCCESS: Bandwidth limited to {rate_mbps} Mbps on {interface}. "
            f"Diagnostic: {diag['status']} | Loss: {diag['packet_loss']}% | RTT: {diag['avg_rtt_ms']}ms")

# ─── Tool 3: Run Diagnostics ────────────────────────────────────
@mcp.tool()
def run_diagnostics(target_ip: str, mode: str = "ping") -> str:
    """
    Run network diagnostics to verify connectivity or measure bandwidth.
    target_ip: IP address to test against
    mode: ping (check reachability) or iperf3 (measure throughput)
    """
    if mode == "ping":
        res = DiagnosticVerifier.verify_connectivity(target_ip)
        return (f"Ping Result [{target_ip}]: "
                f"Status={res['status']} | Loss={res['packet_loss']}% | RTT={res['avg_rtt_ms']}ms")
    elif mode == "iperf3":
        res = DiagnosticVerifier.run_bandwidth_test(target_ip)
        return f"iperf3 Result [{target_ip}]: Status={res['status']} | Throughput={res['throughput_mbps']} Mbps"
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
