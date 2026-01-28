#!/bin/bash
set -e
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )

# Defaults
ENTRYPOINT="main"
BUILD_FLAG=""
BATCH_SIZE="32"
MEMORY_LIMIT="12G"
# Default SHM: 2GB is safe for 48 envs + TensorFlow overhead
SHM_SIZE="2g"
# Default Swap: If null, Docker defaults to 2x RAM (12G RAM + 12G Swap = 24G Total)
# Setting this explicitly protects your host OS from OOM locking.
# Note: This value represents RAM + SWAP combined.
SWAP_LIMIT="14G" 

# Argument Parsing
for arg in "$@"; do
  case $arg in
    --build)
      BUILD_FLAG="--build"
      shift
      ;;
    --batch-size=*)
      BATCH_SIZE="${arg#*=}"
      shift
      ;;
    --memory=*)
      MEMORY_LIMIT="${arg#*=}"
      shift
      ;;
    --shm=*)
      SHM_SIZE="${arg#*=}"
      shift
      ;;
    --swap=*)
      SWAP_LIMIT="${arg#*=}"
      shift
      ;;
    *)
      ENTRYPOINT="$arg"
      ;;
  esac
done

# Determine container behavior via environment variables
export CONTAINER_COMMAND="PYTHONHASHSEED=0 python3 src/main.py"

# GPU Detection
if lspci | grep -iq 'vga.*nvidia'; then
  echo "✅ NVIDIA GPU detected. Using NVIDIA environment."
  export BASE_IMAGE_VAR="tensorflow/tensorflow:2.15.0-gpu"
  # We use a separate override file for GPU configs
  COMPOSE_FILES="-f docker/docker-compose.yml -f docker/docker-compose.nvidia.yml"
else
  echo "⚠️ No NVIDIA GPU detected. Starting in CPU-only mode."
  export BASE_IMAGE_VAR="python:3.11-slim"
  COMPOSE_FILES="-f docker/docker-compose.yml"
fi

# Generate .env file
echo "⚙️  Generating .env file with permissions and config..."
ENV_FILE_PATH="${SCRIPT_DIR}/.env"

echo "UID=$(id -u)" > ${ENV_FILE_PATH}
echo "GID=$(id -g)" >> ${ENV_FILE_PATH}
echo "AI_BATCH_SIZE=${BATCH_SIZE}" >> ${ENV_FILE_PATH}
echo "AI_MEMORY_LIMIT=${MEMORY_LIMIT}" >> ${ENV_FILE_PATH}
echo "AI_SHM_SIZE=${SHM_SIZE}" >> ${ENV_FILE_PATH}
echo "AI_SWAP_LIMIT=${SWAP_LIMIT}" >> ${ENV_FILE_PATH}
echo "BASE_IMAGE=${BASE_IMAGE_VAR}" >> ${ENV_FILE_PATH}

echo ".env file created at ${ENV_FILE_PATH}"
echo "   - Batch Size: ${BATCH_SIZE}"
echo "   - Memory Limit: ${MEMORY_LIMIT}"
echo "   - Swap Limit (Total): ${SWAP_LIMIT}"
echo "   - SHM Size: ${SHM_SIZE}"

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