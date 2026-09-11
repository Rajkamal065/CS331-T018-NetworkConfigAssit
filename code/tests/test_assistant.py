import pytest
import json
from server import configure_firewall, set_bandwidth_limit, run_diagnostics


def test_protected_port_ssh():
    """SSH port 22 must never be blocked."""
    result = configure_firewall(action="DROP", port=22)
    assert "POLICY_REJECTION" in result or "POLICY REJECTION" in result
    assert "PROTECTED" in result


def test_protected_port_dns():
    """DNS port 53 must never be blocked."""
    result = configure_firewall(action="DROP", port=53)
    assert "POLICY_REJECTION" in result or "POLICY REJECTION" in result


def test_arbitrary_port_9999_allowed_by_policy():
    """Port 9999 must not be rejected by policy (v2.0 allows arbitrary ports)."""
    result = configure_firewall(action="DROP", port=9999)
    # Result should either be SUCCESS, DUPLICATE, or EXECUTION_FAILURE (on non-root/non-Linux), but NOT POLICY_REJECTION
    assert "POLICY_REJECTION" not in result
    assert "POLICY REJECTION" not in result


def test_invalid_action():
    """Unknown iptables actions must be rejected."""
    result = configure_firewall(action="DESTROY", port=8080)
    assert "POLICY_REJECTION" in result or "POLICY REJECTION" in result


def test_bandwidth_too_high():
    """Bandwidth above 100 Mbps must be rejected."""
    result = set_bandwidth_limit(interface="eth0", rate_mbps=500)
    assert "POLICY_REJECTION" in result or "POLICY REJECTION" in result


def test_bandwidth_too_low():
    """Bandwidth below 1 Mbps must be rejected."""
    result = set_bandwidth_limit(interface="eth0", rate_mbps=0)
    assert "POLICY_REJECTION" in result or "POLICY REJECTION" in result


def test_protected_interface_eth0():
    """eth0 interface must never be modified by bandwidth limits."""
    result = set_bandwidth_limit(interface="eth0", rate_mbps=10)
    assert "POLICY_REJECTION" in result or "POLICY REJECTION" in result
    assert "PROTECTED" in result


def test_invalid_diagnostic_mode():
    """Invalid diagnostic mode must return error."""
    result = run_diagnostics(target_ip="127.0.0.1", mode="traceroute")
    assert "Invalid" in result or "ERROR" in result


def test_ping_localhost():
    """Ping localhost should return diagnostic packet loss info."""
    result = run_diagnostics(target_ip="127.0.0.1", mode="ping")
    assert "127.0.0.1" in result
    assert "status" in result.lower() or "ping result" in result.lower()
