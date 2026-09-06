# NetOps MCP Assistant: Implementation Reference

This document explains how the NetOps MCP Assistant is implemented. For a
clone-and-install guide intended for GitHub users, see
[README_GITHUB.md](README_GITHUB.md).

## Purpose

NetOps MCP Assistant is an AI-assisted network operations tool. A user writes
a natural-language request such as `block port 9999`; the application converts
that request into a structured operation, sends it to an authoritative MCP
server, applies the configured policy, executes the approved Linux command,
and independently verifies the result.

The LLM interprets intent only. It is never allowed to decide whether an
operation is safe.

## System Architecture

```text
Web UI / CLI
	|
	v
NetOpsBridge (assistant.py)
	|                    \
	v                     v
LLMClient             MCPClient
	|                     |
	v                     v
Claude/Groq/       FastMCP server (server.py)
OpenRouter/Ollama       |
						 v
				 Policy validation
						 |
						 v
				   NetworkOps
			 iptables / tc / ss / ping
						 |
						 v
					Verifier
```

## Request Lifecycle

1. `app.py` serves the UI and exposes the local HTTP API.
2. `assistant.py` receives the user message through `NetOpsBridge`.
3. `llm_client.py` asks the configured provider to return a structured MCP
   tool call.
4. `mcp_client.py` starts `server.py` over FastMCP stdio transport and calls
   the selected tool.
5. `server.py` validates the request against `rules/policies.yaml`.
6. `tools/net_ops.py` executes approved commands using argument arrays, never
   `shell=True`.
7. `tools/verifier.py` checks the resulting kernel/network state separately.
8. The UI receives the operation result, policy decision, and verification.

If an LLM is unavailable, the request fails explicitly. The application does
not silently pretend that deterministic pattern matching is AI reasoning.

## Main Components

| File or directory | Responsibility |
|---|---|
| `app.py` | Desktop/web entry point and embedded HTTP server |
| `assistant.py` | Coordinates LLM, MCP, and verification layers |
| `llm_client.py` | Provider abstraction and structured intent interpretation |
| `mcp_client.py` | FastMCP stdio client connection |
| `server.py` | Authoritative MCP tools and policy enforcement |
| `tools/net_ops.py` | Linux network command execution |
| `tools/verifier.py` | Independent state and connectivity verification |
| `rules/policies.yaml` | Protected ports, interfaces, ranges, and protocols |
| `ui/` | HTML, CSS, and JavaScript interface |
| `tests/` | Unit and MCP integration tests |
| `demo/` | Firewall demonstration and validation scripts |
| `Dockerfile` | Image containing Python, Ollama, and network tools |
| `compose.yaml` | Container ports, volumes, capabilities, and health check |
| `docker-entrypoint.sh` | Starts Ollama, pulls the model, and starts `app.py` |

## Security Model

The default policy protects ports `22`, `53`, and `5000`, and protects the
`eth0` and `lo` interfaces from bandwidth changes. Policies are checked inside
the MCP server, after LLM interpretation and before command execution.

The container requires `NET_ADMIN` and `NET_RAW` for network operations. Run
it only in a trusted environment. Docker isolation does not replace the
policy layer or host security controls.

## Supported MCP Tools

The server provides tools for:

- Applying or allowing firewall rules with `iptables`.
- Applying bandwidth limits with `tc`.
- Running `ping` and `iperf3` diagnostics.
- Listing firewall rules and listening ports.
- Checking port connectivity.
- Verifying firewall rules and firewall changes independently.

## LLM Provider Design

The client supports Ollama, Groq, Anthropic Claude, and OpenRouter through the
same provider interface. Ollama is the default Docker provider because it is
local and requires no API key. Provider selection is controlled by `.env`.

The explicit `offline_deterministic_parse()` method exists for tests and
development diagnostics only. It is not an automatic production fallback.

## Development Commands

Run from `netops-mcp-assistant/`:

```bash
python -m pytest tests/ -v
python app.py --web
python assistant.py
python demo/validate_firewall.py
```

The native desktop mode is `python app.py`. The browser mode is
`python app.py --web`; use `--no-browser` when starting it from a container or
server.

## Docker Implementation

The image contains Python 3.11, Ollama, `llama3.1`, and the Linux networking
utilities. On first startup, the entrypoint starts Ollama, waits for its API,
downloads the model if it is not in the `ollama-data` volume, and then starts
the web application on port `5000`.

```bash
docker compose up --build
```

Ports:

- `5000`: web UI
- `8000`: reserved MCP port/documentation compatibility mapping
- `11434`: Ollama API

The `rules/` and `logs/` directories are bind-mounted. The Ollama model is
stored in the named `ollama-data` volume so it is not downloaded on every run.

## Test Coverage

The test suite covers policy validation, protected resources, structured LLM
behavior, MCP tool discovery, diagnostics, and assistant integration. Run the
suite before submitting changes:

```bash
python -m pytest tests/ -v
```