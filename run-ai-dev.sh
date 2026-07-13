#!/bin/bash
set -e
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )

# Defaults
BUILD_FLAG=""
BATCH_SIZE="38"
MEMORY_LIMIT="12G"
SHM_SIZE="2g"
SWAP_LIMIT="14G"
TRAIN_ARGS='--levels "Ai Test #1" --cycles 1 --episodes-per-cycle 38 --agent ppo_delver'

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
    --train-args=*)
      TRAIN_ARGS="${arg#*=}"
      shift
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

# Build (if needed) then run the native Rust trainer against mounted sources.
export CONTAINER_COMMAND="cargo build --release --manifest-path Cargo.toml && cargo run --release --manifest-path Cargo.toml -- ${TRAIN_ARGS}"

# GPU Detection: prefer a CUDA-capable base when available. CPU Rust images are
# used otherwise; CUDA libtorch wiring can be refined later.
if lspci | grep -iq 'vga.*nvidia'; then
  echo "✅ NVIDIA GPU detected. Using NVIDIA override (host GPU visible)."
  export BASE_IMAGE_VAR="rust:1.85-bookworm"
  export TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu126}"
  COMPOSE_FILES="-f docker/docker-compose.yml -f docker/docker-compose.nvidia.yml"
else
  echo "⚠️ No NVIDIA GPU detected. Starting in CPU-only mode."
  export BASE_IMAGE_VAR="rust:1.85-bookworm"
  export TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cpu}"
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
echo "TORCH_INDEX_URL=${TORCH_INDEX_URL}" >> ${ENV_FILE_PATH}

echo ".env file created at ${ENV_FILE_PATH}"
echo "   - Batch Size: ${BATCH_SIZE}"
echo "   - Memory Limit: ${MEMORY_LIMIT}"
echo "   - Swap Limit (Total): ${SWAP_LIMIT}"
echo "   - SHM Size: ${SHM_SIZE}"
echo "   - Train Args: ${TRAIN_ARGS}"

echo "🔧 Ensuring host log and data directories exist..."
mkdir -p "${SCRIPT_DIR}/intelligence/logs"
mkdir -p "${SCRIPT_DIR}/intelligence/data"

# Execution
echo "📖 Using base image: ${BASE_IMAGE_VAR}"
echo "🚀 Starting the intelligence container..."

if [ -n "$BUILD_FLAG" ]; then
  echo "🛠️  Build flag detected. Forcing image rebuild."
fi

echo "🧹 Cleaning up old containers..."
docker compose --project-directory ${SCRIPT_DIR} ${COMPOSE_FILES} down
docker compose --project-directory ${SCRIPT_DIR} ${COMPOSE_FILES} up ${BUILD_FLAG} --remove-orphans
