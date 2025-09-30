#!/bin/bash
set -e
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )

# Argument Parsing
ENTRYPOINT="main"
BUILD_FLAG=""
for arg in "$@"; do
  if [ "$arg" = "--build" ]; then
    BUILD_FLAG="--build"
  else
    ENTRYPOINT="$arg"
  fi
done

# Determine container behavior via environment variables
export CONTAINER_COMMAND="PYTHONHASHSEED=0 python3 src/main.py"

# GPU Detection
if lspci | grep -iq 'vga.*nvidia'; then
  echo "✅ NVIDIA GPU detected. Using NVIDIA environment."
  #export BASE_IMAGE_VAR="paperspace/gradient-base:pt211-tf215-cudatk120-py311-20240202"
  #export BASE_IMAGE_VAR="nvidia/cuda:12.0.0-cudnn8-devel-ubuntu22.04"
  export BASE_IMAGE_VAR="tensorflow/tensorflow:2.15.0-gpu"
  #export BASE_IMAGE_VAR="python:3.11-slim"
  #COMPOSE_FILES="-f docker/docker-compose.yml -f docker/docker-compose.nvidia.yml"
  COMPOSE_FILES="-f docker/docker-compose.yml"
else
  echo "⚠️ No NVIDIA GPU detected. Starting in CPU-only mode."
  export BASE_IMAGE_VAR="python:3.11-slim"
  COMPOSE_FILES="-f docker/docker-compose.yml"
fi

# This section creates a .env file
# Docker Compose will automatically load it to get the UID and GID for setting permissions.
echo "⚙️  Generating .env file for user permissions..."
ENV_FILE_PATH="${SCRIPT_DIR}/.env"
echo "UID=$(id -u)" > ${ENV_FILE_PATH}
echo "GID=$(id -g)" >> ${ENV_FILE_PATH}
echo ".env file created at ${ENV_FILE_PATH}"

echo "🔧 Ensuring host log directory exists..."
mkdir -p "${SCRIPT_DIR}/ai-delver-intelligence/logs"

# Execution
echo "📖 Using base image: ${BASE_IMAGE_VAR}"
echo "🚀 Starting the intelligence container..."

if [ -n "$BUILD_FLAG" ]; then
  echo "🛠️  Build flag detected. Forcing image rebuild."
fi

echo "🧹 Cleaning up old containers..."
docker compose --project-directory ${SCRIPT_DIR} ${COMPOSE_FILES} down
docker compose --project-directory ${SCRIPT_DIR} ${COMPOSE_FILES} up ${BUILD_FLAG} --remove-orphans