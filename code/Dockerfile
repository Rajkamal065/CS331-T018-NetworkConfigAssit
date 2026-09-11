FROM python:3.11-slim

# Install system dependencies for Linux networking tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    iptables \
    iproute2 \
    iputils-ping \
    iperf3 \
    curl \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create results directory for benchmark charts
RUN mkdir -p /app/results

# Expose Web UI & API port
EXPOSE 5000

# Start the NetOps Web Assistant directly
CMD ["python", "app.py", "--web", "--no-browser", "--host", "0.0.0.0", "--port", "5000"]
