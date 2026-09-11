# NetOps MCP Assistant — CS331-T018

> **An AI-Powered Autonomous Linux Network Configuration Assistant**  
> **Course:** CS331 — Computer Networks | **Team:** Team T018  

### 📚 Documentation
- 📄 **[CS331 Project Report (PDF)](report/report.pdf)**
- 🏗️ **[System Architecture Specification](ARCHITECTURE.md)**
- 🤖 **[AI Usage Documentation](AI_Used/README.md)**
- 📘 **[Implementation Reference](README.md)**


## What This Project Does

NetOps MCP Assistant lets a network administrator use natural language to:

- **Configure firewall rules** — Block/allow ports and IPs via iptables
- **Apply bandwidth limits** — Traffic shaping via tc qdisc tbf
- **Inspect the system** — Listening ports, active firewall rules, bandwidth state
- **Run network diagnostics** — Ping reachability, iperf3 throughput tests
- **Apply workload profiles** — Tune the Linux kernel for gaming, streaming, broadcasting, bulk transfer, or server workloads
- **Benchmark before/after** — Automated latency/jitter measurements + matplotlib comparison charts saved to `results/`
- **Verify changes** — Independent dual-layer verification that rules took effect

The LLM interprets the request. The FastMCP server remains the policy and execution authority.

### Available Optimization Profiles

| Profile | Goal | Key Parameters |
|:---|:---|:---|
| `gaming` | Minimum latency, bufferbloat elimination | `fq_codel`, BBR, 4 MB buffers, `tcp_low_latency=1` |
| `streaming` | Maximum video download throughput | 16 MB `rmem_max`, `tcp_slow_start_after_idle=0` |
| `broadcasting` | Stable upload for OBS/Twitch/Zoom | 16 MB `wmem_max`, BBR + `fq` pacing |
| `bulk_transfer` | Maximum raw TCP throughput | 256 MB buffers, BBR, max `netdev_budget` |
| `server` | High-concurrency with DDoS protection | SYN cookies, 8192 SYN backlog, fast socket reuse |

**Example prompts:**
- *"Optimize my system for gaming and benchmark it"*
- *"Apply the streaming profile and show me before/after results"*
- *"I'm going live on Twitch, optimize my upload"*

The LLM interprets the request. The FastMCP server remains the policy and execution authority.


## Recommended Installation: Docker

Docker is the easiest option because it bundles Python, Ollama, the Llama model, and Linux networking tools in one environment.

### Requirements

Install:

- Docker Desktop on Windows or macOS, or Docker Engine and Compose on Linux.
- At least 8 GB RAM recommended for `llama3.1`.
- At least 6 GB free disk space for the image and model.
- Internet access for the first image build and model download.

On Windows, start Docker Desktop and wait until `docker ps` works without an error.

### Clone the Repository

```bash
git clone <repository-url>
cd CS331-T018-NetworkConfigAssit/netops-mcp-assistant
```

Replace `<repository-url>` with the GitHub URL for this repository.

### Start the Application

Use the modern Compose command:

```bash
docker compose up --build
```

The first run may take several minutes. The container will:

1. Build the application image.
2. Start Ollama.
3. Download `llama3.1` if it is not cached.
4. Start the web application.

