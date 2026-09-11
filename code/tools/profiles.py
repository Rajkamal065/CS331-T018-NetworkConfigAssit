"""
tools/profiles.py — Network Optimization Profiles.

Each profile defines a set of sysctl kernel parameters tuned
for a specific workload. Simple, safe, and easily reversible.

Profiles:
  gaming       — Low latency, bufferbloat elimination
  streaming    — High sustained download throughput (watching)
  broadcasting — High upload throughput (OBS, Twitch, Zoom upload)

Fallback / Rollback:
  A checkpoint of the current kernel state is saved to
  /app/results/checkpoint.json before every profile application.
  Call restore_network_defaults() to revert to it.
"""

from typing import Dict, Any

# ─── Profile Definitions ─────────────────────────────────────────────────────
# Each key maps to a sysctl parameter name.
# Each value is (value_to_set, human_explanation).

PROFILES: Dict[str, Dict[str, Any]] = {

    "gaming": {
        "description": "Low-latency gaming profile. Eliminates bufferbloat so your "
                       "game packets are served immediately even under background load.",
        "goal": "Minimize latency (ping) and jitter",
        "sysctl": {
            # BBR measures real bandwidth instead of reacting to loss → stable ping
            "net.ipv4.tcp_congestion_control":  ("bbr",       "BBR congestion control — stable ping under packet loss"),
            # fq_codel keeps per-flow queues so game packets bypass bulk-download queues
            "net.core.default_qdisc":           ("fq_codel",  "FQ-CoDel — fair queuing, bufferbloat killer"),
            # Tell kernel: do NOT batch; flush each game packet to NIC immediately
            "net.ipv4.tcp_low_latency":         ("1",         "TCP Low Latency mode — immediate NIC flush"),
            # Small buffers drain instantly (large buffers add milliseconds of queue delay)
            "net.core.rmem_max":                ("4194304",   "4 MB receive buffer — small queues drain fast"),
            "net.core.wmem_max":                ("4194304",   "4 MB send buffer — small queues drain fast"),
            # Fast socket teardown — game servers open/close connections rapidly
            "net.ipv4.tcp_fin_timeout":         ("15",        "15 s FIN timeout — fast socket reuse"),
            # Eliminate 1-RTT overhead for reconnecting to known game servers
            "net.ipv4.tcp_fastopen":            ("3",         "TCP Fast Open — skip 3-way handshake on reconnect"),
        },
    },

    "streaming": {
        "description": "Video streaming (watching) profile. Maximises the TCP receive "
                       "window so CDN servers can deliver video chunks at full speed, "
                       "keeping your player locked at the highest resolution.",
        "goal": "Maximise download throughput and prevent chunk-download stalls",
        "sysctl": {
            # Receiver-side: CDN sender controls cwnd, so receiver stays on cubic default
            "net.ipv4.tcp_congestion_control":    ("cubic",         "CUBIC (default) — as receiver, CDN sender controls transmission cwnd"),
            # 16 MB receive buffer — lets CDN servers fill your window with large chunks
            "net.core.rmem_max":                  ("16777216",      "16 MB receive buffer — allows large rwnd advertisement"),
            "net.core.wmem_max":                  ("16777216",      "16 MB send buffer (for ACK-heavy connections)"),
            "net.ipv4.tcp_rmem":                  ("4096 87380 16777216", "TCP receive autotuning: min/default/max (up to 16 MB)"),
            "net.ipv4.tcp_wmem":                  ("4096 65536 16777216", "TCP send autotuning: min/default/max"),
            # CRITICAL: prevents TCP from resetting cwnd to minimum between video chunks
            "net.ipv4.tcp_slow_start_after_idle": ("0",             "Disable slow-start after idle — eliminates buffering stall between chunks"),
            # RFC 1323 — allows rwnd > 64 KB (mandatory for > 12 Mbps on 40 ms RTT)
            "net.ipv4.tcp_window_scaling":        ("1",             "TCP Window Scaling RFC 1323 — unlocks > 64 KB rwnd"),
            # Accurate RTT measurement
            "net.ipv4.tcp_timestamps":            ("1",             "TCP Timestamps — accurate RTT calculation"),
        },
    },

    "broadcasting": {
        "description": "Upload / broadcasting profile for OBS, Twitch, YouTube Live, "
                       "Zoom, or any scenario where YOUR system is sending sustained "
                       "video. BBR + fq paces your upload stream smoothly to prevent "
                       "dropped frames at scene transitions or keyframe bursts.",
        "goal": "Maximise stable upload throughput, prevent OBS dropped frames",
        "sysctl": {
            # YOU are the sender — BBR directly controls your upload congestion window
            "net.ipv4.tcp_congestion_control":    ("bbr",           "BBR — you are the sender, controls upload cwnd"),
            # fq paces your video packets evenly; prevents burst→starve upload pattern
            "net.core.default_qdisc":             ("fq",            "FQ — packet pacing, prevents upload burst spikes"),
            # Large SEND buffer to hold encoded video frames during upload
            "net.core.wmem_max":                  ("16777216",      "16 MB send buffer — holds video frames during upload"),
            "net.ipv4.tcp_wmem":                  ("4096 65536 16777216", "TCP send autotuning for high-bitrate upload"),
            # Moderate receive buffer for incoming ACKs from streaming server
            "net.core.rmem_max":                  ("4194304",       "4 MB receive buffer — for server ACK flow"),
            "net.ipv4.tcp_rmem":                  ("4096 87380 4194304", "TCP receive autotuning for ACKs"),
            # Keyframes cause idle gaps between bursts — without this TCP resets cwnd
            "net.ipv4.tcp_slow_start_after_idle": ("0",             "Disable slow-start after idle — no bitrate drop at scene cuts"),
            # More local ports for concurrent upload + game + Discord streams
            "net.ipv4.ip_local_port_range":       ("1024 65535",    "Expand local ports — support concurrent upload streams"),
            "net.ipv4.tcp_timestamps":            ("1",             "TCP Timestamps — accurate RTT measurement"),
        },
    },
}

