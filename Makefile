ENTRYPOINT ?= main

update-submodules:
	echo "🔁 Initializing submodules without overwriting changes..."
	git submodule update --init --recursive --merge

build-ai-dev: update-submodules
	./run-ai-dev.sh --build

run-ai-dev: update-submodules
	./run-ai-dev.sh

run-client-dev: update-submodules
	./ai-delver-client/run.sh $(ENTRYPOINT)