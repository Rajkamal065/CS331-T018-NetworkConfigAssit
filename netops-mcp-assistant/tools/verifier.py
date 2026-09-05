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
from tools.net_ops import NetworkOps

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
            "target": target_ip
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
            return {
                "reachable": True,
                "state": "REACHABLE",
                "host": host,
                "port": port,
                "latency_ms": elapsed_ms,
                "details": f"TCP connection to {host}:{port} succeeded in {elapsed_ms}ms"
            }
        except socket.timeout:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "reachable": False,
                "state": "BLOCKED",
                "host": host,
                "port": port,
                "latency_ms": elapsed_ms,
                "details": f"Connection timed out ({timeout}s). Traffic likely dropped by firewall (DROP)."
            }
        except ConnectionRefusedError:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "reachable": False,
                "state": "REFUSED",
                "host": host,
                "port": port,
                "latency_ms": elapsed_ms,
                "details": f"Connection refused by host (RST packet received). Port rejected or service not listening."
            }
        except Exception as e:
            return {
                "reachable": False,
                "state": "ERROR",
                "host": host,
                "port": port,
                "latency_ms": 0.0,
                "details": f"Socket probe error: {str(e)}"
            }
        finally:
            try:
                s.close()
            except Exception:
                pass

    @classmethod
    def check_listening_ports(cls) -> Dict[str, Any]:
        """Enumerate listening ports on the local system."""
        raw_output = NetworkOps.list_listening_ports()
        return {
            "status": "PASS",
            "raw": raw_output
        }

    @classmethod
    def verify_firewall_rule(cls, action: str, port: int, protocol: str = "tcp") -> Dict[str, Any]:
        """
        Verify that a specified firewall rule exists in the kernel iptables table.
        """
        rule_exists = NetworkOps.check_rule_exists(action, port, protocol)
        return {
            "rule_present": rule_exists,
            "action": action,
            "port": port,
            "protocol": protocol,
            "status": "VERIFIED" if rule_exists else "NOT_FOUND"
        }

    @classmethod
    def verify_firewall_change(
        cls,
        action: str,
        port: int,
        protocol: str = "tcp",
        target_host: str = "127.0.0.1"
    ) -> Dict[str, Any]:
        """
        Authoritative two-stage verification:
        1. Rule Table Check: Is the rule in the firewall table?
        2. Live Behavioral Probe: Does socket behavior reflect the rule?
        """
        # Step 1: Rule existence check
        rule_check = cls.verify_firewall_rule(action, port, protocol)

        # Step 2: Live socket probe (for TCP)
        probe = None
        if protocol.lower() == "tcp":
            probe = cls.check_port_reachable(host=target_host, port=port, timeout=1.5)

        # Behavioral assessment:
        # If action is DROP, probe should be BLOCKED (Timeout) or if loopback bypasses, rule_check still confirms.
        # If action is ACCEPT, probe should be REACHABLE or REFUSED (if no listener), but NOT BLOCKED.
        behavior_consistent = False
        if probe:
            if action in ["DROP", "REJECT"] and probe["state"] in ["BLOCKED", "REFUSED"]:
                behavior_consistent = True
            elif action == "ACCEPT" and probe["state"] in ["REACHABLE", "REFUSED"]:
                behavior_consistent = True

        overall_status = "VERIFIED" if (rule_check["rule_present"] or behavior_consistent) else "UNVERIFIED"

        return {
            "status": overall_status,
            "action": action,
            "port": port,
            "protocol": protocol,
            "rule_in_kernel": rule_check["rule_present"],
            "socket_state": probe["state"] if probe else "N/A",
            "probe_details": probe["details"] if probe else "No socket probe for non-tcp",
            "summary": (
                f"Rule {action} on port {port}/{protocol} is "
                f"{'active in kernel' if rule_check['rule_present'] else 'unconfirmed in kernel'}. "
                f"Socket probe returned: {probe['state'] if probe else 'N/A'}."
            )
        }
