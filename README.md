# AI Delver

**AI Delver** is a simulation framework where an AI agent learns to navigate 2D environments filled with obstacles, traps, and goals.

This repo encapsulates all of its internal dependencies, serving as a development environment. So the purpose of working with it is to be able to change the codes of any of those dependencies, with this changes affecting the entire project's behavior in real time. Therefore, you must expect the tutorial sections below to work on a development standpoint, while the production environment should be set up separately on the ai-delver-client and ai-delver-intelligence subprojects (but this is not available yet. The production environment will only be available after the first beta version of Ai Delver).

## Features

- 🧠 **AI Integration**: Reinforcement learning support for training agents to solve complex spatial challenges.
- 🧱 **Level Editor**: A GUI tool for designing levels using a tile-based system powered by Pytiling.
- 📊 **Replay System**: Save and review agent behaviors across different environments (NOT AVAILABLE YET).

## Subprojects

- [`ai-delver-client`](https://github.com/dante-ferr/ai-delver-client): Client-side of the project. It includes every piece of interface the user needs to interact it in order to play Ai Delver.
- [`ai-delver-intelligence`](https://github.com/dante-ferr/ai_delver_intelligence): Server-side of the project. It manages the ai processing with Tensorflow needed to train the delver.
- [`ai-delver-level`](): Includes the code with the level's model.
- [`ai-delver-runtime`](https://github.com/dante-ferr/ai_delver_runtime): Subproject responsible for the runtime. It means that it includes the code behind the simulations that the ai will be trained on, the game and the replay system.
- [`pytiling`](https://github.com/dante-ferr/pytiling.git): Autotiling library for handling tilemaps.
- [`pyglet-dragonbones`](https://github.com/dante-ferr/pyglet-dragonbones.git): Renderer for DragonBones animation assets in `pyglet`.

## Requirements

- pyenv
- python poetry
- A decent NVIDIA GPU
  - NVIDIA Gpu Drivers
  - NVIDIA Container Toolkit
- OR a decent AMD GPU
  - (I need to list the requirements when possible)
- docker
- docker compose
- docker buildx

## Setup (Local)

- Git clone Ai Delver (this repo) with its submodules: `git clone --recurse-submodules -j8 https://github.com/dante-ferr/ai-delver.git`
- Run `make run-ai-dev`
- Run `make run-client-dev`. Note that this command has an entrypoint variable, which is explained further in the Commands section.

## Commands

- `make update-submodules`  
  Initializes and updates git submodules without overwriting local changes. It's automatically triggered on the next commands.

- `build-ai-dev`
  Builds the intelligence container, enforces the application of changes on docker-related files and turns the container on.

- `run-ai-dev`
  Builds the intelligence container and turns it on.

- `run-client-dev ENTRYPOINT=<game, ai or editor>`
  Executes the client-side application. This command supports an "ENTRYPOINT" variable with the following options:
  - game: immediately runs the Ai Delver game on the default-named level (My custom level.dill).
  - ai: sends a training request to the Intelligence container. Ensure that it's running while this command is executed.
  - editor: runs the editor application of the project. This is the default behavior of the run-client-dev command, so specifying "editor" as an entrypoint isn't actually needed.