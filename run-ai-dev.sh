#!/bin/bash
set -e
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# --- Argument Parsing ---
ENTRYPOINT="main" # Default is to run the server only
for arg in "$@"; do
  # This script now only accepts the entrypoint argument, not --build
  if [ "$arg" != "--build" ]; then
    ENTRYPOINT="$arg"
  fi
done

# --- Determine container behavior via environment variables ---
# The command to run inside the container is ALWAYS the same now.
# export CONTAINER_COMMAND="python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8001"
export CONTAINER_COMMAND="python3 src/main.py"
export AUTO_TRAIN_ON_STARTUP="false" # Default value

if [ "$ENTRYPOINT" = "auto_train_request" ]; then
  echo "🚦 Entrypoint is 'auto_train_request'. Server will start training automatically."
  export AUTO_TRAIN_ON_STARTUP="true"
else
  echo "🚦 Entrypoint is 'main'. Server will start and wait for requests."
fi

# ... (The rest of the script for GPU detection and execution remains the same) ...
# --- Simplified GPU Detection ---
if lspci | grep -iq 'vga.*nvidia'; then
  echo "✅ NVIDIA GPU detected. Using NVIDIA environment."
  export BASE_IMAGE_VAR="tensorflow/tensorflow:2.15.0-gpu"
  COMPOSE_FILES="-f docker/docker-compose.yml -f docker/docker-compose.nvidia.yml"
else
  echo "⚠️ No NVIDIA GPU detected. Starting in CPU-only mode."
  export BASE_IMAGE_VAR="python:3.11-slim"
  COMPOSE_FILES="-f docker/docker-compose.yml"
fi

# --- Execution ---
echo "📖 Using base image: ${BASE_IMAGE_VAR}"
echo "🚀 Starting the intelligence container..."

if [ -n "$BUILD_FLAG" ]; then
  echo "🛠️  Build flag detected. Forcing image rebuild."
fi

echo "🧹 Cleaning up old containers..."
docker compose --project-directory ${SCRIPT_DIR} ${COMPOSE_FILES} down
docker compose --project-directory ${SCRIPT_DIR} ${COMPOSE_FILES} up ${BUILD_FLAG} --remove-orphans