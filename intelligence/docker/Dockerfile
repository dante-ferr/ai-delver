ARG BASE_IMAGE="rust:1.85-bookworm"

# =========================================================================
# Stage 1: 'base'
# Rust toolchain image with native build dependencies for Rapier / libtorch.
# Set TORCH_INDEX_URL to a CUDA wheel index (e.g. cu126) for GPU images.
# =========================================================================
FROM ${BASE_IMAGE} AS base

ARG DEBIAN_FRONTEND=noninteractive
ARG TORCH_VERSION=2.7.0
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        pkg-config \
        libssl-dev \
        python3 \
        python3-pip \
        python3-venv && \
    rm -rf /var/lib/apt/lists/*

# tch 0.20 expects libtorch 2.7.x. Prefer the Python wheel layout so the
# image stays portable without a separate official libtorch tarball.
RUN python3 -m pip install --break-system-packages --no-cache-dir \
        "torch==${TORCH_VERSION}" --index-url "${TORCH_INDEX_URL}" && \
    TORCH_LIB="$(python3 -c 'import os, torch; print(os.path.join(os.path.dirname(torch.__file__), "lib"))')" && \
    ln -sfn "${TORCH_LIB}" /opt/torch-lib

ENV LIBTORCH_USE_PYTORCH=1 \
    LIBTORCH_BYPASS_VERSION_CHECK=1 \
    LD_LIBRARY_PATH=/opt/torch-lib:${LD_LIBRARY_PATH}

ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID appgroup && \
    useradd -m -s /bin/bash -u $UID -g $GID appuser && \
    mkdir -p /usr/local/cargo /usr/local/rustup && \
    chown -R appuser:appgroup /usr/local/cargo /usr/local/rustup

COPY intelligence/docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# =========================================================================
# Stage 2: 'builder-dev'
# Compile the native trainer against local level + runtime crates.
# =========================================================================
FROM base AS builder-dev

WORKDIR /app

COPY --chown=appuser:appgroup level ./level
COPY --chown=appuser:appgroup runtime ./runtime
COPY --chown=appuser:appgroup intelligence/Cargo.toml intelligence/Cargo.lock \
    intelligence/build.rs intelligence/config.toml ./intelligence/
COPY --chown=appuser:appgroup intelligence/src ./intelligence/src

USER appuser
WORKDIR /app/intelligence

RUN cargo build --release --locked

# =========================================================================
# Stage 3: 'production'
# Slim runtime image with the compiled trainer binary.
# =========================================================================
FROM base AS production

WORKDIR /app
COPY --from=builder-dev --chown=appuser:appgroup \
    /app/intelligence/target/release/ai-delver-intelligence \
    /usr/local/bin/ai-delver-intelligence
COPY --from=builder-dev --chown=appuser:appgroup \
    /app/intelligence/config.toml \
    /app/intelligence/config.toml

USER appuser
WORKDIR /app/intelligence

CMD ["ai-delver-intelligence", "--help"]
