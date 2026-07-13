prepare-scripts:
	chmod +x ../run-ai-dev.sh

on-run: prepare-scripts

# Builds/runs the Rust intelligence trainer container from the repository root.
# Usage: make build ARGS="--batch-size=38"
build: on-run
	cd .. && ./run-ai-dev.sh --build $(ARGS)

run: on-run
	cd .. && ./run-ai-dev.sh $(ARGS)
