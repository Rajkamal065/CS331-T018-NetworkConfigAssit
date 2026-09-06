#!/bin/bash

set -e

echo "🚀 NetOps Autonomous Agent [Ollama + FastMCP stdio]"
echo "=================================================="

# Function to wait for Ollama to be ready
wait_for_ollama() {
    echo "⏳ Waiting for Ollama to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
            echo "✅ Ollama is ready!"
            return 0
        fi
        echo "  Attempt $i/30: Waiting for Ollama..."
        sleep 2
    done
    echo "❌ Ollama failed to start after 60 seconds"
    return 1
}

# Function to pull Ollama model
pull_ollama_model() {
    local model=${1:-llama3.1}
    echo "📥 Pulling Ollama model: $model"
    
    if ollama list | grep -q "$model"; then
        echo "✅ Model $model already available"
    else
        echo "Downloading $model (this may take a few minutes on first run)..."
        ollama pull "$model"
        if [ $? -eq 0 ]; then
            echo "✅ Model $model downloaded successfully"
        else
            echo "❌ Failed to download model $model"
            return 1
        fi
    fi
}

# Start Ollama in the background
echo "🤖 Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready
if ! wait_for_ollama; then
    kill $OLLAMA_PID 2>/dev/null || true
    exit 1
fi

# Pull the model
if ! pull_ollama_model "llama3.1"; then
    kill $OLLAMA_PID 2>/dev/null || true
    exit 1
fi

# Export Ollama URL for the application
export OLLAMA_BASE_URL=http://localhost:11434

# Start the NetOps Assistant application
echo ""
echo "🎯 Starting NetOps Assistant..."
echo "📱 Web UI available at: http://localhost:5000"
echo "🔌 FastMCP server running on stdio"
echo "📡 Ollama API at: http://localhost:11434"
echo ""
echo "Ready to accept network configuration commands!"
echo "=================================================="
echo ""

# Run the web application. It starts the embedded HTTP UI and launches the
# FastMCP server as a stdio child process through the normal application path.
exec python app.py --web --no-browser
