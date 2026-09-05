"""
setup_claude_desktop.py — Automatically link NetOps MCP Server to Claude Desktop.

Identical to NetMCP setup:
1. Detects Python executable path
2. Locates Claude Desktop config directory (%APPDATA%\\Claude)
3. Merges/installs the 'netops' MCP server entry into claude_desktop_config.json
"""

import os
import sys
import json
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
SERVER_PY = os.path.join(ROOT, "server.py")
PYTHON_EXE = sys.executable

CLAUDE_DIR = os.path.expandvars(r"%APPDATA%\Claude")
CLAUDE_CONFIG = os.path.join(CLAUDE_DIR, "claude_desktop_config.json")


def install_config():
    print("=" * 60)
    print("  NetOps MCP Assistant — Claude Desktop Configuration Setup")
    print("=" * 60)
    print(f"Python Executable : {PYTHON_EXE}")
    print(f"FastMCP Server    : {SERVER_PY}")
    print(f"Target Config     : {CLAUDE_CONFIG}")
    print()

    os.makedirs(CLAUDE_DIR, exist_ok=True)

    config_data = {}
    if os.path.isfile(CLAUDE_CONFIG):
        try:
            with open(CLAUDE_CONFIG, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            print(f"Loaded existing Claude Desktop configuration.")
        except Exception as e:
            print(f"Warning: Could not parse existing config ({e}), creating backup...")
            shutil.copy2(CLAUDE_CONFIG, CLAUDE_CONFIG + ".bak")
            config_data = {}

    if "mcpServers" not in config_data:
        config_data["mcpServers"] = {}

    config_data["mcpServers"]["netops"] = {
        "command": PYTHON_EXE,
        "args": [SERVER_PY]
    }

    with open(CLAUDE_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    print("\nSUCCESS: 'netops' MCP Server successfully linked to Claude Desktop!")
    print(json.dumps(config_data["mcpServers"]["netops"], indent=2))
    print("\nWhen you open Claude Desktop, the hammer/tools icon will show NetOps tools:")
    print("- configure_firewall")
    print("- list_firewall_rules")
    print("- check_listening_ports")
    print("- set_bandwidth_limit")
    print("- run_diagnostics")
    print("- check_port_connectivity")
    print("- validate_firewall_change")
    print("=" * 60)


if __name__ == "__main__":
    install_config()