# ─── All sysctl keys touched across all profiles ─────────────────────────────
# Used to save a full checkpoint before any profile is applied.
ALL_PROFILE_KEYS = sorted({
    key
    for prof in PROFILES.values()
    for key in prof["sysctl"].keys()
})

# ─── Linux kernel defaults (safe fallback if checkpoint read fails) ───────────
LINUX_DEFAULTS: Dict[str, str] = {
    "net.ipv4.tcp_congestion_control":    "cubic",
    "net.core.default_qdisc":            "pfifo_fast",
    "net.ipv4.tcp_low_latency":          "0",
    "net.core.rmem_max":                 "212992",
    "net.core.wmem_max":                 "212992",
    "net.ipv4.tcp_rmem":                 "4096 131072 6291456",
    "net.ipv4.tcp_wmem":                 "4096 16384 4194304",
    "net.ipv4.tcp_slow_start_after_idle":"1",
    "net.ipv4.tcp_window_scaling":       "1",
    "net.ipv4.tcp_timestamps":           "1",
    "net.ipv4.tcp_fin_timeout":          "60",
    "net.ipv4.tcp_fastopen":             "1",
    "net.ipv4.ip_local_port_range":      "32768 60999",
}


def get_profile(name: str) -> Dict[str, Any]:
    """Return a profile by name (case-insensitive). Raises ValueError if unknown."""
    key = name.lower().strip()
    if key not in PROFILES:
        available = ", ".join(PROFILES.keys())
        raise ValueError(f"Unknown profile '{name}'. Available: {available}")
    return PROFILES[key]


def list_profiles() -> Dict[str, str]:
    """Return a dict of {profile_name: description}."""
    return {k: v["description"] for k, v in PROFILES.items()}
