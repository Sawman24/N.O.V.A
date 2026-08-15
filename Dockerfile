FROM python:3.11-slim

WORKDIR /app

# Install system build dependencies required by llama-cpp-python (C++ extension)
# and clean up apt caches in the same layer to keep image size down.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        gcc \
        g++ \
        libstdc++6 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer — only rebuilds when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create models directory for GGUF storage
RUN mkdir -p models

# Expose the FastAPI port
EXPOSE 8000

# Health check — using lightweight curl instead of spawning a heavy python process
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
