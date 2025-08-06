#!/bin/bash
set -e

# --- Argument Parsing ---
# Set default values
BUILD_FLAG=""
ENTRYPOINT="main" # Default from your Makefile

# Loop through all arguments passed to the script
for arg in "$@"; do
  case $arg in
    --build)
    BUILD_FLAG="--build"
    shift # Consume the --build argument
    ;;
    *)
    # Assume any other argument is the entrypoint
    ENTRYPOINT="$arg"
    shift # Consume the entrypoint argument
    ;;
  esac
done

# --- Determine container command based on ENTRYPOINT ---
if [ "$ENTRYPOINT" = "auto_train_request" ]; then
  echo "🚦 Entrypoint is 'auto_train_request'. Setting command to run the auto-train script."
  # Export the command for docker-compose to use.
  export CONTAINER_COMMAND="python3 src/auto_train_request.py"
else
  echo "🚦 Entrypoint is 'main'. Setting command to run the API server."
  # The default command to run the uvicorn server.
  export CONTAINER_COMMAND="python3 src/main.py"
fi


# --- Determine the absolute path of the project root directory ---
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

echo "🔧 Preparing host directories for Docker volumes..."
mkdir -p "${SCRIPT_DIR}/ai-delver-intelligence/logs/train"

# --- Simplified GPU Detection ---
if lspci | grep -iq 'vga.*nvidia'; then
  # --- NVIDIA GPU ---
  echo "✅ NVIDIA GPU detected. Using NVIDIA environment."
  export BASE_IMAGE_VAR="tensorflow/tensorflow:2.15.0-gpu"
  COMPOSE_FILES="-f docker/docker-compose.yml -f docker/docker-compose.nvidia.yml"
else
  # --- CPU Fallback ---
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