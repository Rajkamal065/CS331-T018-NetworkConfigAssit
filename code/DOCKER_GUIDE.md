# 🐳 Docker Deployment Guide for NetOps Assistant

Complete guide to deploying the NetOps MCP Assistant using Docker with bundled Ollama.

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Clone/navigate to the project
cd netops-mcp-assistant

# Build and run
docker-compose up
```

Access the web UI at: **http://localhost:5000**

### Option 2: Use Convenience Scripts

#### On Linux/Mac
```bash
bash run-docker.sh
```

#### On Windows
```bash
run-docker.bat
```

These scripts:
1. Check if the image exists
2. Build if necessary
3. Start with Docker Compose
4. Offer cleanup when done

### Option 3: Manual Docker Commands

```bash
# Build the image
docker build -t netops-assistant:latest .

# Run with required capabilities
docker run -d \
  --name netops-assistant \
  --cap-add=NET_ADMIN \
  -p 5000:5000 \
  -p 8000:8000 \
  -p 11434:11434 \
  -v $(pwd)/rules:/app/rules \
  -v ollama-data:/root/.ollama \
  netops-assistant:latest

# View logs
docker logs -f netops-assistant
```

---

## Architecture: What's Inside

### The Container Includes

✅ **Python 3.11** with all dependencies
✅ **Ollama** (llama3.1 model)
✅ **Network Tools**: iptables, tc, ss, netstat, ping, iperf3
✅ **FastMCP Server** for policy enforcement
✅ **Web UI** (pywebview)
✅ **CLI Assistant** option

### Port Mappings

| Port | Service | Purpose |
|------|---------|---------|
| 5000 | Web UI | Access dashboard |
| 8000 | FastMCP | MCP server (internal) |
| 11434 | Ollama API | LLM service (internal) |

### Volumes

| Mount | Purpose |
|-------|---------|
| `/app/rules` | Policy files (policies.yaml) |
| `/app/logs` | Application logs |
| `ollama-data` | Cached Ollama models |

---

## Configuration

### Environment Variables

Set in `.env` (already pre-configured):

```ini
LLM_PROVIDER=ollama        # Use bundled Ollama
LLM_MODEL=llama3.1         # Model to use
OLLAMA_BASE_URL=http://localhost:11434
DEBUG=false                # Set to 'true' for verbose logging
```

### Custom Policies

Edit `rules/policies.yaml` to customize security policies:

```yaml
allow_arbitrary_ports: true
protected_ports:
  - port: 22
    reason: "SSH - Critical access"
  - port: 53
    reason: "DNS - Core infrastructure"
```

Changes are picked up immediately (no restart needed if volume-mounted).

---

## Common Tasks

### View Container Logs

```bash
docker-compose logs -f netops-assistant
```

### Stop the Container

```bash
docker-compose down
```

### Clean Up Everything (including volumes)

```bash
docker-compose down -v
```

### Rebuild the Image

```bash
docker-compose build --no-cache
docker-compose up
```

### Enter Container Shell

```bash
docker-compose exec netops-assistant /bin/bash
```

### Run Tests Inside Container

```bash
docker-compose exec netops-assistant python -m pytest tests/ -v
```

---

## Troubleshooting

### Port Already in Use

```
docker: Error response from daemon: ... port 5000 already in use
```

**Solution**: Stop conflicting container or change port in `compose.yaml`:

```yaml
ports:
  - '5001:5000'  # Use 5001 instead
```

### Ollama Not Loading Model on First Run

**Expected**: First startup takes time (downloading ~4GB model)

**Check progress**:
```bash
docker-compose logs netops-assistant | grep -i ollama
```

**Wait**: Typically 5-10 minutes depending on internet speed

### Network Operations Not Working

Make sure container has NET_ADMIN capability:

```bash
docker run --cap-add=NET_ADMIN ...
```

Docker Compose already includes this in `compose.yaml`.

### Out of Disk Space

Ollama models take ~4GB. If Docker reports low disk:

```bash
# Check Docker disk usage
docker system df

# Clean up unused images/volumes
docker system prune -a --volumes
```

---

## Performance Tuning

### Increase Ollama Memory

Edit `compose.yaml`:

```yaml
environment:
  - OLLAMA_NUM_GPU=1        # Enable GPU (if available)
  - OLLAMA_NUM_THREAD=8     # Number of CPU threads
```

### Use a Larger Model (slower but better quality)

```ini
# In .env
LLM_MODEL=mistral          # Larger model
```

Then pull: `ollama pull mistral` (takes more time/space)

### Use GPU Acceleration

If you have NVIDIA GPU:

```bash
# Install nvidia-docker
apt-get install nvidia-docker2

# Use in compose.yaml
runtime: nvidia
environment:
  - CUDA_VISIBLE_DEVICES=0
```

---

## Production Deployment

### Health Check

```bash
curl http://localhost:5000
```

### Automatic Restarts

Docker Compose already has `restart: unless-stopped` configured.

### Persistent Storage

All state is persisted in Docker volumes. To back up:

```bash
docker run --rm -v ollama-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/ollama-backup.tar.gz -C /data .
```

### Multi-Node Orchestration

For Kubernetes/Swarm, use `docker-compose.yaml` as a base but:

1. Use external image registry instead of local builds
2. Mount policies from ConfigMap
3. Scale Ollama separately if needed

---

## Security Considerations

✅ Container runs with minimum required capabilities (`NET_ADMIN`)
✅ No secrets in environment (policies are the security model)
✅ MCP server enforces policies server-side
✅ Network isolation via Docker bridge

⚠️ **Important**: This container needs `NET_ADMIN` to configure network interfaces. Only run in trusted environments.

---

## Examples

### Example 1: Block Port 9999

```
User: "Block port 9999"
```

In container:
1. Ollama (running on :11434) interprets intent
2. FastMCP server validates against policies.yaml
3. iptables executes inside container
4. Verifier tests connectivity
5. Result displayed in UI

### Example 2: Custom Policy

Edit `rules/policies.yaml`:

```yaml
protected_ports:
  - port: 8080
    reason: "Custom app - do not modify"
```

Push rule. Next time user tries to block 8080: **POLICY_REJECTION**

### Example 3: Bandwidth Limiting

```
User: "Limit bandwidth on eth0 to 100Mbps"
```

Ollama + MCP server + tc command = bandwidth rule applied instantly

---

## Next Steps

- Read [README.md](./README.md) for full architecture
- Check [tests/](./tests/) for integration examples
- Review [rules/policies.yaml](./rules/policies.yaml) for policy syntax
- Deploy to production with confidence!

---

**Questions?** Check the main [README.md](./README.md) or run:

```bash
docker-compose logs netops-assistant
```
