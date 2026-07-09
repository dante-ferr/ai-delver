prepare-scripts:
	chmod +x run-ai-dev.sh
	chmod +x client/run.sh

update-submodules:
	@echo "🔁 Initializing submodules without overwriting changes..."
	git submodule update --init --recursive --merge

on-run: prepare-scripts

build-ai-dev: on-run
	./run-ai-dev.sh --build $(ARGS)

# Usage example: make run-ai-dev ARGS="--batch-size=48 --memory=12G --shm=2g --swap=14G"
run-ai-dev: on-run
	./run-ai-dev.sh $(ARGS)

build-client-dev:
	cd client && poetry env use 3.13 && poetry install

run-client-dev: on-run
	cd client && ./run.sh