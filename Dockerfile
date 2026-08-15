FROM python:3.11-slim

WORKDIR /app

# Install minimal system build tools (needed to compile llama-cpp-python C++ extension)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create models directory for GGUF storage
RUN mkdir -p models

EXPOSE 8000

# Lightweight TCP health check — survives even when the model is busy generating tokens
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -S -c "import socket; socket.create_connection(('localhost', 8000), timeout=2)" || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
