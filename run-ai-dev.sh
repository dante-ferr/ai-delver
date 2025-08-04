#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# Determine the absolute path of the project root directory.
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# --- Simplified GPU Detection ---
if lspci | grep -iq 'vga.*nvidia'; then
  # --- NVIDIA GPU ---
  echo "✅ NVIDIA GPU detected. Using NVIDIA environment."
  # Official TensorFlow 2.15 image with CUDA and Python 3.11
  export BASE_IMAGE_VAR="paperspace/gradient-base:pt211-tf215-cudatk120-py311-20240202"
  COMPOSE_FILES="-f docker/docker-compose.yml -f docker/docker-compose.nvidia.yml"
else
  # --- CPU Fallback ---
  echo "⚠️ No NVIDIA GPU detected. Starting in CPU-only mode."
  # Standard Python 3.11 image for CPU
  export BASE_IMAGE_VAR="python:3.11-slim"
  COMPOSE_FILES="-f docker/docker-compose.yml"
fi

# --- Execution ---
echo "📖 Using base image: ${BASE_IMAGE_VAR}"
echo "🚀 Starting the intelligence container..."

BUILD_FLAG=""
if [ "$1" == "--build" ]; then
  echo "🛠️  Build flag detected. Forcing image rebuild."
  BUILD_FLAG="--build"
fi

echo "🧹 Cleaning up old containers..."
docker compose --project-directory ${SCRIPT_DIR} ${COMPOSE_FILES} down

docker compose --project-directory ${SCRIPT_DIR} ${COMPOSE_FILES} up ${BUILD_FLAG} --remove-orphans