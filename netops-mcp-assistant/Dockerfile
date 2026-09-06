FROM ollama/ollama:latest AS ollama-base

FROM python:3.11-slim

# Copy Ollama from its image
COPY --from=ollama-base /bin/ollama /bin/ollama
COPY --from=ollama-base /usr/bin/ollama /usr/bin/ollama

# Install system dependencies for networking tools and Ollama
RUN apt-get update && apt-get install -y --no-install-recommends \
    iptables \
    iproute2 \
    iputils-ping \
    iperf3 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create Ollama model directory
RUN mkdir -p /root/.ollama/models

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose ports
EXPOSE 11434 5000 8000

# Use entrypoint to start both Ollama and the app
ENTRYPOINT ["/docker-entrypoint.sh"]
