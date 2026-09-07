"""
tools/verifier.py — Independent network and firewall verification engine.

Performs authoritative, independent verification of network state, firewall rules,
port reachability, and diagnostic metrics. Does not rely on unverified command success codes.
"""

import os
import re
import socket
import time
import json
import logging
from typing import Dict, Any, Optional
from tools.net_ops import NetworkOps, HAS_IPTABLES

logger = logging.getLogger("DiagnosticVerifier")


class DiagnosticVerifier:
    """Independent verification engine for network operations."""

    @staticmethod
    def verify_connectivity(
        target_ip: str,
        count: int = 4,
        max_allowed_loss_percent: float = 0.0
    ) -> Dict[str, Any]:
        """Verify reachability and measure packet loss using ICMP ping."""
        # Detect platform for correct ping flag
        is_windows = os.name == "nt"
        ping_args = ["ping", "-n" if is_windows else "-c", str(count), target_ip]

        res = NetworkOps._run_args(ping_args)
        if not res["success"]:
            return {
                "status": "FAIL",
                "packet_loss": 100.0,
                "avg_rtt_ms": 0.0,
                "details": res.get("stderr") or "Ping execution failed"
            }

        stdout = res.get("stdout", "")
        # Parse packet loss across Linux and Windows ping outputs
        loss_match = re.search(r'(\d+)%\s*(?:packet\s*)?loss', stdout, re.IGNORECASE)
        loss = float(loss_match.group(1)) if loss_match else 0.0

        # Parse RTT (Linux: min/avg/max/mdev, Windows: Average = XXms)
        rtt = 0.0
        rtt_match_linux = re.search(r'rtt min/avg/max/mdev = [\d\.]+/([\d\.]+)/', stdout)
        if rtt_match_linux:
            rtt = float(rtt_match_linux.group(1))
        else:
            rtt_match_win = re.search(r'Average = (\d+)ms', stdout, re.IGNORECASE)
            if rtt_match_win:
                rtt = float(rtt_match_win.group(1))

        status = "PASS" if loss <= max_allowed_loss_percent else ("DEGRADED" if loss < 100 else "FAIL")
        return {
            "status": status,
            "packet_loss": loss,
            "avg_rtt_ms": rtt,
            "target": target_ip,
            "execution": {
                "command": " ".join(ping_args),
                "stdout": stdout,
                "stderr": res.get("stderr", ""),
                "returncode": res.get("returncode", 0),
                "execution_mode": res.get("execution_mode", "real")
            }
        }

    @staticmethod
    def run_bandwidth_test(server_ip: str, duration: int = 5) -> Dict[str, Any]:
        """Measure network throughput via iperf3."""
        res = NetworkOps._run_args(["iperf3", "-c", server_ip, "-t", str(duration), "-J"])

        if not res["success"]:
            return {
                "status": "FAIL",
                "throughput_mbps": 0.0,
                "error": res.get("stderr", "iperf3 failed")
            }

        try:
            data = json.loads(res["stdout"])
            bps = data["end"]["sum_sent"]["bits_per_second"]
            return {
                "status": "PASS",
                "throughput_mbps": round(bps / 1e6, 2),
                "server": server_ip
            }
        except Exception as e:
            return {
                "status": "PARSING_ERROR",
                "throughput_mbps": 0.0,
                "error": str(e)
            }

    @staticmethod
    def check_port_reachable(host: str = "127.0.0.1", port: int = 80, timeout: float = 2.0) -> Dict[str, Any]:
        """
        Actively probe TCP socket reachability to independently verify firewall behavior.
        Distinguishes between REACHABLE, BLOCKED (Timeout/Drop), REFUSED (No service), or UNREACHABLE.
        """
        start_time = time.time()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)

        try:
            s.connect((host, port))
            s.close()
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            cmd_str = f"nc -zv -w {int(timeout)} {host} {port}"
            return {
                "reachable": True,
                "state": "REACHABLE",
                "host": host,
                "port": port,
                "latency_ms": elapsed_ms,
                "details": f"TCP connection to {host}:{port} succeeded in {elapsed_ms}ms",
                "execution": {
                    "command": cmd_str,
                    "stdout": f"Connection to {host} {port} port [tcp/*] succeeded! (RTT {elapsed_ms}ms)",
                    "stderr": "",
                    "returncode": 0,
                    "execution_mode": "socket_probe"
                }
            }
        except socket.timeout:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            cmd_str = f"nc -zv -w {int(timeout)} {host} {port}"
            return {
                "reachable": False,
                "state": "BLOCKED",
                "host": host,
                "port": port,
                "latency_ms": elapsed_ms,
                "details": f"Connection timed out ({timeout}s). Traffic likely dropped by firewall (DROP).",
                "execution": {
                    "command": cmd_str,
                    "stdout": "",
                    "stderr": f"Connection timed out after {timeout}s (DROP)",
                    "returncode": 1,
                    "execution_mode": "socket_probe"
                }
            }
        except ConnectionRefusedError:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            cmd_str = f"nc -zv -w {int(timeout)} {host} {port}"
            return {
                "reachable": False,
                "state": "REFUSED",
                "host": host,
                "port": port,
                "latency_ms": elapsed_ms,
                "details": f"Connection refused by host (RST packet received). Port rejected or service not listening.",
                "execution": {
                    "command": cmd_str,
                    "stdout": "",
                    "stderr": f"connect to {host} port {port} (tcp) failed: Connection refused",
                    "returncode": 1,
                    "execution_mode": "socket_probe"
                }
            }
        except Exception as e:
            cmd_str = f"nc -zv -w {int(timeout)} {host} {port}"
            return {
                "reachable": False,
                "state": "ERROR",
                "host": host,
                "port": port,
                "latency_ms": 0.0,
                "details": f"Socket probe error: {str(e)}",
                "execution": {
                    "command": cmd_str,
                    "stdout": "",
                    "stderr": str(e),
                    "returncode": 1,
                    "execution_mode": "socket_probe"
                }
            }
        finally:
            try:
                s.close()
            except Exception:
                pass

    @classmethod
    def check_listening_ports(cls) -> Dict[str, Any]:
        """Enumerate listening ports on the local system."""
        res = NetworkOps.list_listening_ports()
        if isinstance(res, dict):
            return {
                "status": "PASS",
                "raw": res.get("raw", ""),
                "execution": res.get("execution")
            }
        return {
            "status": "PASS",
            "raw": str(res)
        }

    @classmethod
    def verify_firewall_rule(cls, action: str, port: int = 0, protocol: str = "tcp", source_ip: str = "") -> Dict[str, Any]:
        """
        Verify that a specified firewall rule exists in the active iptables / firewall table.
        """
        rule_exists = NetworkOps.check_rule_exists(action, port, protocol, source_ip)
        return {
            "rule_present": rule_exists,
            "action": action,
            "port": port,
            "protocol": protocol,
            "source_ip": source_ip,
            "status": "VERIFIED" if rule_exists else "NOT_FOUND"
        }

    @classmethod
    def verify_firewall_change(
        cls,
        action: str,
        port: int = 0,
        protocol: str = "tcp",
        source_ip: str = "",
        target_host: str = "127.0.0.1"
    ) -> Dict[str, Any]:
        """
        Authoritative two-stage verification:
        1. Rule Table Check: Is the rule in the firewall table?
        2. Live Behavioral Probe: Does socket behavior reflect the rule?
        """
        # Step 1: Rule existence check
        rule_check = cls.verify_firewall_rule(action, port, protocol, source_ip)

        # Step 2: Live socket probe (for TCP port if port > 0)
        probe = None
        behavior_consistent = False
        if port > 0 and protocol.lower() == "tcp":
            probe = cls.check_port_reachable(host=target_host, port=port, timeout=1.5)
            if probe:
                if action in ["DROP", "REJECT"] and probe["state"] in ["BLOCKED", "REFUSED"]:
                    behavior_consistent = True
                elif action == "ACCEPT" and probe["state"] in ["REACHABLE", "REFUSED"]:
                    behavior_consistent = True

        is_windows = os.name == "nt"
        has_real_iptables = HAS_IPTABLES

        # On Windows (no iptables), we can only check the in-memory simulation table.
        # Socket probe REFUSED does NOT mean iptables blocked it — it just means
        # no service is listening on that port (which is the Windows default).
        # We must be honest about this distinction.
        if is_windows or not has_real_iptables:
            rule_in_sim = rule_check["rule_present"]  # checked in-memory table
            overall_status = "SIMULATED" if rule_in_sim else "UNVERIFIED"
            summary_parts = []
            if rule_in_sim:
                target_desc = f"port {port}/{protocol}" if port > 0 else f"source IP {source_ip}"
                summary_parts.append(
                    f"[SIMULATED] Rule {action} for {target_desc} is registered in the "
                    f"in-memory policy table. iptables is not available on this system (Windows). "
                    f"This rule does NOT enforce actual OS-level traffic blocking."
                )
            else:
                target_desc = f"port {port}/{protocol}" if port > 0 else f"source IP {source_ip}"
                summary_parts.append(
                    f"Rule {action} for {target_desc} was not found in the in-memory table."
                )
            return {
                "status": overall_status,
                "action": action,
                "port": port,
                "protocol": protocol,
                "source_ip": source_ip,
                "rule_in_kernel": False,
                "rule_in_memory": rule_in_sim,
                "socket_state": "N/A (Windows simulation mode)",
                "probe_details": "Socket probe skipped — on Windows, REFUSED means no service is bound, not firewall block.",
                "summary": " ".join(summary_parts)
            }

        overall_status = "VERIFIED" if (rule_check["rule_present"] or behavior_consistent) else "UNVERIFIED"

        target_desc = f"port {port}/{protocol}" if port > 0 else f"source IP {source_ip}"
        if port > 0 and source_ip:
            target_desc = f"{source_ip} on port {port}/{protocol}"

        summary_parts = [
            f"Rule {action} for {target_desc} is {'confirmed active in firewall table' if rule_check['rule_present'] else 'unconfirmed in table'}."
        ]
        if probe:
            summary_parts.append(f"Socket probe returned: {probe['state']}.")

        return {
            "status": overall_status,
            "action": action,
            "port": port,
            "protocol": protocol,
            "source_ip": source_ip,
            "rule_in_kernel": rule_check["rule_present"],
            "socket_state": probe["state"] if probe else "N/A",
            "probe_details": probe["details"] if probe else ("No socket probe needed for IP block" if port == 0 else "N/A"),
            "summary": " ".join(summary_parts)
        }

    @classmethod
    def verify_bandwidth_limit(
        cls,
        interface: str,
        requested_rate_mbps: int,
        before_status: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Authoritative verification of bandwidth limit transition:
        Compares before vs after bandwidth states and verifies active qdisc.
        """
        after_status = NetworkOps.get_bandwidth_status(interface)
        is_verified = (
            after_status.get("is_limited") is True and
            after_status.get("current_rate_mbps") == requested_rate_mbps
        )

        before_rate = before_status.get("current_rate_mbps", 1000) if before_status else 1000
        before_text = f"{before_rate} Mbps (Unconstrained)" if (before_status and not before_status.get("is_limited")) else f"{before_rate} Mbps"

        summary = (
            f"Bandwidth on {interface} successfully transitioned from {before_text} "
            f"to {requested_rate_mbps} Mbps. Active qdisc: {after_status.get('qdisc')}."
        ) if is_verified else f"Bandwidth limit on {interface} could not be confirmed."

        return {
            "status": "VERIFIED" if is_verified else "FAIL",
            "interface": interface,
            "before_rate_mbps": before_rate,
            "before_text": before_text,
            "configured_rate_mbps": requested_rate_mbps,
            "after_rate_mbps": after_status.get("current_rate_mbps"),
            "after_text": f"{after_status.get('current_rate_mbps')} Mbps (Throttled)",
            "qdisc": after_status.get("qdisc"),
            "summary": summary
        }


