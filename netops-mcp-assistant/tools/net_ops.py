import subprocess
import shlex
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NetOps")

class NetworkOps:
    @staticmethod
    def run_cmd(cmd_str: str) -> dict:
        args = shlex.split(cmd_str)
        try:
            result = subprocess.run(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
            )
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip()
            }
        except Exception as e:
            return {"success": False, "returncode": -1, "stdout": "", "stderr": str(e)}

    @classmethod
    def apply_iptables_rule(cls, action: str, port: int, proto: str = "tcp", source_ip: str = None) -> dict:
        cmd = f"iptables -A INPUT -p {proto} --dport {port}"
        if source_ip:
            cmd += f" -s {source_ip}"
        cmd += f" -j {action}"
        logger.info(f"Executing Firewall Command: {cmd}")
        return cls.run_cmd(cmd)

    @classmethod
    def apply_tc_bandwidth_limit(cls, interface: str, rate_mbps: int, latency_ms: int = 20) -> dict:
        burst_kbytes = max(15, int(rate_mbps * 1.5))
        cmd = (f"tc qdisc add dev {interface} root tbf "
               f"rate {rate_mbps}mbit burst {burst_kbytes}k latency {latency_ms}ms")
        logger.info(f"Executing Bandwidth Command: {cmd}")
        return cls.run_cmd(cmd)

    @classmethod
    def list_iptables_rules(cls) -> str:
        res = cls.run_cmd("iptables -L INPUT -v -n --line-numbers")
        return res["stdout"] if res["success"] else res["stderr"]
