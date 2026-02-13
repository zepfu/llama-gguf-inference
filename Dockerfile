# ==============================================================================
# llama-gguf-inference
#
# GGUF model inference server using llama.cpp
# Platform-agnostic: works on RunPod, Vast.ai, Lambda, or any Docker host
#
# Base image: ghcr.io/ggml-org/llama.cpp:server-cuda
# ==============================================================================

FROM ghcr.io/ggml-org/llama.cpp:server-cuda

ARG GIT_SHA=unknown
ARG BUILD_TIME=unknown

LABEL org.opencontainers.image.title="llama-gguf-inference"
LABEL org.opencontainers.image.description="GGUF model inference server using llama.cpp"
LABEL org.opencontainers.image.revision=$GIT_SHA
LABEL org.opencontainers.image.created=$BUILD_TIME

# Ensure llama-server can find shared libraries
ENV LD_LIBRARY_PATH=/app:/usr/local/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH}

# Minimal Python for gateway (uses stdlib only, no pip packages)
# hadolint ignore=DL3008
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        python3 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy application
WORKDIR /opt/app
COPY . /opt/app

# Write version file for runtime inspection
RUN printf "GIT_SHA=%s\nBUILD_TIME=%s\n" "$GIT_SHA" "$BUILD_TIME" > /opt/app/VERSION

# Make scripts executable
RUN if ls /opt/app/scripts/*.sh 1>/dev/null 2>&1; then chmod +x /opt/app/scripts/*.sh; fi && \
    if ls /opt/app/scripts/*.py 1>/dev/null 2>&1; then chmod +x /opt/app/scripts/*.py; fi

# Verify base image has required binary
RUN test -x /app/llama-server || (echo "ERROR: /app/llama-server not found" && exit 1)

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

ENTRYPOINT ["/opt/app/scripts/start.sh"]
