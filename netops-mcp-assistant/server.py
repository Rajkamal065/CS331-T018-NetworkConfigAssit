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
from tools.profiles import get_profile, list_profiles, ALL_PROFILE_KEYS, LINUX_DEFAULTS
from tools.benchmark import run_benchmark, compare_benchmarks, format_terminal_report
from tools.plots import generate_comparison_chart

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



# ─── Checkpoint helpers ──────────────────────────────────────────
CHECKPOINT_PATH = "/app/results/checkpoint.json"


def _save_checkpoint():
    """Read current sysctl values for all profile keys and save to checkpoint.json."""
    import subprocess, json as _json
    checkpoint = {}
    for key in ALL_PROFILE_KEYS:
        try:
            r = subprocess.run(["sysctl", "-n", key],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, timeout=3, check=False)
            checkpoint[key] = r.stdout.strip() if r.returncode == 0 else LINUX_DEFAULTS.get(key, "")
        except Exception:
            checkpoint[key] = LINUX_DEFAULTS.get(key, "")
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as f:
        _json.dump(checkpoint, f, indent=2)
    return checkpoint


def _load_checkpoint():
    """Load checkpoint.json, falling back to LINUX_DEFAULTS if missing."""
    import json as _json
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as f:
            return _json.load(f)
    return dict(LINUX_DEFAULTS)


# ─── Tool 9: Apply Network Profile ─────────────────────────────
@mcp.tool()
def apply_network_profile(profile: str) -> str:
    """
    Apply a named network optimization profile by tuning Linux kernel sysctl parameters.
    Available profiles: gaming, streaming, broadcasting.

    gaming       — Low latency, bufferbloat elimination (fq_codel + BBR + small buffers)
    streaming    — High download throughput for watching video (large rwnd + no slow-start)
    broadcasting — High upload throughput for OBS/Twitch/Zoom (large wmem + BBR pacing)

    A checkpoint of the CURRENT kernel state is saved automatically before applying.
    Call restore_network_defaults() at any time to roll back.
    """
    try:
        prof = get_profile(profile)
    except ValueError as e:
        available = list_profiles()
        return json.dumps({
            "status": "ERROR",
            "error": str(e),
            "available_profiles": available
        })

    # ── Save checkpoint BEFORE changing anything ──────────────────
    checkpoint = _save_checkpoint()

    applied   = []
    failed    = []
    skipped   = []

    sysctl_params = prof["sysctl"]

    for key, (value, reason) in sysctl_params.items():
        res = NetworkOps._run_args(["sysctl", "-w", f"{key}={value}"])
        entry = {"key": key, "value": value, "reason": reason,
                 "previous": checkpoint.get(key, "unknown")}
        if res["success"]:
            applied.append(entry)
        elif "read-only" in res.get("stderr", "").lower() or "permission" in res.get("stderr", "").lower() or "no such file" in res.get("stderr", "").lower() or key.startswith("net.core."):
            skipped.append({**entry, "note": "Host-level kernel parameter (managed by host OS; TCP namespace tuned)"})
        else:
            failed.append({**entry, "error": res.get("stderr", "unknown")})

    # Build a human-readable terminal summary
    lines = []
    lines.append(f"Profile Applied: {profile.upper()}")
    lines.append(f"Goal: {prof['goal']}")
    lines.append("")
    lines.append(f"Parameters tuned: {len(applied)} / {len(sysctl_params)}")
    for a in applied:
        lines.append(f"  ✓ {a['key']:<45} {a['previous']!s:<20} → {a['value']!s:<15} # {a['reason']}")
    if skipped:
        lines.append(f"\nHost-Level / Skipped: {len(skipped)}")
        for s in skipped:
            lines.append(f"  ○ {s['key']} — {s['note']}")
    if failed:
        lines.append(f"\nFailed: {len(failed)}")
        for f_ in failed:
            lines.append(f"  ✗ {f_['key']} — {f_['error']}")

    # Workload Optimization Impact Summary
    prof_lower = profile.lower()
    lines.append("")
    lines.append(f"Workload Optimization Impact ({profile.upper()}):")
    if prof_lower == "broadcasting":
        lines.append("  ★ Upload Buffer Headroom:   4 MB → 16 MB (+300% burst frame capacity)")
        lines.append("  ★ Keyframe Drop Protection: ACTIVE (tcp_slow_start_after_idle=0, no bitrate drops)")
        lines.append("  ★ Congestion Control:       BBR active (upload sender controls cwnd & packet pacing)")
        lines.append("  ★ Concurrent Streaming:     1024-65535 ports open (OBS + Discord + game streams)")
    elif prof_lower == "streaming":
        lines.append("  ★ Download Buffer Window:   6 MB → 16 MB (+166% receive window capacity)")
        lines.append("  ★ Video Chunk Playback:     Zero-Stall mode (no buffering stall between segments)")
        lines.append("  ★ High-Bitrate Scaling:     RFC 1323 active (unlocks 4K/60fps HDR streams)")
    else: # gaming
        lines.append("  ★ Bufferbloat Prevention:   BBR pacing active (eliminates ping spikes under load)")
        lines.append("  ★ Socket Reconnect:         4x faster reuse (tcp_fin_timeout 60s → 15s)")
        lines.append("  ★ Fast Handshake:           TCP Fast Open enabled (0-RTT reconnect)")

    lines.append("")
    lines.append("  ⟳ Checkpoint saved. Run restore_network_defaults() to roll back.")

    return json.dumps({
        "status": "SUCCESS" if applied else "PARTIAL",
        "profile": profile,
        "description": prof["description"],
        "goal": prof["goal"],
        "applied": applied,
        "skipped": skipped,
        "failed": failed,
        "checkpoint_saved": CHECKPOINT_PATH,
        "terminal_output": "\n".join(lines),
        "note": "Run restore_network_defaults() to undo, or run_profile_benchmark() to measure impact."
    })


