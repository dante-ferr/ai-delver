# Agentic Fine-Tuning Protocol (CLI)

This protocol tells an **orchestrating AI agent** (or a human following the same ritual) how to fine-tune the Delver using the CLI. Prefer the CLI over calling the intelligence HTTP API directly—the same rule as the [GUI-to-CLI Integration Protocol](gui_cli_protocol.md).

Near-term goal: confirm a **capable platforming** Delver. Later big features (traps, enemies, puzzles) each get another fine-tune pass once they exist in the training sim.

---

## 1. Hard rules for orchestrators

1. **Orchestrate through the client CLI**, not by inventing ad-hoc HTTP clients:
   ```bash
   cd client
   poetry run python src/cli/main.py <command> ...
   ```
2. **Ensure the training server is up** before `train` / `tune` (default `localhost:8001`):
   ```bash
   # from repo root
   make run-ai-dev
   # or: cargo run --release --manifest-path intelligence/Cargo.toml --features tch/download-libtorch -- serve --host 127.0.0.1 --port 8001
   ```
3. **Use `--mode static` only.** Dynamic curriculum still errors on the server.
4. **Parse JSON lines on stdout.** Every lifecycle signal is a single JSON object with an `event` field. Do not scrape human prose logs.
5. **Prefer `--runs-per-cycle`.** A run is a full-length play (up to `max_seconds_per_episode`). Intelligence converts runs into collect-window episode slots (`episodes_per_run = max_seconds_per_episode / collect_seconds_per_env`, default 12). Legacy `--episodes-per-cycle` remains for low-level control; when using it, align to `env_batch_size` from `GET /init` (the CLI auto-rounds and emits an `info` event).
6. **Warm-start expects libtorch `.ot` bytes.** Legacy TF-Agents zip payloads are ignored by the Rust server. Prefer checkpoints / weights produced by the current intelligence binary.
7. **Do not call the intelligence API from GUI or one-off scripts** for training lifecycle actions—extend the CLI instead.

Command reference: [CLI Commands Reference](cli_commands.md). Curriculum / forgetting behavior: [Curriculum & Forgetting Prevention](curriculum_and_forgetting.md).

---

## 2. Standard fine-tune ritual (`train`)

### Prerequisites

| Check | How |
| :--- | :--- |
| Server healthy | `GET http://localhost:8001/init` succeeds |
| Levels exist | Names resolve under `client/data/level_saves/<name>/level.json` |
| Agent folder | `create-agent` / `load-agent`, or an existing `data/agents/<agent>/` |
| Platforming-only for now | Trainer loads **platforms + delver + goal** only; other world objects are ignored until the sim is extended |

### Train session

```bash
cd client
poetry run python src/cli/main.py train \
    --levels "Ai Test #1,Ai Test #2" \
    --cycles 10 \
    --runs-per-cycle 5 \
    --mode static \
    --agent ppo_delver \
    --server localhost:8001 \
    --checkpoint-interval 5
```

Prefer `--runs-per-cycle` (full-length run equivalents). The intelligence server converts runs → episode slots via `max_seconds_per_episode / collect_seconds_per_env` (default **12**). Legacy `--episodes-per-cycle` still works for low-level budgets.

Optional overrides (`--learning-rate`, `--entropy-regularization`, reward knobs, etc.) map into `config_overrides` for the server. Defaults live in `intelligence/config.toml`.

### What the CLI already automates

- Batch-size alignment for `--episodes-per-cycle`
- Level prepare / hash for the `/train` payload
- Weight upload when agent weights exist (warm-start)
- **New-challenge LR scaling**: if warm-starting and any target level is absent from `trained_levels` in metadata, LR becomes `0.000075` unless the user/orchestrator set `--learning-rate`
- Weight / checkpoint download on complete or interrupt
- Append trained levels to metadata on success
- Final `stats` emission

### Events to watch

| Event | Meaning for the orchestrator |
| :--- | :--- |
| `session_created` | Training started; keep `session_id` for `interrupt` |
| `progress` | Cycle finished |
| `metrics` | Loss / return snapshot (nerd stats) |
| `checkpoint` | Intermediate weights saved under the agent |
| `completed` / `interrupted` | Terminal success paths |
| `error` | Stop; fix the message before retrying |
| `stats` | Aggregate victories / amount after the run |

Interrupt:

```bash
poetry run python src/cli/main.py interrupt \
    --session-id <uuid> \
    --server localhost:8001
```

### Success criteria (platforming)

Treat the Delver as “capable enough to proceed” when:

1. Training completes without `error`.
2. `stats` shows a clear rise in victories vs early cycles / a prior blank run.
3. Warm-start on a **new platform layout** still improves (or at least does not collapse) with the auto-reduced LR.
4. Optional: mix several platform levels in one `--levels` list so the policy sees layout diversity in one session.

Native one-shot Rust `train` (see `intelligence/README.md`) is fine for benchmarks; for the product / orchestrator loop, prefer this client CLI so agent folders, forgetting prevention, and stats stay consistent.

---

## 3. Auto fine-tuning (`tune`)

