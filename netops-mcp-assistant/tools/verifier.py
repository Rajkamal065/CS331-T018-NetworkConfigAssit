import re
import json
from tools.net_ops import NetworkOps

class DiagnosticVerifier:
    @staticmethod
    def verify_connectivity(target_ip: str, count: int = 4) -> dict:
        res = NetworkOps.run_cmd(f"ping -c {count} {target_ip}")
        if not res["success"]:
            return {"status": "FAIL", "packet_loss": 100.0, "avg_rtt_ms": 0.0}
        loss_match = re.search(r'(\d+)% packet loss', res["stdout"])
        rtt_match = re.search(r'rtt min/avg/max/mdev = [\d\.]+/([\d\.]+)/', res["stdout"])
        loss = float(loss_match.group(1)) if loss_match else 0.0
        avg_rtt = float(rtt_match.group(1)) if rtt_match else 0.0
        return {
            "status": "PASS" if loss == 0.0 else "DEGRADED",
            "packet_loss": loss,
            "avg_rtt_ms": avg_rtt
        }

    @staticmethod
    def run_bandwidth_test(server_ip: str) -> dict:
        res = NetworkOps.run_cmd(f"iperf3 -c {server_ip} -J")
        if not res["success"]:
            return {"status": "FAIL", "throughput_mbps": 0.0}
        try:
            data = json.loads(res["stdout"])
            bps = data["end"]["sum_sent"]["bits_per_second"]
            return {"status": "PASS", "throughput_mbps": round(bps / 1e6, 2)}
        except Exception:
            return {"status": "PARSING_ERROR", "throughput_mbps": 0.0}
