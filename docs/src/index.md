# AI Delver

Welcome to the documentation for **AI Delver**, an agentic AI reinforcement learning framework that trains agents to solve level trajectories.

## Overview

Use the sidebar sections:

| Section | For |
| :--- | :--- |
| [CLI](cli/index.md) | Commands, training client, GUI wiring |
| [Agentic Fine-Tuning](agentic_fine_tuning/index.md) | Improve the **training engine** (HPs, eval packs, sim) |
| [Level Authoring](levels/authoring.md) | Geometry, spacing, sketches |
| [Player Curriculum](player/curriculum.md) | Player coaching / forgetting prevention |
| [Engineering](engineering/index.md) | Errors, performance history, roadmap |

Orchestrating agents that improve the training engine: start at [Agentic Fine-Tuning](agentic_fine_tuning/index.md) (emit the eval pack level list first, then `tune` / smoke trains). Player Delver coaching is separate — [Player Curriculum](player/curriculum.md).
