FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

# Avoid prompts during package installations
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1

WORKDIR /app

# Install Python 3.10 (Ubuntu 22.04 default) and pip only — no build tools needed
# because we install a pre-built llama-cpp-python CUDA wheel below.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-dev \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first
RUN python3 -m pip install --upgrade pip

# Install all Python dependencies EXCEPT llama-cpp-python
COPY requirements.txt .
RUN grep -v "llama-cpp-python" requirements.txt > requirements_base.txt && \
    python3 -m pip install --no-cache-dir -r requirements_base.txt

# Install llama-cpp-python using an official pre-built CUDA 12.1 wheel.
# This avoids the lengthy C++ compilation step entirely.
RUN python3 -m pip install --no-cache-dir \
    llama-cpp-python \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121

# Copy application code
COPY . .

# Create models directory for GGUF storage
RUN mkdir -p models

# Expose the FastAPI port
EXPOSE 8000

# Lightweight TCP socket health check — does not spawn a Python process,
# works even when the model is busy generating tokens.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python3 -S -c "import socket; socket.create_connection(('localhost', 8000), timeout=2)" || exit 1

CMD ["python3", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
