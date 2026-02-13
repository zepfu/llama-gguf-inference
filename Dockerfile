# ==============================================================================
# llama-gguf-inference — CUDA (amd64)
#
# GGUF model inference server using llama.cpp with NVIDIA GPU acceleration.
# Platform-agnostic: works on RunPod, Vast.ai, Lambda, or any Docker host.
#
# Base image: ghcr.io/ggml-org/llama.cpp:server-cuda (linux/amd64 only)
# For CPU/multi-arch builds, see Dockerfile.cpu
# ==============================================================================

FROM ghcr.io/ggml-org/llama.cpp:server-cuda

ARG GIT_SHA=unknown
ARG BUILD_TIME=unknown

LABEL org.opencontainers.image.title="llama-gguf-inference" \
      org.opencontainers.image.description="GGUF model inference server using llama.cpp (CUDA)" \
      org.opencontainers.image.revision="$GIT_SHA" \
      org.opencontainers.image.created="$BUILD_TIME" \
      org.opencontainers.image.source="https://github.com/zepfu/llama-gguf-inference" \
      org.opencontainers.image.variant="cuda"

# Ensure llama-server can find shared libraries
ENV LD_LIBRARY_PATH=/app:/usr/local/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH}

# Minimal Python for gateway (uses stdlib only, no pip packages)
# hadolint ignore=DL3008
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        python3 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

# Set working directory
WORKDIR /opt/app

# Copy only runtime scripts (not tests, diagnostics, benchmarks, docs)
# Selective COPY avoids relying solely on .dockerignore and makes the image
# contents explicit. Only these files are needed at runtime:
#   start.sh         - Container entrypoint (orchestrates all services)
#   gateway.py       - API gateway (port 8000)
#   auth.py          - API key authentication and rate limiting
#   health_server.py - Platform health checks (port 8001)
#   key_mgmt.py      - API key management CLI
COPY scripts/start.sh scripts/gateway.py scripts/auth.py scripts/health_server.py scripts/key_mgmt.py /opt/app/scripts/

# Write version file and set permissions in a single layer
# hadolint ignore=SC2015
RUN printf "GIT_SHA=%s\nBUILD_TIME=%s\n" "$GIT_SHA" "$BUILD_TIME" > /opt/app/VERSION \
    && find /opt/app/scripts -name '*.sh' -exec chmod +x {} + 2>/dev/null; \
       find /opt/app/scripts -name '*.py' -exec chmod +x {} + 2>/dev/null; \
       if ! test -x /app/llama-server; then echo "ERROR: /app/llama-server not found"; exit 1; fi

# Default environment
# DATA_DIR: Base path for models and logs
#   - Auto-detects /runpod-volume or /workspace if /data doesn't exist
#   - Override for custom setups: DATA_DIR=/mnt/storage
ENV DATA_DIR=/data \
    PORT=8000 \
    BACKEND_PORT=8080 \
    NGL=99 \
    CTX=16384 \
    LOG_NAME=llama

EXPOSE 8000

# Health check using Python stdlib (no curl dependency)
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ping')" || exit 1

ENTRYPOINT ["/opt/app/scripts/start.sh"]
