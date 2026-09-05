"""
tools/net_ops.py — Low-level Linux network operations.

All operations use subprocess with argument arrays (no shell=True).
No arbitrary command execution is exposed.
"""

import subprocess
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NetOps")


class NetworkOps:
    """Safe wrappers around Linux networking commands (iptables, tc)."""

    @staticmethod
    def _run_args(args: list[str]) -> dict:
        """Run a command with an explicit argument list. Never uses shell=True."""
        try:
            result = subprocess.run(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, check=False, timeout=15
            )
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip()
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "returncode": -1, "stdout": "", "stderr": "Command timed out"}
        except Exception as e:
            return {"success": False, "returncode": -1, "stdout": "", "stderr": str(e)}

    @classmethod
    def check_rule_exists(cls, action: str, port: int, proto: str = "tcp") -> bool:
        """Check if an iptables rule already exists to avoid duplicates."""
        res = cls._run_args([
            "iptables", "-C", "INPUT", "-p", proto,
            "--dport", str(port), "-j", action
        ])
        return res["success"]

    @classmethod
    def apply_iptables_rule(cls, action: str, port: int, proto: str = "tcp",
                            source_ip: Optional[str] = None) -> dict:
        """Apply an iptables rule. Returns structured result."""
        # Check for duplicate
        if cls.check_rule_exists(action, port, proto):
            return {
                "success": True,
                "duplicate": True,
                "stdout": f"Rule already exists: {action} {proto} dpt:{port}",
                "stderr": ""
            }

        args = ["iptables", "-A", "INPUT", "-p", proto, "--dport", str(port)]
        if source_ip:
            args.extend(["-s", source_ip])
        args.extend(["-j", action])

        logger.info(f"Executing: {' '.join(args)}")
        result = cls._run_args(args)
        result["duplicate"] = False
        return result

    @classmethod
    def remove_iptables_rule(cls, action: str, port: int, proto: str = "tcp",
                             source_ip: Optional[str] = None) -> dict:
        """Remove an iptables rule."""
        args = ["iptables", "-D", "INPUT", "-p", proto, "--dport", str(port)]
        if source_ip:
            args.extend(["-s", source_ip])
        args.extend(["-j", action])

        logger.info(f"Removing: {' '.join(args)}")
        return cls._run_args(args)

    @classmethod
    def apply_tc_bandwidth_limit(cls, interface: str, rate_mbps: int,
                                 latency_ms: int = 20) -> dict:
        """Apply traffic shaping with tc qdisc tbf."""
        burst_kbytes = max(15, int(rate_mbps * 1.5))
        args = [
            "tc", "qdisc", "add", "dev", interface, "root", "tbf",
            f"rate", f"{rate_mbps}mbit",
            f"burst", f"{burst_kbytes}k",
            f"latency", f"{latency_ms}ms"
        ]
        logger.info(f"Executing: {' '.join(args)}")
        return cls._run_args(args)

    @classmethod
    def list_iptables_rules(cls) -> str:
        """List iptables INPUT chain rules."""
        res = cls._run_args(["iptables", "-L", "INPUT", "-v", "-n", "--line-numbers"])
        return res["stdout"] if res["success"] else res["stderr"]

    @classmethod
    def list_listening_ports(cls) -> str:
        """List TCP listening sockets using ss."""
        res = cls._run_args(["ss", "-tlnp"])
        if res["success"]:
            return res["stdout"]
        # Fallback to netstat
        res2 = cls._run_args(["netstat", "-tlnp"])
        return res2["stdout"] if res2["success"] else res2["stderr"]
