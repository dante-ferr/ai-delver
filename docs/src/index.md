# AI Delver

Welcome to the documentation for **AI Delver**, an agentic AI reinforcement learning framework that trains agents to solve level trajectories.

## Overview

Use the sidebar sections:

| Section | For |
| :--- | :--- |
| [How the Intelligence Learns](intelligence/index.md) | **Start here** to understand the training engine end-to-end |
| [CLI](cli/index.md) | Commands, training client, GUI wiring |
| [Agentic Fine-Tuning](agentic_fine_tuning/index.md) | Improve the **training engine** (HPs, eval packs, sim) |
| [Level Authoring](levels/authoring.md) | Geometry, spacing, sketches |
| [Player Curriculum](player/curriculum.md) | Player coaching / forgetting prevention |
| [Automatic Reviews](player/automatic_reviews.md) | When review passes arm, mix vs showcases |
| [Engineering](engineering/index.md) | History, Stage B deep-dive, errors, performance, roadmap |

**Learning how the Delver trains:** read [How the Intelligence Learns](intelligence/index.md) in order.

**Orchestrating agents** that improve the engine: [Agentic Fine-Tuning](agentic_fine_tuning/index.md) (emit the eval pack level list first, then `tune` / smoke trains).

**Player Delver coaching** is separate — [Player Curriculum](player/curriculum.md).
