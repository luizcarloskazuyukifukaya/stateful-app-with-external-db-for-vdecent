#!/bin/bash

# Default port candidates (priority order)
PORT_CANDIDATES=(80 8081 8082 8083 8084 8085)

# Exit on error
set -e

# Detect Local IP Address
LOCAL_IP=$(hostname -I | awk '{print $1}')

echo "===================================================="
echo "   Stateful Activity Log - Local Deployment"
echo "===================================================="

# Function to check if a port is in use
is_port_in_use() {
    ss -tuln | grep -q ":$1 "
}

# Find available port
for p in "${PORT_CANDIDATES[@]}"; do
    if ! is_port_in_use "$p"; then
        PORT=$p
        break
    fi
done

# If no port found
if [ -z "$PORT" ]; then
    echo "Error: No available ports (80, 8081, 8082, 8083, 8084, 8085)."
    exit 1
fi

echo "-> Using port: $PORT"

# Check for Docker Compose (plugin or standalone)
if docker compose version >/dev/null 2>&1; then
    DOCKER_CMD="docker compose"
elif docker-compose version >/dev/null 2>&1; then
    DOCKER_CMD="docker-compose"
else
    echo "Error: Docker Compose is not installed."
    echo "This script requires Docker to run the App and PostgreSQL database together."
    exit 1
fi

echo "Step 1: Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "-> Created .env from .env.example"
fi

if command -v npm >/dev/null 2>&1; then
    echo "Step 2: Installing host-side dependencies (Optional, for IDE support)..."
    npm install --silent
    echo "-> Done."
else
    echo "Step 2: Skipping host-side npm install (Not found). Docker will handle all dependencies internally."
fi

echo "Step 3: Starting App + Database via Docker..."

# Create override file with selected port
cat <<OVERRIDE > docker-compose.local.yaml
services:
  app:
    ports:
      - "$PORT:80"
OVERRIDE

echo "-> Building and launching containers..."
$DOCKER_CMD -f docker-compose.yaml -f docker-compose.local.yaml up --build -d

# Build URLs depending on port
if [ "$PORT" -eq 80 ]; then
    LOCAL_URL="http://localhost"
    NETWORK_URL="http://$LOCAL_IP"
else
    LOCAL_URL="http://localhost:$PORT"
    NETWORK_URL="http://$LOCAL_IP:$PORT"
fi

echo ""
echo "Success! The application is starting up."
echo "Access the web page at:"
echo "1) Local:  $LOCAL_URL"

if [ ! -z "$LOCAL_IP" ]; then
    echo "2) Network: $NETWORK_URL"
    echo "   (Use this URL to access from other PCs in your network)"
fi

echo ""
echo "Useful Commands:"
echo " - View logs:  $DOCKER_CMD logs -f app"
echo " - Stop app:   $DOCKER_CMD down"
echo "===================================================="
