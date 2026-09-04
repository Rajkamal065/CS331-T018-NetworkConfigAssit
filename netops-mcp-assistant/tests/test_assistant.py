import pytest
from server import configure_firewall, set_bandwidth_limit, run_diagnostics

def test_protected_port_ssh():
    """SSH port 22 must never be blocked."""
    result = configure_firewall(action="DROP", port=22)
    assert "POLICY REJECTION" in result
    assert "PROTECTED" in result

def test_protected_port_dns():
    """DNS port 53 must never be blocked."""
    result = configure_firewall(action="DROP", port=53)
    assert "POLICY REJECTION" in result

def test_invalid_action():
    """Unknown iptables actions must be rejected."""
    result = configure_firewall(action="DESTROY", port=8080)
    assert "POLICY REJECTION" in result

def test_bandwidth_too_high():
    """Bandwidth above 100 Mbps must be rejected."""
    result = set_bandwidth_limit(interface="eth0", rate_mbps=500)
    assert "POLICY REJECTION" in result

def test_bandwidth_too_low():
    """Bandwidth below 1 Mbps must be rejected."""
    result = set_bandwidth_limit(interface="eth0", rate_mbps=0)
    assert "POLICY REJECTION" in result

def test_protected_interface_eth0():
    """eth0 interface must never be modified by bandwidth limits."""
    result = set_bandwidth_limit(interface="eth0", rate_mbps=10)
    assert "POLICY REJECTION" in result
    assert "PROTECTED" in result

def test_invalid_diagnostic_mode():
    """Invalid diagnostic mode must return error."""
    result = run_diagnostics(target_ip="127.0.0.1", mode="traceroute")
    assert "Invalid mode" in result

def test_ping_localhost():
    """Ping localhost should always pass."""
    result = run_diagnostics(target_ip="127.0.0.1", mode="ping")
    assert "PASS" in result or "Loss=0.0%" in result