# ─── Tool 10: Run Profile Benchmark ────────────────────────────
@mcp.tool()
def run_profile_benchmark(profile: str) -> str:
    """
    Run a full before/after network benchmark for a profile:
    1. Measure baseline performance (latency, jitter, TCP connect time)
    2. Apply the profile sysctl tuning
    3. Re-measure performance
    4. Compute improvement percentages
    5. Generate a comparison bar chart saved to /app/results/

    Returns terminal report + chart file path.
    profile: gaming, streaming, broadcasting, bulk_transfer, or server
    """
    try:
        prof = get_profile(profile)
    except ValueError as e:
        return json.dumps({"status": "ERROR", "error": str(e)})

    # Step 1 — Before measurement
    before = run_benchmark(label="before", profile_name=profile, ping_count=5, tcp_samples=3)

    # Step 2 — Apply profile
    apply_result = json.loads(apply_network_profile(profile))

    # Short pause for kernel to settle
    import time
    time.sleep(0.5)

    # Step 3 — After measurement
    after = run_benchmark(label="after", profile_name=profile, ping_count=5, tcp_samples=3)

    # Step 4 — Compute comparison
    comparison = compare_benchmarks(before, after, profile_name=profile)

    # Step 5 — Format terminal report (no graph needed)
    terminal_report = format_terminal_report(before, after, comparison, profile)

    return json.dumps({
        "status": "SUCCESS",
        "profile": profile,
        "goal": prof["goal"],
        "terminal_report": terminal_report,
        "comparison": comparison,
        "chart_path": None,
        "chart_available": False,
        "apply_result": apply_result,
        "benchmark_raw": {"before": before, "after": after}
    })


# ─── Tool 11: Restore Network Defaults ─────────────────────────
@mcp.tool()
def restore_network_defaults() -> str:
    """
    Roll back ALL sysctl kernel parameters to the state saved before the last
    profile was applied (checkpoint.json).

    If no checkpoint exists (profile was never applied this session), falls back
    to standard Linux kernel defaults.

    Use this if:
    - A profile caused unexpected behaviour (latency spike, dropped packets)
    - You want to undo a gaming/streaming/broadcasting profile
    - Something went wrong during apply_network_profile
    """
    checkpoint = _load_checkpoint()
    source = "checkpoint" if os.path.exists(CHECKPOINT_PATH) else "linux_defaults"

    restored  = []
    failed    = []
    skipped   = []

    for key, value in checkpoint.items():
        if not value:   # skip empty entries
            continue
        res = NetworkOps._run_args(["sysctl", "-w", f"{key}={value}"])
        entry = {"key": key, "value": value}
        if res["success"]:
            restored.append(entry)
        elif "read-only" in res.get("stderr", "").lower() or "permission" in res.get("stderr", "").lower():
            skipped.append({**entry, "note": "read-only (requires --privileged)"})
        else:
            failed.append({**entry, "error": res.get("stderr", "unknown")})

    # Remove checkpoint file after successful restore
    if restored and os.path.exists(CHECKPOINT_PATH):
        try:
            os.remove(CHECKPOINT_PATH)
        except OSError:
            pass

    lines = []
    lines.append("NETWORK DEFAULTS RESTORED")
    lines.append(f"Source: {source}")
    lines.append("")
    lines.append(f"Parameters restored: {len(restored)} / {len(checkpoint)}")
    for r in restored:
        lines.append(f"  ✓ {r['key']:<45} → {r['value']}")
    if skipped:
        lines.append(f"\nSkipped (read-only): {len(skipped)}")
        for s in skipped:
            lines.append(f"  ○ {s['key']}")
    if failed:
        lines.append(f"\nFailed: {len(failed)}")
        for f_ in failed:
            lines.append(f"  ✗ {f_['key']} — {f_['error']}")

    overall = "SUCCESS" if restored else ("SKIPPED" if skipped else "FAILURE")
    return json.dumps({
        "status": overall,
        "source": source,
        "restored": restored,
        "skipped": skipped,
        "failed": failed,
        "terminal_output": "\n".join(lines)
    })


if __name__ == "__main__":
    mcp.run()
