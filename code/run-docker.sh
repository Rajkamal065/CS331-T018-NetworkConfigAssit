#!/bin/bash

echo "🚀 Starting NetOps Assistant with Docker Compose..."
echo "===================================================="
echo ""
echo "Features:"
echo "  ✅ Ollama (llama3.1) bundled and ready"
echo "  ✅ FastMCP server running"
echo "  ✅ Network tools available (iptables, tc, ping, iperf3)"
echo "  ✅ Web UI on http://localhost:5000"
echo ""

# Check if image exists
if ! docker image inspect netops-assistant:latest > /dev/null 2>&1; then
    echo "📦 Image not found. Building..."
    bash build-docker.sh
    if [ $? -ne 0 ]; then
        echo "❌ Build failed!"
        exit 1
    fi
fi

echo ""
docker-compose up

# When stopped, offer cleanup
echo ""
echo "🛑 Container stopped"
read -p "Clean up containers and volumes? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose down -v
    echo "✅ Cleanup complete"
fi
