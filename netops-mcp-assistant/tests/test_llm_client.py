import pytest
from llm_client import LLMClient, MCP_TOOLS_SCHEMA


def test_tool_schemas_registered():
    """Verify tool definitions are correctly defined for LLM function calling."""
    tool_names = [t["function"]["name"] for t in MCP_TOOLS_SCHEMA]
    assert "configure_firewall" in tool_names
    assert "set_bandwidth_limit" in tool_names
    assert "run_diagnostics" in tool_names
    assert "list_firewall_rules" in tool_names
    assert "check_listening_ports" in tool_names
    assert "check_port_connectivity" in tool_names


def test_fallback_parser_block():
    """Verify fallback parser correctly maps natural language block command to tool call."""
    client = LLMClient()
    res = client._fallback_parse("Block port 9999 TCP with DROP")
    assert res["type"] == "tool_call"
    assert res["tool"] == "configure_firewall"
    assert res["arguments"]["port"] == 9999
    assert res["arguments"]["action"] == "DROP"


def test_fallback_parser_allow():
    """Verify fallback parser correctly maps natural language allow command."""
    client = LLMClient()
    res = client._fallback_parse("Open port 8080")
    assert res["type"] == "tool_call"
    assert res["tool"] == "configure_firewall"
    assert res["arguments"]["port"] == 8080
    assert res["arguments"]["action"] == "ACCEPT"


def test_fallback_parser_bandwidth():
    """Verify fallback parser correctly maps bandwidth limit command."""
    client = LLMClient()
    res = client._fallback_parse("Limit bandwidth on eth1 to 20 Mbps")
    assert res["type"] == "tool_call"
    assert res["tool"] == "set_bandwidth_limit"
    assert res["arguments"]["interface"] == "eth1"
    assert res["arguments"]["rate_mbps"] == 20


def test_fallback_parser_diagnostic():
    """Verify fallback parser correctly maps ping command."""
    client = LLMClient()
    res = client._fallback_parse("Ping 192.168.1.1 to check latency")
    assert res["type"] == "tool_call"
    assert res["tool"] == "run_diagnostics"
    assert res["arguments"]["target_ip"] == "192.168.1.1"


def test_fallback_parser_list_rules():
    """Verify fallback parser maps list rules query."""
    client = LLMClient()
    res = client._fallback_parse("Show active firewall rules")
    assert res["type"] == "tool_call"
    assert res["tool"] == "list_firewall_rules"

    res2 = client._fallback_parse("give me firewall rules")
    assert res2["type"] == "tool_call"
    assert res2["tool"] == "list_firewall_rules"


def test_fallback_parser_ip_block_with_greeting():
    """Verify 'hello block the 8.8.8.8' correctly triggers IP block."""
    client = LLMClient()
    res = client._fallback_parse("hello block the 8.8.8.8")
    assert res["type"] == "tool_call"
    assert res["tool"] == "configure_firewall"
    assert res["arguments"]["action"] == "DROP"
    assert res["arguments"]["source_ip"] == "8.8.8.8"


def test_fallback_parser_bare_block():
    """Verify 'block' alone gives guidance message."""
    client = LLMClient()
    res = client._fallback_parse("block")
    assert res["type"] == "message"
    assert "specify" in res["message"].lower()


def test_fallback_parser_tools_query():
    """Verify 'give me waht tools you can do' returns tool list."""
    client = LLMClient()
    res = client._fallback_parse("give me waht tools you can do")
    assert res["type"] == "message"
    assert "configure_firewall" in res["message"]
    assert "list_firewall_rules" in res["message"]


def test_fallback_parser_listening_ports():
    """Verify 'What ports are currently listening on this machine?' maps to check_listening_ports."""
    client = LLMClient()
    res = client._fallback_parse("What ports are currently listening on this machine?")
    assert res["type"] == "tool_call"
    assert res["tool"] == "check_listening_ports"

