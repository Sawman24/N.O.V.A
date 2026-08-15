FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

# Avoid prompts during package installations
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1

WORKDIR /app

# Install default Python 3, pip, and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-dev \
        python3-pip \
        cmake \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Configure environment variables to compile llama-cpp-python with CUDA GPU support
ENV CMAKE_ARGS="-DGGML_CUDA=on"
ENV FORCE_CMAKE=1

# Install Python dependencies (ensuring python3 -m pip matches the python3 runtime)
COPY requirements.txt .
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create models directory for GGUF storage
RUN mkdir -p models

# Expose the FastAPI port
EXPOSE 8000

# Health check — optimized to check if the socket port 8000 is open and listening.
# This succeeds instantly even if the FastAPI event loop is temporarily blocked
# by heavy GPU inference (generating tokens).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python3 -S -c "import socket; socket.create_connection(('localhost', 8000), timeout=2)" || exit 1

CMD ["python3", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
