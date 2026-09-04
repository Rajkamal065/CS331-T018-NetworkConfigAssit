import pytest
from mcp_client import MCPClient


@pytest.fixture(scope="module")
def mcp_client():
    client = MCPClient()
    client.connect()
    yield client
    client.close()


def test_mcp_tool_discovery(mcp_client):
    """Verify that MCP client discovers all 4 tools exposed by FastMCP server."""
    tools = mcp_client.list_tools()
    tool_names = [t["name"] for t in tools]
    assert "configure_firewall" in tool_names
    assert "set_bandwidth_limit" in tool_names
    assert "run_diagnostics" in tool_names
    assert "list_firewall_rules" in tool_names


def test_mcp_protected_port_rejection(mcp_client):
    """Verify that MCP client call to configure_firewall with port 22 returns policy rejection."""
    res = mcp_client.call_tool(
        "configure_firewall",
        {"action": "DROP", "port": 22}
    )
    assert "POLICY REJECTION" in res
    assert "PROTECTED" in res


def test_mcp_protected_interface_rejection(mcp_client):
    """Verify that MCP client call to set_bandwidth_limit on eth0 returns policy rejection."""
    res = mcp_client.call_tool(
        "set_bandwidth_limit",
        {"interface": "eth0", "rate_mbps": 10}
    )
    assert "POLICY REJECTION" in res
    assert "PROTECTED" in res


def test_mcp_run_diagnostics_ping(mcp_client):
    """Verify that MCP client call to run_diagnostics on 127.0.0.1 succeeds."""
    res = mcp_client.call_tool(
        "run_diagnostics",
        {"target_ip": "127.0.0.1", "mode": "ping"}
    )
    assert "Ping Result" in res
    assert "127.0.0.1" in res
