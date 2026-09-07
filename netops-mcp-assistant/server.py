"""
server.py — FastMCP Server for Network Operations & Policy Validation.

Provides authoritative policy enforcement before any low-level network command is executed.
Exposes MCP tools via stdio transport to the MCP client.
"""

from fastmcp import FastMCP
import yaml
import os
import ipaddress
import json
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
    port: int = 0,
    protocol: str = "tcp",
    source_ip: str = ""
):
    sec = POLICIES.get("security_policy", {})

    if action not in sec.get("allowed_actions", ["ACCEPT", "DROP", "REJECT"]):
        raise ValueError(
            f"Action '{action}' is not permitted. "
            f"Allowed: {sec.get('allowed_actions')}"
        )

    # Validate source IP if present
    if source_ip:
        try:
            ipaddress.IPv4Address(source_ip)
        except ipaddress.AddressValueError:
            raise ValueError(f"Invalid source IP address: {source_ip}")

    # Validate port
    if not source_ip:
        if not (1 <= port <= 65535):
            raise ValueError(f"Invalid port {port}. Port must be between 1 and 65535.")
    else:
        if port != 0 and not (1 <= port <= 65535):
            raise ValueError(f"Invalid port {port}. Port must be between 1 and 65535.")

    if port in sec.get("protected_ports", [22, 53, 5000]):
        raise ValueError(
            f"Port {port} is PROTECTED by security policy (prevents lockouts)."
        )

    allow_arbitrary = sec.get("allow_arbitrary_ports", True)
    if not allow_arbitrary and port > 0:
        allowed = sec.get("allowed_ports", [])
        if port not in allowed:
            raise ValueError(
                f"Port {port} is not in allowed_ports policy list: {allowed}"
            )

    proto_lower = protocol.lower() if protocol else "tcp"
    if proto_lower not in sec.get("allowed_protocols", ["tcp", "udp", "all"]):
        raise ValueError(
            f"Protocol '{protocol}' is not permitted. Allowed: {sec.get('allowed_protocols')}"
        )

    return True


# ─── Tool 1: Configure Firewall ─────────────────────────────────
@mcp.tool()
def configure_firewall(action: str, port: int = 0, protocol: str = "tcp", source_ip: str = "") -> str:
    """
    Block or allow traffic on a specific port or source IP using iptables.
    action: ACCEPT, DROP, or REJECT
    port: port number (1-65535), or 0 when applying an IP-level rule
    protocol: tcp or udp (default: tcp)
    source_ip: optional - source IP address (e.g. 8.8.8.8)
    """
    try:
        validate_firewall_policy(action, port, protocol, source_ip)
        res = NetworkOps.apply_iptables_rule(action, port, protocol.lower() if protocol else "tcp", source_ip if source_ip else None)

        target_desc = f"port {port}/{protocol.lower()}" if port > 0 else f"source IP {source_ip}"
        if port > 0 and source_ip:
            target_desc = f"{source_ip} on port {port}/{protocol.lower()}"

        if res.get("duplicate"):
            return json.dumps({
                "status": "DUPLICATE",
                "message": f"Firewall rule already active: {action} {target_desc}",
                "action": action,
                "port": port,
                "protocol": protocol.lower() if protocol else "tcp",
                "source_ip": source_ip
            })

        if res["success"]:
            return json.dumps({
                "status": "SUCCESS",
                "message": f"Firewall rule applied successfully: [iptables {action} {target_desc}]",
                "action": action,
                "port": port,
                "protocol": protocol.lower() if protocol else "tcp",
                "source_ip": source_ip,
                "execution": {
                    "command": res.get("command"),
                    "stdout": res.get("stdout", ""),
                    "stderr": res.get("stderr", ""),
                    "returncode": res.get("returncode", 0),
                    "execution_mode": res.get("execution_mode", "unknown")
                }
            })
        return json.dumps({
            "status": "EXECUTION_FAILURE",
            "error": res.get("stderr") or "Command execution failed",
            "execution": {
                "command": res.get("command"),
                "stdout": res.get("stdout", ""),
                "stderr": res.get("stderr", ""),
                "returncode": res.get("returncode", -1),
                "execution_mode": res.get("execution_mode", "unknown")
            }
        })
    except Exception as e:
        return json.dumps({
            "status": "POLICY_REJECTION",
            "error": str(e)
        })


