ARG BASE_IMAGE="rust:1.85-bookworm"

# =========================================================================
# Stage 1: 'base'
# Rust toolchain image with native build dependencies for Rapier / libtorch.
# =========================================================================
FROM ${BASE_IMAGE} AS base

ARG DEBIAN_FRONTEND=noninteractive

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

# tch 0.20 expects a matching libtorch. Prefer the Python wheel layout so the
# image stays portable without a separate official libtorch tarball.
RUN python3 -m pip install --break-system-packages --no-cache-dir \
        "torch==2.4.1" --index-url https://download.pytorch.org/whl/cpu && \
    TORCH_LIB="$(python3 -c 'import os, torch; print(os.path.join(os.path.dirname(torch.__file__), "lib"))')" && \
    ln -sfn "${TORCH_LIB}" /opt/torch-lib

ENV LIBTORCH_USE_PYTORCH=1 \
    LD_LIBRARY_PATH=/opt/torch-lib:${LD_LIBRARY_PATH}

ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID appgroup && \
    useradd -m -s /bin/bash -u $UID -g $GID appuser && \
    mkdir -p /usr/local/cargo /usr/local/rustup && \
    chown -R appuser:appgroup /usr/local/cargo /usr/local/rustup

# =========================================================================
# Stage 2: 'builder-dev'
# Compile the native trainer against local level + runtime crates.
# =========================================================================
FROM base AS builder-dev

WORKDIR /app

COPY --chown=appuser:appgroup level ./level
COPY --chown=appuser:appgroup runtime ./runtime
COPY --chown=appuser:appgroup intelligence/intelligence_rs ./intelligence/intelligence_rs
COPY --chown=appuser:appgroup intelligence/src/ai/config.toml ./intelligence/src/ai/config.toml

USER appuser
WORKDIR /app/intelligence/intelligence_rs

RUN cargo build --release --locked

# =========================================================================
# Stage 3: 'production'
# Slim runtime image with the compiled trainer binary.
# =========================================================================
FROM base AS production

WORKDIR /app
COPY --from=builder-dev --chown=appuser:appgroup \
    /app/intelligence/intelligence_rs/target/release/ai-delver-intelligence \
    /usr/local/bin/ai-delver-intelligence
COPY --from=builder-dev --chown=appuser:appgroup \
    /app/intelligence/src/ai/config.toml \
    /app/intelligence/src/ai/config.toml

USER appuser
WORKDIR /app/intelligence

ENTRYPOINT ["ai-delver-intelligence"]
CMD ["--help"]
