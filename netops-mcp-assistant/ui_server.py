"""
NetOps MCP Assistant — UI Bridge Server
A FastAPI server that serves the Copilot-like UI and streams tool activity via SSE.
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import AsyncGenerator

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# ── Path setup so tools imports work ──────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from tools.net_ops import NetworkOps
from tools.verifier import DiagnosticVerifier

app = FastAPI(title="NetOps MCP Assistant")

# Mount static files
static_dir = ROOT / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── Load Policies ──────────────────────────────────────────────────────────────
POLICY_PATH = ROOT / "rules" / "policies.yaml"
with open(POLICY_PATH) as f:
    POLICIES = yaml.safe_load(f)


def validate_firewall_policy(action: str, port: int):
    sec = POLICIES["security_policy"]
    if port in sec["protected_ports"]:
        raise ValueError(f"Port {port} is PROTECTED by security policy (prevents lockouts).")
    if action not in sec["allowed_actions"]:
        raise ValueError(f"Action '{action}' is not permitted. Allowed: {sec['allowed_actions']}")
    return True


# ── Command Parser ─────────────────────────────────────────────────────────────
def parse_command(message: str) -> dict:
    """
    Rule-based parser: maps natural language to a structured tool call.
    Returns: { intent, params } or { intent: 'unknown' }
    """
    msg = message.lower().strip()

    # ── LIST RULES ─────────────────────────────────────────────────────────────
    if re.search(r"\b(list|show|display|get)\b.*\b(rule|firewall|iptables)\b", msg) or \
       re.search(r"\b(firewall|iptables)\b.*\b(list|show|rules?)\b", msg) or \
       msg in ("list rules", "show rules", "firewall rules", "rules"):
        return {"intent": "list_rules", "params": {}}

    # ── DIAGNOSTICS ────────────────────────────────────────────────────────────
    diag_match = re.search(
        r"\b(ping|test|check|diagnose|diagnostic|reachability|bandwidth|iperf)\b"
        r".*?(\d{1,3}(?:\.\d{1,3}){3}|localhost|127\.0\.0\.1)?",
        msg
    )
    if diag_match:
        target = diag_match.group(2) or "127.0.0.1"
        if target == "localhost":
            target = "127.0.0.1"
        mode = "iperf3" if re.search(r"\b(iperf|bandwidth|throughput|speed)\b", msg) else "ping"
        return {"intent": "diagnostics", "params": {"target_ip": target, "mode": mode}}

    # ── BANDWIDTH LIMIT ────────────────────────────────────────────────────────
    bw_match = re.search(
        r"\b(limit|throttle|set|cap|restrict)\b.*\b(bandwidth|speed|rate|bw)\b"
        r".*?(\d+)\s*(mb|mbps|mbit|m)?", msg
    ) or re.search(
        r"\b(bandwidth|speed|rate)\b.*?(\d+)\s*(mb|mbps|mbit|m)?", msg
    )
    if bw_match:
        groups = bw_match.groups()
        rate = next((int(g) for g in groups if g and g.isdigit()), None)
        iface_match = re.search(r"\b(eth\d+|ens\d+|eno\d+|enp\d+s\d+|lo|wlan\d+)\b", msg)
        iface = iface_match.group(1) if iface_match else "eth0"
        if rate:
            return {"intent": "bandwidth", "params": {"interface": iface, "rate_mbps": rate}}

    # ── FIREWALL ───────────────────────────────────────────────────────────────
    fw_match = re.search(
        r"\b(block|drop|reject|deny|allow|accept|permit|open)\b.*?"
        r"(?:port\s+)?(\d{2,5})\b", msg
    ) or re.search(
        r"\bport\s+(\d{2,5})\b.*?\b(block|drop|reject|deny|allow|accept|permit|open)\b", msg
    )
    if fw_match:
        groups = fw_match.groups()
        port = next((int(g) for g in groups if g and g.isdigit()), None)
        action_word = next((g for g in groups if g and not g.isdigit()), "")
        block_words = {"block", "drop", "reject", "deny"}
        allow_words = {"allow", "accept", "permit", "open"}
        if action_word.lower() in block_words:
            action = "DROP"
        elif action_word.lower() in allow_words:
            action = "ACCEPT"
        else:
            action = "DROP"
        proto_match = re.search(r"\b(tcp|udp)\b", msg)
        proto = proto_match.group(1) if proto_match else "tcp"
        src_match = re.search(r"\bfrom\s+(\d{1,3}(?:\.\d{1,3}){3})\b", msg)
        src = src_match.group(1) if src_match else ""
        if port:
            return {"intent": "firewall", "params": {
                "action": action, "port": port, "protocol": proto, "source_ip": src
            }}

    return {"intent": "unknown", "params": {}}


# ── SSE Event Helpers ──────────────────────────────────────────────────────────
def sse_event(event_type: str, data: dict) -> str:
    payload = json.dumps({"type": event_type, **data})
    return f"data: {payload}\n\n"


async def yield_with_delay(event: str, delay: float = 0.0):
    await asyncio.sleep(delay)
    return event


# ── Main Chat Stream Handler ───────────────────────────────────────────────────
async def process_command(message: str) -> AsyncGenerator[str, None]:
    yield sse_event("activity", {
        "icon": "🧠",
        "status": "thinking",
        "text": "Parsing your command...",
        "detail": message
    })
    await asyncio.sleep(0.4)

    parsed = parse_command(message)
    intent = parsed["intent"]
    params = parsed["params"]

    if intent == "unknown":
        yield sse_event("activity", {
            "icon": "❓",
            "status": "error",
            "text": "Command not recognized",
            "detail": "Try: 'block port 8080', 'limit bandwidth to 10 mbps on eth0', 'ping 127.0.0.1', 'list firewall rules'"
        })
        yield sse_event("result", {
            "success": False,
            "message": "I couldn't understand that command.",
            "suggestion": "Try: **Block port 8080**, **Limit bandwidth to 10 Mbps on eth0**, **Ping 127.0.0.1**, **List firewall rules**"
        })
        return

    # ── Show parsed intent ────────────────────────────────────────────────────
    yield sse_event("activity", {
        "icon": "🔍",
        "status": "success",
        "text": f"Intent identified: `{intent}`",
        "detail": json.dumps(params)
    })
    await asyncio.sleep(0.3)

    # ── FIREWALL ──────────────────────────────────────────────────────────────
    if intent == "firewall":
        action = params["action"]
        port = params["port"]
        protocol = params["protocol"]
        source_ip = params.get("source_ip", "")

        yield sse_event("activity", {
            "icon": "🛡️",
            "status": "thinking",
            "text": "Validating against security policy...",
            "detail": f"Checking port {port} — protected ports: 22, 53, 5000"
        })
        await asyncio.sleep(0.5)

        try:
            validate_firewall_policy(action, port)
        except ValueError as e:
            yield sse_event("activity", {
                "icon": "🚫",
                "status": "error",
                "text": "Policy REJECTED",
                "detail": str(e)
            })
            yield sse_event("result", {"success": False, "message": f"**Policy Rejection:** {e}"})
            return

        yield sse_event("activity", {
            "icon": "✅",
            "status": "success",
            "text": "Policy check passed",
            "detail": f"Port {port} is not protected. Action {action} is allowed."
        })
        await asyncio.sleep(0.3)

        cmd = f"iptables -A INPUT -p {protocol} --dport {port}"
        if source_ip:
            cmd += f" -s {source_ip}"
        cmd += f" -j {action}"

        yield sse_event("activity", {
            "icon": "⚡",
            "status": "thinking",
            "text": "Executing firewall command...",
            "detail": f"$ {cmd}"
        })
        await asyncio.sleep(0.6)

        res = NetworkOps.apply_iptables_rule(action, port, protocol, source_ip if source_ip else None)

        if res["success"]:
            yield sse_event("activity", {
                "icon": "✅",
                "status": "success",
                "text": "Firewall rule applied successfully",
                "detail": f"iptables rule: {action} port {port}/{protocol}" + (f" from {source_ip}" if source_ip else "")
            })
            yield sse_event("result", {
                "success": True,
                "message": f"**Firewall rule applied.**\n\n`{cmd}`\n\nPort `{port}` is now **{action}**ed on `{protocol}`."
            })
        else:
            yield sse_event("activity", {
                "icon": "❌",
                "status": "error",
                "text": "Firewall command failed",
                "detail": res["stderr"] or "Permission denied — run with sudo or inside Docker"
            })
            yield sse_event("result", {
                "success": False,
                "message": f"**Command failed.**\n\n```\n{res['stderr'] or 'Permission denied. Try: sudo python ui_server.py'}\n```"
            })

    # ── BANDWIDTH ─────────────────────────────────────────────────────────────
    elif intent == "bandwidth":
        interface = params["interface"]
        rate_mbps = params["rate_mbps"]
        bw = POLICIES["bandwidth_policy"]

        yield sse_event("activity", {
            "icon": "🛡️",
            "status": "thinking",
            "text": "Validating bandwidth policy...",
            "detail": f"Allowed range: {bw['min_bandwidth_mbps']}–{bw['max_bandwidth_mbps']} Mbps"
        })
        await asyncio.sleep(0.4)

        if rate_mbps < bw["min_bandwidth_mbps"] or rate_mbps > bw["max_bandwidth_mbps"]:
            yield sse_event("activity", {
                "icon": "🚫",
                "status": "error",
                "text": "Policy REJECTED — out of range",
                "detail": f"{rate_mbps} Mbps is outside [{bw['min_bandwidth_mbps']}–{bw['max_bandwidth_mbps']}] Mbps"
            })
            yield sse_event("result", {
                "success": False,
                "message": f"**Policy Rejection:** `{rate_mbps} Mbps` is outside the allowed range of `{bw['min_bandwidth_mbps']}–{bw['max_bandwidth_mbps']} Mbps`."
            })
            return

        yield sse_event("activity", {
            "icon": "✅",
            "status": "success",
            "text": "Policy check passed",
            "detail": f"{rate_mbps} Mbps is within allowed range."
        })
        await asyncio.sleep(0.3)

        yield sse_event("activity", {
            "icon": "⚡",
            "status": "thinking",
            "text": f"Applying tc bandwidth limit on {interface}...",
            "detail": f"$ tc qdisc add dev {interface} root tbf rate {rate_mbps}mbit burst {max(15, int(rate_mbps*1.5))}k latency 20ms"
        })
        await asyncio.sleep(0.6)

        res = NetworkOps.apply_tc_bandwidth_limit(interface, rate_mbps)

        if res["success"]:
            yield sse_event("activity", {
                "icon": "🌐",
                "status": "thinking",
                "text": "Verifying connectivity post-limit...",
                "detail": "$ ping -c 4 127.0.0.1"
            })
            await asyncio.sleep(0.3)
            diag = DiagnosticVerifier.verify_connectivity("127.0.0.1")
            yield sse_event("activity", {
                "icon": "✅",
                "status": "success",
                "text": f"Bandwidth limited to {rate_mbps} Mbps | Connectivity: {diag['status']}",
                "detail": f"Loss: {diag['packet_loss']}% | RTT: {diag['avg_rtt_ms']}ms"
            })
            yield sse_event("result", {
                "success": True,
                "message": f"**Bandwidth limited to `{rate_mbps} Mbps`** on `{interface}`.\n\n| Metric | Value |\n|--------|-------|\n| Status | {diag['status']} |\n| Packet Loss | {diag['packet_loss']}% |\n| Avg RTT | {diag['avg_rtt_ms']} ms |"
            })
        else:
            yield sse_event("activity", {
                "icon": "❌",
                "status": "error",
                "text": "tc command failed",
                "detail": res["stderr"] or "Permission denied — try sudo or Docker"
            })
            yield sse_event("result", {
                "success": False,
                "message": f"**Command failed.**\n\n```\n{res['stderr'] or 'Permission denied. Run with sudo or in Docker.'}\n```"
            })

    # ── DIAGNOSTICS ───────────────────────────────────────────────────────────
    elif intent == "diagnostics":
        target_ip = params["target_ip"]
        mode = params["mode"]

        yield sse_event("activity", {
            "icon": "🌐",
            "status": "thinking",
            "text": f"Running {mode} diagnostics to {target_ip}...",
            "detail": f"$ {'ping -c 4' if mode == 'ping' else 'iperf3 -c'} {target_ip}"
        })
        await asyncio.sleep(0.5)

        if mode == "ping":
            res = DiagnosticVerifier.verify_connectivity(target_ip)
            status_icon = "✅" if res["status"] == "PASS" else "⚠️" if res["status"] == "DEGRADED" else "❌"
            yield sse_event("activity", {
                "icon": status_icon,
                "status": "success" if res["status"] == "PASS" else "error",
                "text": f"Ping {target_ip} → {res['status']}",
                "detail": f"Packet loss: {res['packet_loss']}% | Avg RTT: {res['avg_rtt_ms']}ms"
            })
            yield sse_event("result", {
                "success": res["status"] == "PASS",
                "message": f"**Ping Results for `{target_ip}`**\n\n| Metric | Value |\n|--------|-------|\n| Status | {status_icon} {res['status']} |\n| Packet Loss | {res['packet_loss']}% |\n| Avg RTT | {res['avg_rtt_ms']} ms |"
            })
        else:
            res = DiagnosticVerifier.run_bandwidth_test(target_ip)
            yield sse_event("activity", {
                "icon": "✅" if res["status"] == "PASS" else "❌",
                "status": "success" if res["status"] == "PASS" else "error",
                "text": f"iperf3 → {res['status']} | Throughput: {res['throughput_mbps']} Mbps",
                "detail": f"Target: {target_ip}"
            })
            yield sse_event("result", {
                "success": res["status"] == "PASS",
                "message": f"**iperf3 Results for `{target_ip}`**\n\n| Metric | Value |\n|--------|-------|\n| Status | {res['status']} |\n| Throughput | {res['throughput_mbps']} Mbps |"
            })

    # ── LIST RULES ────────────────────────────────────────────────────────────
    elif intent == "list_rules":
        yield sse_event("activity", {
            "icon": "📋",
            "status": "thinking",
            "text": "Fetching active iptables rules...",
            "detail": "$ iptables -L INPUT -v -n --line-numbers"
        })
        await asyncio.sleep(0.5)

        rules = NetworkOps.list_iptables_rules()
        if rules:
            yield sse_event("activity", {
                "icon": "✅",
                "status": "success",
                "text": "Rules retrieved",
                "detail": f"{len(rules.splitlines())} lines returned"
            })
            yield sse_event("result", {
                "success": True,
                "message": f"**Active Firewall Rules (INPUT chain)**\n\n```\n{rules}\n```"
            })
        else:
            yield sse_event("activity", {
                "icon": "ℹ️",
                "status": "success",
                "text": "No active rules found",
                "detail": "INPUT chain is empty or iptables not available"
            })
            yield sse_event("result", {
                "success": True,
                "message": "**No active firewall rules found** in the INPUT chain."
            })

    yield sse_event("done", {"text": "Done"})


# ── API Routes ─────────────────────────────────────────────────────────────────
@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return {"error": "Empty message"}

    async def stream():
        async for event in process_command(message):
            yield event

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = static_dir / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>NetOps MCP Assistant</h1><p>Static files not found.</p>")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "NetOps MCP Assistant"}


if __name__ == "__main__":
    import uvicorn
    import logging
    logging.basicConfig(level=logging.INFO)
    print("\n🚀 NetOps MCP Assistant UI starting...")
    print("   Open: http://localhost:8000\n")
    uvicorn.run("ui_server:app", host="0.0.0.0", port=8000, reload=True)