# ─── Tool 2: Set Bandwidth Limit ────────────────────────────────
@mcp.tool()
def set_bandwidth_limit(interface: str, rate_mbps: int) -> str:
    """
    Apply a bandwidth limit on a network interface using tc.
    interface: network interface name e.g. eth1
    rate_mbps: speed limit in Mbps (must be between 1 and 100)
    """
    try:
        sec = POLICIES.get("security_policy", {})

        # Protect critical interfaces
        if interface in sec.get("protected_interfaces", ["eth0", "lo"]):
            raise ValueError(
                f"Interface '{interface}' is PROTECTED by security policy."
            )

        # Validate bandwidth range
        bw = POLICIES.get("bandwidth_policy", {})
        min_bw = bw.get("min_bandwidth_mbps", 1)
        max_bw = bw.get("max_bandwidth_mbps", 100)

        if rate_mbps < min_bw or rate_mbps > max_bw:
            raise ValueError(
                f"{rate_mbps} Mbps is outside allowed range [{min_bw} - {max_bw} Mbps]"
            )

        # Step 1: Capture pre-throttle bandwidth state
        before_status = NetworkOps.get_bandwidth_status(interface)

        # Step 2: Apply tc bandwidth limit
        res = NetworkOps.apply_tc_bandwidth_limit(interface, rate_mbps)

        if not res["success"]:
            return json.dumps({
                "status": "EXECUTION_FAILURE",
                "error": res.get("stderr") or "tc command failed"
            })

        # Step 3: Independent verification of before vs after state
        audit = DiagnosticVerifier.verify_bandwidth_limit(interface, rate_mbps, before_status)

        verification = POLICIES.get("verification", {})
        diag = DiagnosticVerifier.verify_connectivity(
            "127.0.0.1",
            count=verification.get("ping_count", 4),
            max_allowed_loss_percent=verification.get("max_allowed_loss_percent", 0.0)
        )

        return json.dumps({
            "status": "SUCCESS",
            "message": f"Bandwidth limited to {rate_mbps} Mbps on interface {interface} (transitioned from {audit['before_text']}).",
            "bandwidth_audit": audit,
            "verification": audit,
            "diagnostic": diag
        })
    except Exception as e:
        return json.dumps({
            "status": "POLICY_REJECTION",
            "error": str(e)
        })


# ─── Tool 2b: Check Bandwidth Status ────────────────────────────
@mcp.tool()
def check_bandwidth(interface: str = "eth1") -> str:
    """
    Inspect the current bandwidth limit and active traffic control qdisc on an interface.
    interface: network interface name e.g. eth1 (default: eth1)
    """
    try:
        sec = POLICIES.get("security_policy", {})
        if interface in sec.get("protected_interfaces", ["eth0", "lo"]):
            # Still report status safely without allowing modification
            pass

        status = NetworkOps.get_bandwidth_status(interface)
        return json.dumps({
            "status": "SUCCESS",
            "interface": interface,
            "is_limited": status.get("is_limited", False),
            "current_rate_mbps": status.get("current_rate_mbps", 1000),
            "baseline_rate_mbps": status.get("baseline_rate_mbps", 1000),
            "qdisc": status.get("qdisc", "unknown"),
            "details": status.get("status_text", "")
        })
    except Exception as e:
        return json.dumps({
            "status": "ERROR",
            "error": str(e)
        })


