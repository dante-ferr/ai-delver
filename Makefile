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

# Regenerate DragonBones editor representations (and Delver preview GIFs).
# Requires a working OpenGL context; headless: xvfb-run -a make regen-dragonbones
regen-dragonbones:
	cd client && poetry run python src/cli/main.py regen-dragonbones

# Print jump/gap authoring limits from runtime physics TOMLs.
platforming-limits: on-run
	cd client && poetry run python src/cli/main.py platforming-limits

# Interactive Pyglet playtest. Usage: make play-level LEVEL=platforming-1
play-level: on-run
	cd client && poetry run python src/cli/main.py play-level --level "$(LEVEL)"

# Level browser GUI: list / minimap preview / play. Usage: make playtest-gui
playtest-gui: on-run
	cd client && poetry run python src/cli/main.py playtest-gui

# Level groups. Usage:
#   make level-group-list
#   make level-group-add NAME=my_group LEVELS="a,b,c"
#   make level-group-delete NAME=my_group DELETE_FILES=1
level-group-list: on-run
	cd client && poetry run python src/cli/main.py level-group list

level-group-add: on-run
	cd client && poetry run python src/cli/main.py level-group add --name "$(NAME)" --levels "$(LEVELS)" $(if $(REPLACE),--replace,)

level-group-delete: on-run
	cd client && poetry run python src/cli/main.py level-group delete --name "$(NAME)" $(if $(DELETE_FILES),--delete-files,)

# Generate a procedural platforming pack under level_saves/generated/<GROUP>/.
# Curriculum phases are on by default. Usage:
#   make gen-platforming-pack GROUP=platforming_gen_v1 SEED=42
#   make gen-platforming-pack GROUP=free_mix COUNT=10 SEED=1 ARGS='--no-curriculum'
GROUP ?= platforming_gen_v1
COUNT ?=
gen-platforming-pack: on-run
	cd client && poetry run python src/cli/main.py gen-platforming-pack --group "$(GROUP)" $(if $(COUNT),--count $(COUNT),) $(if $(SEED),--seed $(SEED),) $(ARGS)
