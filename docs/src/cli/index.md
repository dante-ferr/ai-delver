# CLI

Headless and GUI-facing command-line tooling under `client/src/cli/`.

| Doc | Purpose |
| :--- | :--- |
| [Commands Reference](commands.md) | Every `main.py` subcommand, flags, GUI triggers, event table |
| [Training Client Internals](training_client.md) | Batch alignment, JSON event examples, signals, weight sync |
| [GUI-to-CLI Protocol](gui_protocol.md) | GUI must spawn CLI subprocesses — never call the intelligence API directly |

Canonical entrypoint:

```bash
cd client
poetry run python src/cli/main.py <command> ...
```

Engine fine-tuning (`tune`, eval packs): [Agentic Fine-Tuning](../agentic_fine_tuning/index.md).