# ─── Tool 3: Run Diagnostics ────────────────────────────────────
@mcp.tool()
def run_diagnostics(target_ip: str, mode: str = "ping") -> str:
    """
    Run network diagnostics to verify connectivity or measure bandwidth.
    target_ip: IP address to test against
    mode: ping (check reachability) or iperf3 (measure throughput)
    """
    try:
        ipaddress.IPv4Address(target_ip)
    except ipaddress.AddressValueError:
        return json.dumps({
            "status": "ERROR",
            "error": f"Invalid target IPv4 address: {target_ip}"
        })

    mode_lower = mode.lower()
    if mode_lower not in {"ping", "iperf3"}:
        return json.dumps({
            "status": "ERROR",
            "error": "Invalid diagnostic mode. Supported: 'ping' or 'iperf3'."
        })

    verification = POLICIES.get("verification", {})

    if mode_lower == "ping":
        res = DiagnosticVerifier.verify_connectivity(
            target_ip,
            count=verification.get("ping_count", 4),
            max_allowed_loss_percent=verification.get("max_allowed_loss_percent", 0.0)
        )
        return json.dumps({
            "status": res["status"],
            "target": target_ip,
            "packet_loss_percent": res["packet_loss"],
            "avg_rtt_ms": res["avg_rtt_ms"],
            "execution": res.get("execution")
        })
    elif mode_lower == "iperf3":
        res = DiagnosticVerifier.run_bandwidth_test(
            target_ip,
            duration=verification.get("iperf_duration_seconds", 5)
        )
        return json.dumps({
            "status": res["status"],
            "target": target_ip,
            "throughput_mbps": res.get("throughput_mbps", 0.0),
            "execution": res.get("execution")
        })


# ─── Tool 4: List Firewall Rules ────────────────────────────────
@mcp.tool()
def list_firewall_rules() -> str:
    """
    Show all currently active iptables firewall rules.
    """
    res = NetworkOps.list_iptables_rules()
    if isinstance(res, dict):
        return json.dumps({
            "status": "SUCCESS",
            "rules": res.get("rules", "No active firewall rules found."),
            "execution": res.get("execution")
        })
    return json.dumps({
        "status": "SUCCESS",
        "rules": res if res else "No active firewall rules found."
    })


# ─── Tool 5: Check Listening Ports ──────────────────────────────
@mcp.tool()
def check_listening_ports() -> str:
    """
    Enumerate ports currently listening on the system.
    """
    res = DiagnosticVerifier.check_listening_ports()
    return json.dumps(res)


# ─── Tool 6: Check Port Connectivity ────────────────────────────
@mcp.tool()
def check_port_connectivity(port: int, host: str = "127.0.0.1") -> str:
    """
    Actively test TCP reachability to a given host and port.
    port: TCP port number
    host: target IP (default: 127.0.0.1)
    """
    res = DiagnosticVerifier.check_port_reachable(host=host, port=port)
    return json.dumps(res)


# ─── Tool 7: Verify Firewall Rule ───────────────────────────────
@mcp.tool()
def verify_firewall_rule(action: str, port: int = 0, protocol: str = "tcp", source_ip: str = "") -> str:
    """
    Confirm whether an iptables rule actually exists in the kernel table.
    """
    res = DiagnosticVerifier.verify_firewall_rule(action=action, port=port, protocol=protocol, source_ip=source_ip)
    return json.dumps(res)


# ─── Tool 8: Validate Firewall Change ───────────────────────────
@mcp.tool()
def validate_firewall_change(action: str, port: int = 0, protocol: str = "tcp", source_ip: str = "") -> str:
    """
    Perform independent dual-layer verification of a firewall rule:
    1. Kernel rule presence check
    2. Socket behavioral probe
    """
    res = DiagnosticVerifier.verify_firewall_change(action=action, port=port, protocol=protocol, source_ip=source_ip)
    return json.dumps(res)



if __name__ == "__main__":
    mcp.run()
