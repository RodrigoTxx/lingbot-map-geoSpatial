# ============================================================
# LingBot-Map — GPU-enabled API Backend
# Base: PyTorch 2.8.0 + CUDA 12.8
# ============================================================
FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime

WORKDIR /app

# ── System dependencies ──────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────
# Copy only manifest first for layer-cache efficiency
COPY pyproject.toml README.md ./

# Install project + visualization extras
RUN pip install --no-cache-dir -e ".[vis]"

# FlashInfer for paged KV-cache attention (JIT-compiles on first use)
RUN pip install --no-cache-dir \
    --index-url https://pypi.org/simple \
    flashinfer-python

# API server dependencies
RUN pip install --no-cache-dir \
    fastapi>=0.115 \
    "uvicorn[standard]>=0.32" \
    python-multipart>=0.0.18

# ── Project source ────────────────────────────────────────────
COPY lingbot_map/ lingbot_map/
COPY demo.py .
COPY api/ api/

# ── Runtime configuration ─────────────────────────────────────
ENV PYTHONPATH=/app
ENV MODEL_PATH=/models/lingbot-map-long.pt
ENV UPLOAD_BASE=/tmp/lingbot_uploads
ENV CORS_ORIGINS=*

# Reduce CUDA allocator fragmentation (skip when --compile is used)
ENV PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

EXPOSE 8000

# ── Entrypoint ────────────────────────────────────────────────
CMD ["uvicorn", "api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--timeout-keep-alive", "75", \
     "--limit-max-requests", "1000"]
