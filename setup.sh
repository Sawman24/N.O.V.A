#!/bin/bash
set -e

echo "=== Nova Setup ==="
echo ""

# Create .env from template if it doesn't exist
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✓ Created .env from .env.example"
        echo "  → Edit .env with your settings before starting Nova."
    else
        echo "✗ .env.example not found. Please re-clone the repo."
        exit 1
    fi
else
    echo "✓ .env already exists"
fi

# Create required directories
mkdir -p profiles tools
echo "✓ Directories ready (profiles/, tools/)"

# Check for Docker
if command -v docker &>/dev/null && command -v docker-compose &>/dev/null; then
    echo "✓ Docker and docker-compose found"
    echo ""
    echo "=== Ready ==="
    echo ""
    echo "  Start:   docker-compose up -d"
    echo "  Logs:    docker-compose logs -f nova"
    echo "  Stop:    docker-compose down"
    echo "  Web UI:  http://localhost:8000"
else
    echo "  Docker not found — to run manually:"
    echo ""
    echo "  pip install -r requirements.txt"
    echo "  uvicorn api:app --host 0.0.0.0 --port 8000"
    echo ""
    echo "  Web UI: http://localhost:8000"
fi

echo ""
