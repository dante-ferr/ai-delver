ENTRYPOINT ?= main

prepare-scripts:
	chmod +x run-ai-dev.sh
	chmod +x ai-delver-client/run.sh

update-submodules:
	echo "🔁 Initializing submodules without overwriting changes..."
	git submodule update --init --recursive --merge

on-run: prepare-scripts

build-ai-dev: on-run update-submodules
	./run-ai-dev.sh --build

run-ai-dev: on-run
	./run-ai-dev.sh $(ENTRYPOINT)

build-client-dev: update-submodules
	cd ai-delver-client && poetry install

run-client-dev: on-run
	cd ai-delver-client && ./run.sh $(ENTRYPOINT)