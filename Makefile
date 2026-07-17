prepare-scripts:
	chmod +x run-ai-dev.sh
	chmod +x client/run.sh

update-submodules:
	@echo "🔁 Initializing submodules without overwriting changes..."
	git submodule update --init --recursive --merge

on-run: prepare-scripts

# Builds the Rust intelligence image.
# Usage: make build-ai-dev ARGS="--batch-size=38"
# One-shot train: make run-ai-dev ARGS='--train-args=train --levels "Ai Test #1" --cycles 1 --episodes-per-cycle 38'
build-ai-dev: on-run
	./run-ai-dev.sh --build $(ARGS)

# Starts the long-lived training server (serve on :8001) by default.
# Usage example: make run-ai-dev ARGS="--batch-size=38 --memory=12G --shm=2g"
run-ai-dev: on-run
	./run-ai-dev.sh $(ARGS)

build-client-dev:
	cd client && poetry env use 3.13 && poetry install

run-client-dev: on-run
	cd runtime && PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 poetry run python build_rust.py
	cd client && ./run.sh

docs-serve:
	@which mdbook > /dev/null || (echo "❌ mdBook is not installed. Please install it first (e.g. 'cargo install mdbook' or download the binary from https://github.com/rust-lang/mdBook/releases)" && exit 1)
	@echo "🖥️ Starting local documentation server at http://localhost:3000..."
	mdbook serve docs