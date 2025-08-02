ENTRYPOINT ?= main

prepare-scripts:
	chmod +x run-ai-dev.sh
	chmod +x ai-delver-client/run.sh

update-submodules:
	echo "🔁 Initializing submodules without overwriting changes..."
	git submodule update --init --recursive --merge

on-run: prepare-scripts update-submodules

build-ai-dev: on-run
	./run-ai-dev.sh --build

run-ai-dev: on-run
	./run-ai-dev.sh

build-client-dev:
	cd ai-delver-client && poetry install

run-client-dev: on-run
	cd ai-delver-client && ./run.sh $(ENTRYPOINT)