# AI Delver

**AI Delver** is a simulation framework where an AI agent learns to navigate 2D environments filled with obstacles, traps, and goals.

📖 **[Read the Documentation](https://dante-ferr.github.io/ai-delver/)**

This repo encapsulates all of its internal dependencies, serving as a development environment. So the purpose of working with it is to be able to change the codes of any of those dependencies, with those changes affecting the entire project's behavior in real time. Therefore, you must expect the tutorial sections below to work on a development standpoint, while the production environment should be set up separately on the client and intelligence projects (but this is not available yet. The production environment will only be available after the first beta version of Ai Delver).

## Features

- 🧠 **AI Integration**: Reinforcement learning support for training agents to solve complex spatial challenges.
- 🧱 **Level Editor**: A GUI tool for designing levels using a tile-based system powered by Pytiling.
- 📊 **Replay System**: Save and review agent behaviors. Also see statistics regarding the AI's attempts.

## Modules

- `client`: Client-side of the project. It includes every piece of interface the user needs to interact with in order to play AI Delver.
- `intelligence`: Server-side of the project. It manages the AI processing with TensorFlow needed to train the delver.
- `level`: Includes the code for the level model and grid map serialization.
- `runtime`: Responsible for the simulation runtime, game loop, physics engine, and replay systems.
- `agent`: Wrapper for agent metadata, loading, and saving functionality.
- `assets`: Graphical and game resources.
- [`pytiling`](https://github.com/dante-ferr/pytiling.git) (Submodule): Autotiling library for handling tilemaps.
- [`pyglet-dragonbones`](https://github.com/dante-ferr/pyglet-dragonbones.git) (Submodule): Renderer for DragonBones animation assets in `pyglet`.

## Requirements

- pyenv
- python poetry
- A decent NVIDIA GPU is highly recommended. If you don't own one, tensorflow will only use your CPU's processing power, which is super slow. Additionaly you must have in your system:
  - NVIDIA Gpu Drivers
  - NVIDIA Container Toolkit
- docker
- docker-compose
- docker buildx

## Setup (Local)

- Git clone Ai Delver (this repo) with its submodules: `git clone --recurse-submodules -j8 https://github.com/dante-ferr/ai-delver.git`
- Run `make run-ai-dev`
- Run `make run-client-dev` (on another terminal).

## Commands

- `make update-submodules`  
  Initializes and updates git submodules without overwriting local changes. It's automatically triggered on the next commands.

- `build-ai-dev`
  - Builds the intelligence container, enforces the application of changes on docker-related files and turns the container on.
  - Args:
    - --memory (default: 12G): The amount of RAM dedicated to the container. It's important to set a number compatible to your machine, otherwise your system may freeze.
    - --batch-size (default: 32): The amount of parallel environments per training session. Setting a low number will make training too slow, as will setting a very high number (which might even freeze your system as well).
    - --shm (default: 2g): Shared memory size. Essential to prevent Python multiprocessing crashes when using many parallel environments.
    - --swap (default: 14G): Total memory limit (RAM + Swap). Setting this protects your host OS from OOM locking if the training consumes too much memory.
    - Ex: make build-ai-dev ARGS="--batch-size=48 --memory=12G --shm=2g --swap=14G"

- `run-ai-dev`
  Turns the container on. It also builds the container if it hasn't been done yet.
  - Args: the same as the previous command.

- `build-client-dev`
  Builds the client side by installing its dependencies.

- `run-client-dev`
  Executes the client-side application.

## Tweaks
You can tweak the ai training settings at intelligence/src/ai/config.json. Be careful, because some of them might break the app if changed.