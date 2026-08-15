#!/bin/bash
set -e

echo "=== Nova Setup ==="
echo ""

# ── System dependencies (Linux only) ─────────────────────────────────────────
# llama-cpp-python requires a C++17 compiler and cmake to build its native
# extension. Install them automatically on Debian/Ubuntu-based systems.
if [[ "$(uname -s)" == "Linux" ]]; then
    if command -v apt-get &>/dev/null; then
        echo "→ Checking build dependencies for llama-cpp-python..."
        MISSING_PKGS=()
        command -v gcc   &>/dev/null || MISSING_PKGS+=(gcc)
        command -v g++   &>/dev/null || MISSING_PKGS+=(g++)
        command -v cmake &>/dev/null || MISSING_PKGS+=(cmake)
        command -v make  &>/dev/null || MISSING_PKGS+=(make)

        if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
            echo "  Installing: ${MISSING_PKGS[*]}"
            sudo apt-get update -qq
            sudo apt-get install -y --no-install-recommends \
                build-essential cmake "${MISSING_PKGS[@]}"
            echo "✓ Build tools installed"
        else
            echo "✓ Build tools already present (gcc, g++, cmake, make)"
        fi
    else
        echo "⚠ Non-apt Linux detected. Ensure gcc, g++, cmake, and make are installed"
        echo "  before running pip install -r requirements.txt"
    fi
fi

# ── .env setup ────────────────────────────────────────────────────────────────
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

# ── Required directories ──────────────────────────────────────────────────────
mkdir -p profiles tools models
echo "✓ Directories ready (profiles/, tools/, models/)"

# ── Docker vs. manual ────────────────────────────────────────────────────────
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

# ── GPU note ─────────────────────────────────────────────────────────────────
echo ""
echo "  NOTE: The HuggingFace backend (BACKEND=huggingface) uses llama-cpp-python."
echo "  For GPU/CUDA acceleration, rebuild with:"
echo "    CMAKE_ARGS=\"-DGGML_CUDA=on\" pip install llama-cpp-python --force-reinstall"
echo ""