AI Delver includes **Optuna-based automatic hyperparameter search** as a developer CLI command. Use it when defaults feel wrong after a big change, or when an orchestrator needs to search for a better HP set before a long train.

### Behavior

`tune` (implemented in `client/src/cli/commands/tune.py`):

1. Creates an Optuna study that **maximizes win rate**.
2. For each trial, suggests:
   - `learning_rate` ∈ `[5e-5, 8e-4]` (log scale)
   - `entropy_reg` ∈ `[0.05, 0.30]`
   - `finished_reward` ∈ `[50, 200]`
3. Spawns `poetry run python src/cli/main.py train ...` as a **subprocess** with those overrides (`--mode static`).
4. Streams the child process JSON events:
   - If a `metrics` event has `abs(loss) > 20`, the trial is **pruned** early (`TrialPruned`).
   - If a `stats` event arrives, win rate = `victories / amount`.
5. Emits `completed` with `best_params` and `best_value` when the study finishes.

### Invocation

```bash
cd client
poetry run python src/cli/main.py tune \
    --levels "Ai Test #1" \
    --cycles 5 \
    --episodes-per-cycle 38 \
    --agent ppo_delver \
    --trials 10 \
    --server localhost:8001
```

`tune` still uses legacy `--episodes-per-cycle` for trial subprocesses.
### Orchestrator protocol for `tune`

1. Start the intelligence server.
2. Run `tune` with a **representative platforming level set** and enough `--cycles` that win rate is meaningful (too few cycles → noisy objective).
3. Read the final `completed` event’s `best_params`.
4. Apply those values on a longer `train` run (CLI flags and/or update comments in `intelligence/config.toml` if they should become project defaults).
5. Do **not** treat `tune` as a substitute for feature work: it only searches HPs for the current sim and reward stack.

### Caveats

- Search ranges are coded in `tune.py`. The shipped default `entropy_regularization` in `config.toml` is `0.01`; Optuna’s current entropy band starts at `0.05`. If tuned entropy looks high vs known-good defaults, prefer a follow-up `train` with an explicit lower entropy override.
- Prefer `--episodes-per-cycle` equal to `env_batch_size` (e.g. `38`) so trials are not silently rounded.
- `tune` is developer-oriented (no GUI button). Orchestrators may run it headlessly; parse JSON the same way as `train`.

---

## 4. When new big features are added

Adding enemies, traps, puzzles, or other gameplay systems is a **developer fine-tune ritual**, not a reason to discard the platforming Delver.

```text
implement feature in editor + training sim
        → fine-tune via orchestrator + CLI (warm-start)
        → confirm learning / retention
        → next feature
```

### Required order

1. **Land the feature in the training environment**  
   Extend level loading and physics/observations so the new objects affect rollouts. Today `Level::from_json` only keeps platforms, one delver, and one goal; other world-object names are ignored. Fine-tuning on levels that *visually* contain traps does nothing until those objects are simulated.

2. **Warm-start from the last capable checkpoint**  
   Keep the same `--agent` (or load prior weights). The CLI uploads existing weights and may auto-cut LR when new level names appear in the session.

3. **Fine-tune with `train` (static)**  
   Include levels that exercise the new feature. Prefer **combo levels** (old platforming + new mechanic) so prior skills are not wiped—see [Curriculum & Forgetting Prevention](curriculum_and_forgetting.md).

4. **Optionally run `tune`**  
   If rewards or exploration need retuning for the new mechanic (e.g. new death conditions change return scale), run `tune` on a small representative set, then lock HPs into a longer `train`.

5. **Confirm**  
   Check `stats` / victories on levels that use the new feature **and** on older platform-only levels if retention matters. Roll back to a checkpoint if the run diverges.

6. **Optional product step**  
   Refresh any shipped foundation weights for players only after the developer Delver is capable on the expanded game. That is separate from this ritual.

### What does *not* require a full feature ritual

| Change | Action |
| :--- | :--- |
| New platform **layouts** only | `train` with mixed `--levels`; rely on auto LR scaling for truly new names |
| HP / reward tweak only | Short `train`, or `tune` then `train` |
| New mechanic in the editor but **not** in the training sim | Do not fine-tune yet—extend the sim first |

### What you should expect

- **Yes**, plan another orchestrator+CLI fine-tune after each big mechanic family lands in the sim.
- **No**, you do not start from random weights every time—warm-start and extend.
- One shared policy + `config.toml` remains the architecture; **checkpoints advance** as the game grows.

---

## 5. Minimal orchestrator checklist

```text
[ ] Server up (serve / make run-ai-dev)
[ ] Agent created or loaded
[ ] Levels are real platforming maps (or maps whose mechanics exist in the sim)
[ ] train --mode static --runs-per-cycle set (or legacy --episodes-per-cycle aligned to env_batch_size)
[ ] Watch JSON: session_created → progress/metrics → completed|error
[ ] Inspect stats / checkpoints
[ ] If HPs unstable after a feature change: tune → apply best_params → longer train
[ ] After a new mechanic: sim support first, then warm-start train (combo levels), then confirm
```

For subprocess wiring and event parsing patterns shared with the GUI, see [GUI-to-CLI Integration Protocol](gui_cli_protocol.md).
