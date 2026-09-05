import pytest
from server import validate_firewall_policy


def test_valid_arbitrary_port():
    """Arbitrary port 9999 must pass policy validation."""
    assert validate_firewall_policy("DROP", 9999, "tcp") is True
    assert validate_firewall_policy("ACCEPT", 8080, "tcp") is True
    assert validate_firewall_policy("REJECT", 443, "tcp") is True


def test_protected_ports():
    """Protected ports 22, 53, 5000 must raise ValueError."""
    with pytest.raises(ValueError, match="PROTECTED"):
        validate_firewall_policy("DROP", 22)

    with pytest.raises(ValueError, match="PROTECTED"):
        validate_firewall_policy("DROP", 53)

    with pytest.raises(ValueError, match="PROTECTED"):
        validate_firewall_policy("DROP", 5000)


def test_invalid_port_range():
    """Ports outside 1-65535 must raise ValueError."""
    with pytest.raises(ValueError, match="Invalid port"):
        validate_firewall_policy("DROP", 0)

    with pytest.raises(ValueError, match="Invalid port"):
        validate_firewall_policy("DROP", 70000)


def test_invalid_action():
    """Invalid actions must raise ValueError."""
    with pytest.raises(ValueError, match="Action"):
        validate_firewall_policy("DISABLE", 8080)


def test_invalid_protocol():
    """Non tcp/udp protocols must raise ValueError."""
    with pytest.raises(ValueError, match="Protocol"):
        validate_firewall_policy("ACCEPT", 8080, protocol="icmp")


def test_source_ip_validation():
    """Valid source IPs pass; invalid ones raise ValueError."""
    assert validate_firewall_policy("ACCEPT", 8080, "tcp", source_ip="192.168.1.50") is True

    with pytest.raises(ValueError, match="Invalid source IP"):
        validate_firewall_policy("ACCEPT", 8080, "tcp", source_ip="999.999.999.999")
