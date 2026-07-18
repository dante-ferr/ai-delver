# GUI-to-CLI Integration Protocol

All interactive GUI buttons in AI Delver that trigger server-side operations **must call the CLI** (`src/cli/main.py`) as a subprocess rather than talking to the FastAPI server directly.

This is a deliberate architectural decision: the CLI is the single source of truth for all training orchestration logic. Routing GUI interactions through the CLI prevents duplicating complex state-management, error handling, batch-size validation, and level-saving logic inside the GUI code.

---

## The Rule

> **Every GUI button that triggers a training lifecycle action must call `src/cli/main.py` as a subprocess, not the intelligence API directly.**

This means:
- The GUI **never** calls `httpx` or `websockets` directly to the intelligence server for training-related flows.
- All training operations (`train`, `stats`, `interrupt`) are exposed via the CLI and invoked using `sys.executable`.
- The GUI reads structured JSON lines from the CLI's `stdout` to update state and the UI.

---

## Why This Matters

| Concern | Without the Protocol | With the Protocol |
|:---|:---|:---|
| **Logic Duplication** | GUI and CLI each duplicate batch-size validation, level-hashing, and session wiring | CLI owns all orchestration logic; GUI just reads JSON stdout |
| **Boilerplate** | Every GUI action requires implementing async WebSocket/HTTP client code inside Tkinter threads | GUI is a thin subprocess runner + JSON parser |
| **Testability** | GUI logic is hard to test in isolation | CLI commands can be run and tested headlessly |
| **Extensibility** | Adding a new feature requires updating both GUI and CLI separately | Feature is added to the CLI first; GUI gets it for free |

---

For a detailed list of available CLI commands, their syntax, GUI triggers, and output event formats, see the [Commands Reference](commands.md).

---

## Adding a New CLI Command

1. Create `client/src/cli/commands/<name>.py` with a `run_<name>(args)` entry point.
2. Register the subparser in `client/src/cli/main.py`.
3. If the command needs a GUI button, add the button to the appropriate panel, and have it launch the CLI command via `subprocess.Popen(sys.executable, "src/cli/main.py", "<name>", ...)`.
4. Parse the JSON events from stdout and update `StateManager` as needed.
5. Document the new command and its event types in [commands.md](commands.md).
