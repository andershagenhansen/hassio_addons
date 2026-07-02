FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dep resolution
RUN pip install --no-cache-dir uv

# Install plapre and its dependencies (PyTorch CPU-only to keep image lean)
RUN uv pip install --system --no-cache \
    torch --index-url https://download.pytorch.org/whl/cpu

RUN git clone https://github.com/syv-ai/plapre.git /tmp/plapre_src \
    && cd /tmp/plapre_src \
    && git checkout bc8ad9ef61 \
    && printf '\n[tool.hatch.metadata]\nallow-direct-references = true\n' >> pyproject.toml \
    && uv pip install --system --no-cache . \
    && rm -rf /tmp/plapre_src

RUN uv pip install --system --no-cache fastapi "uvicorn[standard]"

WORKDIR /app
COPY server.py .

# Model weights are downloaded to /data on first start (persisted by HAOS)
ENV HF_HOME=/data/hf_cache
ENV TRANSFORMERS_CACHE=/data/hf_cache

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