Open [http://localhost:5000](http://localhost:5000) after the startup logs say the application is ready.

### Windows Convenience Script

From the `netops-mcp-assistant` directory:

```bat
run-docker.bat
```

Or build first:

```bat
build-docker.bat
run-docker.bat
```

### Linux or macOS Convenience Script

```bash
bash run-docker.sh
```

## Docker Commands

Stop the application without deleting the model:

```bash
docker compose down
```

View logs:

```bash
docker compose logs -f netops-assistant
```

Run tests in the container:

```bash
docker compose exec netops-assistant python -m pytest tests/ -v
```

Open a shell in the running container:

```bash
docker compose exec netops-assistant /bin/bash
```

Rebuild after code changes:

```bash
docker compose down
docker compose build --no-cache
docker compose up
```

Delete the model cache as well as the container:

```bash
docker compose down -v
```

Use the last command only when you intentionally want Ollama to download the model again.

## Local Python Installation

Use this option for development or when Docker is unavailable. Real firewall and traffic-shaping operations require Linux privileges. Windows is suitable for UI and unit-test development, but `iptables` and `tc` operations require a Linux host, WSL2, or Docker.

### Requirements

- Python 3.11 or newer.
- Git.
- Linux networking tools: `iptables`, `iproute2`, `iputils-ping`, and optionally `iperf3`.
- An LLM provider configured in `.env`.

### Create a Virtual Environment

From `netops-mcp-assistant/`:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Activate it on Windows Command Prompt:

```bat
.venv\Scripts\activate.bat
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

Install Python dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configure an LLM

An LLM is required for natural-language interpretation. The application reports a clear error when no provider is available; it does not silently use a rule parser in production.

### Option A: Ollama

Install Ollama from [ollama.com](https://ollama.com), then run:

```bash
ollama pull llama3.1
ollama serve
```

In another terminal, set `.env`:

```ini
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
OLLAMA_BASE_URL=http://localhost:11434
```

On Windows and macOS, Ollama may already run as a background service after installation. `ollama serve` is only needed when the API is not already running.

### Option B: Groq

Create an API key at [console.groq.com](https://console.groq.com), then set:

```ini
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=your_key_here
```

### Option C: Anthropic Claude

Create an API key at [console.anthropic.com](https://console.anthropic.com), then set:

```ini
LLM_PROVIDER=claude
LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=your_key_here
```

### Option D: OpenRouter

Create an API key at [openrouter.ai](https://openrouter.ai), then set:

```ini
LLM_PROVIDER=openrouter
LLM_MODEL=meta-llama/llama-3.1-8b-instruct:free
OPENROUTER_API_KEY=your_key_here
```

Do not commit `.env` or API keys to GitHub. Put secrets in your local environment or a secrets manager.

## Run Locally

Start the native desktop interface:

```bash
python app.py
```

Start the browser interface:

```bash
python app.py --web
```

Start the browser server without opening a browser automatically:

```bash
python app.py --web --no-browser
```

Run the terminal assistant:

```bash
python assistant.py
```

The browser interface normally uses `http://127.0.0.1:8000`. If that port is busy, the application selects the next available port.

## Run Tests

Run all tests:

```bash
python -m pytest tests/ -v
```

The suite checks:

- Protected ports and interfaces.
- Policy validation and allowed ranges.
- LLM availability and structured interpretation.
- MCP tool discovery and stdio integration.
- Assistant operations and diagnostics.

Run the firewall demonstration on a Linux environment with the required privileges:

```bash
python demo/validate_firewall.py
```

The demo uses a temporary service on port `9999`. Do not run it on a production host without reviewing the scripts first.

## Configuration and Policies

Edit `rules/policies.yaml` to review or change the policy:

- `protected_ports`: ports that cannot be blocked.
- `protected_interfaces`: interfaces that cannot be traffic-shaped.
- `allowed_actions`: firewall actions accepted by the server.
- `allowed_protocols`: permitted network protocols.
- `allow_arbitrary_ports`: whether ports outside an explicit list are allowed.
- Bandwidth and verification limits.

Policy checks happen inside `server.py`, immediately before network commands execute. The LLM cannot bypass these checks.

## Ports and Files

| Port | Purpose |
|---|---|
| `5000` | Docker web UI mapping |
| `8000` | Local embedded web server default and reserved Compose mapping |
| `11434` | Ollama API |

Important files:

- `app.py`: desktop and browser entry point.
- `assistant.py`: application orchestration.
- `llm_client.py`: LLM provider integration.
- `mcp_client.py`: FastMCP client.
- `server.py`: MCP tools and policy authority.
- `rules/policies.yaml`: security policy.
- `tools/`: network execution and verification.
- `ui/`: browser interface.
- `tests/`: automated tests.
- `DOCKER_GUIDE.md`: Docker operations and deeper troubleshooting.

## Troubleshooting

### Docker Cannot Connect to the Daemon

On Windows or macOS, open Docker Desktop and wait for it to finish starting. Verify:

```bash
docker ps
docker compose version
```

### Port 5000 Is Already in Use

Change only the host side of the mapping in `compose.yaml`:

```yaml
ports:
  - "5001:5000"
```

Then open [http://localhost:5001](http://localhost:5001).

### Ollama Model Download Is Slow

The first download is large. Keep the `ollama-data` volume and subsequent starts will reuse the model:

```bash
docker volume ls
```

### LLM Provider Not Configured

Check `.env`, confirm the selected provider name, and verify that Ollama or the selected API is reachable. Docker uses the bundled Ollama service at `http://localhost:11434`.

### Network Operations Are Rejected

A rejection may be intentional. Ports `22`, `53`, and `5000`, and interfaces `eth0` and `lo`, are protected by default. Review `rules/policies.yaml` and the policy response before changing anything.

### Linux Permission Errors

Run network operations with the required privileges. Docker Compose grants `NET_ADMIN` and `NET_RAW` to the container. Local execution may require `sudo`, depending on the operation and host configuration.

## GitHub Contribution Checklist

Before opening a pull request:

```bash
python -m pytest tests/ -v
git status
git diff --check
```

Do not commit:

- `.env` files containing secrets.
- Ollama model files.
- Logs, virtual environments, or Python cache directories.
- Host-specific Docker volumes.

For implementation details and design decisions, read [README.md](README.md).
