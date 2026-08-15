FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

# Avoid prompts during package installations
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1

WORKDIR /app

# Install Python 3.11, pip, and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-dev \
        python3-pip \
        cmake \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Link python3.11 as the default python command
RUN ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

# Configure environment variables to compile llama-cpp-python with CUDA GPU support
ENV CMAKE_ARGS="-DGGML_CUDA=on"
ENV FORCE_CMAKE=1

# Install Python dependencies (cached layer — only rebuilds when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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
    CMD python -S -c "import socket; socket.create_connection(('localhost', 8000), timeout=2)" || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
