FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential espeak-ng ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dep resolution
RUN pip install --no-cache-dir uv

# PyTorch CPU-only + FastAPI — plapre is installed on first boot by server.py
RUN uv pip install --system --no-cache \
    torch torchaudio --index-url https://download.pytorch.org/whl/cpu

RUN uv pip install --system --no-cache fastapi "uvicorn[standard]" numpy "transformers>=5.0.0" python-multipart

WORKDIR /app
COPY server.py phrases.json ui.html ./

# Model weights are downloaded to /data on first start (persisted by HAOS)
ENV HF_HOME=/data/hf_cache
ENV TRANSFORMERS_CACHE=/data/hf_cache

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
