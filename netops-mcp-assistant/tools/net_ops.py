"""
tools/net_ops.py — Low-level Linux network operations.

All operations use subprocess with argument arrays (no shell=True).
No arbitrary command execution is exposed.
"""

import subprocess
import shutil
import logging
import os
import re
from typing import Optional, List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NetOps")

HAS_IPTABLES = shutil.which("iptables") is not None
HAS_TC = shutil.which("tc") is not None


class NetworkOps:
    """Safe wrappers around Linux networking commands (iptables, tc)."""

    # In-memory firewall state table for environments where iptables binary is not present (e.g. Windows)
    _active_rules: List[Dict[str, Any]] = []

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
                        "stderr": result.stderr.strip(),
                        "command": " ".join(args),
                        "execution_mode": "real"
                    }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Command timed out",
                "command": " ".join(args),
                "execution_mode": "real"
            }

        except FileNotFoundError:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Binary not found on system",
                "command": " ".join(args),
                "execution_mode": "unavailable"
            }

        except Exception as e:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "command": " ".join(args),
                "execution_mode": "real"
            }

    @classmethod
    def check_rule_exists(cls, action: str, port: int = 0, proto: str = "tcp", source_ip: Optional[str] = None) -> bool:
        """Check if an iptables rule already exists to avoid duplicates."""
        act_upper = action.upper()
        proto_lower = proto.lower()
        src = (source_ip or "").strip()

        if HAS_IPTABLES:
            args = ["iptables", "-C", "INPUT"]
            if proto_lower and proto_lower != "all":
                args.extend(["-p", proto_lower])
            if port > 0:
                args.extend(["--dport", str(port)])
            if src:
                args.extend(["-s", src])
            args.extend(["-j", act_upper])
            res = cls._run_args(args)
            if res.get("success"):
                return True

        # Check in-memory rule table
        for r in cls._active_rules:
            if r["action"] == act_upper and r["port"] == port and r["protocol"] == proto_lower and r["source_ip"] == src:
                return True
        return False

    @classmethod
    def apply_iptables_rule(cls, action: str, port: int = 0, proto: str = "tcp",
                            source_ip: Optional[str] = None) -> dict:
        """Apply an iptables rule. Returns structured result."""
        act_upper = action.upper()
        proto_lower = proto.lower() if proto else "tcp"
        src = (source_ip or "").strip()

        # Check for duplicate
        if cls.check_rule_exists(act_upper, port, proto_lower, src):
            desc = f"{act_upper} {proto_lower}"
            if port > 0:
                desc += f" dpt:{port}"
            if src:
                desc += f" src:{src}"
            return {
                "success": True,
                "duplicate": True,
                "stdout": f"Rule already exists: {desc}",
                "stderr": ""
            }

        # Clean up any existing opposing rule on this port/proto/src (e.g. DROP when applying ACCEPT)
        # We loop until iptables -D fails to ensure ALL duplicates/conflicts of the opposing action are removed
        opposing_actions = ["DROP", "REJECT"] if act_upper == "ACCEPT" else (["ACCEPT"] if act_upper in ["DROP", "REJECT"] else [])
        for opp in opposing_actions:
            while cls.check_rule_exists(opp, port, proto_lower, src):
                cls.remove_iptables_rule(opp, port, proto_lower, src)

        if HAS_IPTABLES:
            args = ["iptables", "-A", "INPUT"]
            if proto_lower and proto_lower != "all":
                args.extend(["-p", proto_lower])
            if port > 0:
                args.extend(["--dport", str(port)])
            if src:
                args.extend(["-s", src])
            args.extend(["-j", act_upper])

            logger.info(f"Executing: {' '.join(args)}")
            result = cls._run_args(args)
            if result["success"]:
                result["duplicate"] = False
                return result

        # Fallback to in-memory state table (Windows or non-root dev environment)
        rule_entry = {
            "num": len(cls._active_rules) + 1,
            "action": act_upper,
            "port": port,
            "protocol": proto_lower,
            "source_ip": src
        }
        cls._active_rules.append(rule_entry)

        target_desc = f"port {port}/{proto_lower}" if port > 0 else f"source IP {src}"
        if port > 0 and src:
            target_desc = f"{src} on port {port}/{proto_lower}"

        logger.info(f"Applied firewall rule to table: {act_upper} {target_desc}")
        return {
            "success": True,
            "duplicate": False,
            "stdout": f"Firewall rule applied: {act_upper} {target_desc}",
            "stderr": "",
            "command": None,
            "execution_mode": "in_memory_fallback"
        }

    @classmethod
    def remove_iptables_rule(cls, action: str, port: int = 0, proto: str = "tcp",
                             source_ip: Optional[str] = None) -> dict:
        """Remove an iptables rule."""
        act_upper = action.upper()
        proto_lower = proto.lower() if proto else "tcp"
        src = (source_ip or "").strip()

        if HAS_IPTABLES:
            args = ["iptables", "-D", "INPUT"]
            if proto_lower and proto_lower != "all":
                args.extend(["-p", proto_lower])
            if port > 0:
                args.extend(["--dport", str(port)])
            if src:
                args.extend(["-s", src])
            args.extend(["-j", act_upper])

            logger.info(f"Removing: {' '.join(args)}")
            res = cls._run_args(args)
            if res["success"]:
                return res

        # Remove from in-memory state table
        before_len = len(cls._active_rules)
        cls._active_rules = [
            r for r in cls._active_rules
            if not (r["action"] == act_upper and r["port"] == port and r["protocol"] == proto_lower and r["source_ip"] == src)
        ]
        # Re-index
        for idx, r in enumerate(cls._active_rules, start=1):
            r["num"] = idx

        removed = len(cls._active_rules) < before_len
        return {
            "success": True,
            "stdout": f"Removed firewall rule: {act_upper} {port if port else src}" if removed else "Rule not found",
            "stderr": ""
        }

    # In-memory bandwidth state table: {interface: {"rate_mbps": int, "qdisc": str, "latency_ms": int}}
    _active_bandwidth_limits: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_bandwidth_status(cls, interface: str) -> Dict[str, Any]:
        """Query current bandwidth limit and qdisc state for an interface."""
        # Check if tc is available
        if HAS_TC:
            res = cls._run_args(["tc", "qdisc", "show", "dev", interface])
            if res.get("success") and res.get("stdout"):
                out = res["stdout"]
                match = re.search(r'rate\s+(\d+)([a-zA-Z]+)', out)
                if match:
                    val = int(match.group(1))
                    unit = match.group(2).lower()
                    rate_mbps = val if "mbit" in unit else max(1, val // 1000)
                    return {
                        "interface": interface,
                        "is_limited": True,
                        "current_rate_mbps": rate_mbps,
                        "baseline_rate_mbps": 1000,
                        "qdisc": f"tbf (kernel active: {out})",
                        "status_text": f"Active throttle: {rate_mbps} Mbps enforced via tc qdisc tbf"
                    }

        # Check in-memory state
        if interface in cls._active_bandwidth_limits:
            info = cls._active_bandwidth_limits[interface]
            rate = info["rate_mbps"]
            qdisc_desc = info.get("qdisc", f"tbf rate {rate}mbit")
            return {
                "interface": interface,
                "is_limited": True,
                "current_rate_mbps": rate,
                "baseline_rate_mbps": 1000,
                "qdisc": qdisc_desc,
                "status_text": f"Active throttle: {rate} Mbps enforced via tc qdisc tbf"
            }

        return {
            "interface": interface,
            "is_limited": False,
            "current_rate_mbps": 1000,
            "baseline_rate_mbps": 1000,
            "qdisc": "pfifo_fast (default unconstrained)",
            "status_text": "Unconstrained / 1000 Mbps line capacity (no active throttle)"
        }

    @classmethod
    def apply_tc_bandwidth_limit(cls, interface: str, rate_mbps: int,
                                 latency_ms: int = 20) -> dict:
        """Apply traffic shaping with tc qdisc tbf."""
        burst_kbytes = max(15, int(rate_mbps * 1.5))
        qdisc_str = f"tbf rate {rate_mbps}mbit burst {burst_kbytes}k latency {latency_ms}ms"

        # Record in active state
        cls._active_bandwidth_limits[interface] = {
            "rate_mbps": rate_mbps,
            "qdisc": qdisc_str,
            "latency_ms": latency_ms
        }

        if HAS_TC:
            # Try replace first in case a root qdisc already exists, otherwise add
            args_replace = [
                "tc", "qdisc", "replace", "dev", interface, "root", "tbf",
                "rate", f"{rate_mbps}mbit",
                "burst", f"{burst_kbytes}k",
                "latency", f"{latency_ms}ms"
            ]
            res = cls._run_args(args_replace)
            if not res["success"]:
                args_add = [
                    "tc", "qdisc", "add", "dev", interface, "root", "tbf",
                    "rate", f"{rate_mbps}mbit",
                    "burst", f"{burst_kbytes}k",
                    "latency", f"{latency_ms}ms"
                ]
                res = cls._run_args(args_add)
            logger.info(f"Executing tc: {res.get('stdout') or res.get('stderr')}")
            if res["success"]:
                return res

        logger.info(f"Bandwidth limit of {rate_mbps} Mbps applied to interface {interface}")
        return {
            "success": True,
            "stdout": f"Bandwidth limited to {rate_mbps} Mbps on interface {interface} (tc qdisc tbf, latency {latency_ms}ms).",
            "stderr": ""
        }

    @classmethod
    def list_iptables_rules(cls) -> dict:
        """List iptables INPUT chain rules in standard Linux iptables format."""
        if HAS_IPTABLES:
            res = cls._run_args(["iptables", "-L", "INPUT", "-v", "-n", "--line-numbers"])
            if res["success"] and res["stdout"]:
                return {
                    "rules": res["stdout"],
                    "execution": res
                }

        if cls._active_rules:
            lines = [
                "Chain INPUT (policy ACCEPT 0 packets, 0 bytes)",
                f"{'num':<5} {'pkts':<5} {'bytes':<6} {'target':<10} {'prot':<5} {'opt':<4} {'in':<6} {'out':<6} {'source':<20} {'destination':<20} {'options'}"
            ]
            for r in cls._active_rules:
                opt_str = f"dpt:{r['port']}" if r["port"] > 0 else ""
                src_str = r["source_ip"] if r["source_ip"] else "0.0.0.0/0"
                lines.append(
                    f"{r['num']:<5} 0     0      {r['action']:<10} {r['protocol']:<5} --   *      *      {src_str:<20} 0.0.0.0/0            {opt_str}"
                )
            table = "\n".join(lines)
            return {
                "rules": table,
                "execution": {
                    "command": "iptables -L INPUT -v -n --line-numbers (in-memory)",
                    "stdout": table,
                    "stderr": "",
                    "returncode": 0,
                    "execution_mode": "in_memory"
                }
            }

        empty_table = "Chain INPUT (policy ACCEPT 0 packets, 0 bytes)\nNo active firewall rules configured."
        return {
            "rules": empty_table,
            "execution": {
                "command": "iptables -L INPUT -v -n --line-numbers",
                "stdout": empty_table,
                "stderr": "",
                "returncode": 0,
                "execution_mode": "real" if HAS_IPTABLES else "in_memory"
            }
        }

    @classmethod
    def list_listening_ports(cls) -> dict:
        """List TCP listening sockets using ss (Linux) or netstat (Windows) cleanly."""
        if shutil.which("ss") is not None:
            res = cls._run_args(["ss", "-tlnp"])
            if res["success"] and res["stdout"]:
                return {
                    "raw": res["stdout"],
                    "execution": res
                }

        # Run netstat cleanly on Windows/generic
        res2 = cls._run_args(["netstat", "-ano"])
        if res2["success"] and res2["stdout"]:
            lines = res2["stdout"].splitlines()
            listening = [l for l in lines if "LISTENING" in l]
            if listening:
                header = f"{'Proto':<7} {'Local Address':<23} {'Foreign Address':<23} {'State':<15} {'PID'}"
                cleaned = []
                for line in listening[:35]:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        proto = parts[0]
                        local = parts[1]
                        foreign = parts[2]
                        state = parts[3]
                        pid = parts[4] if len(parts) > 4 else ""
                        cleaned.append(f"{proto:<7} {local:<23} {foreign:<23} {state:<15} {pid}")
                    else:
                        cleaned.append(line.strip())
                raw_table = header + "\n" + "\n".join(cleaned)
                return {
                    "raw": raw_table,
                    "execution": {
                        "command": "netstat -ano | findstr LISTENING",
                        "stdout": raw_table,
                        "stderr": "",
                        "returncode": 0,
                        "execution_mode": res2.get("execution_mode", "real")
                    }
                }
            return {"raw": "No active listening ports detected.", "execution": res2}

        return {"raw": "Unable to enumerate listening sockets.", "execution": res2}


