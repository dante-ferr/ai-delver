#!/bin/bash

set -e
set -o pipefail

echo "🖥️ Running AI Delver's client application on the '$1' entrypoint..."
if [ "$1" == "game" ]; then
    PYTHONHASHSEED=0 poetry run python src/direct_game.py
elif [ "$1" == "ai" ]; then
    PYTHONHASHSEED=0 poetry run python src/direct_ai.py
elif [ "$1" == "editor" ]; then
    PYTHONHASHSEED=0 poetry run python src/main.py
else
    PYTHONHASHSEED=0 poetry run python src/main.py
fi 