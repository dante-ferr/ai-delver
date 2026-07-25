import json
import shutil
import subprocess
from pathlib import Path

import optuna


def print_json(event: str, **kwargs):
    """Utility to print a structured JSON event to stdout."""
    payload = {"event": event, **kwargs}
    print(json.dumps(payload), flush=True)


def _append_override(cmd: list[str], flag: str, value) -> None:
    if value is None:
        return
    cmd.extend([flag, str(value)])


def _run_train_subprocess(
    *,
    client_dir: Path,
    levels: str,
    cycles: int,
    episodes_per_cycle: int | None,
    agent: str,
    server: str,
    play: bool,
    overrides: dict,
    on_event=None,
) -> tuple[int, dict[str, dict]]:
    """Spawn train; return (exit_code, level_mastery_by_name)."""
    cmd = [
        "poetry",
        "run",
        "python",
        "src/cli/main.py",
        "train",
        "--levels",
        levels,
        "--cycles",
        str(cycles),
        "--mode",
        "static",
        "--agent",
        agent,
        "--server",
        server,
    ]
    if play:
        cmd.append("--play")
    elif episodes_per_cycle is not None:
        cmd.extend(["--episodes-per-cycle", str(episodes_per_cycle)])

    for key, value in overrides.items():
        flag = f"--{key.replace('_', '-')}"
        _append_override(cmd, flag, value)

    process = subprocess.Popen(
        cmd,
        cwd=client_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    level_mastery: dict[str, dict] = {}
    pruned = False

    try:
        for line in iter(process.stdout.readline, ""):
            if not line.strip():
                continue
            try:
                event_data = json.loads(line)
            except json.JSONDecodeError:
                continue

            if on_event is not None:
                on_event(event_data)

            event_type = event_data.get("event")
            if event_type == "metrics" and not play:
                loss = event_data.get("loss")
                if loss is not None and abs(loss) > 20.0:
                    print_json(
                        "info",
                        message=f"Pruning trial due to loss divergence: {loss}",
                    )
                    process.terminate()
                    pruned = True
                    break
            elif event_type == "level_mastery":
                level = event_data.get("level")
                if isinstance(level, str) and level:
                    level_mastery[level] = {
                        "victories": int(event_data.get("victories") or 0),
                        "amount": int(event_data.get("amount") or 0),
                        "win_rate": float(event_data.get("win_rate") or 0.0),
                        "play": bool(event_data.get("play")),
                    }
            elif event_type == "error":
                print_json(
                    "info",
                    message=f"Child train error: {event_data.get('message')}",
                )
    finally:
        process.wait()

    if pruned:
        raise optuna.exceptions.TrialPruned()

    return process.returncode or 0, level_mastery


def _reset_trial_agent(agent_name: str) -> None:
    """Ensure each Optuna trial starts from a blank agent directory."""
    from agent.config import AGENT_SAVE_FOLDER_PATH

    agent_dir = Path(AGENT_SAVE_FOLDER_PATH) / agent_name
    if agent_dir.exists():
        shutil.rmtree(agent_dir)
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / ".tune_blank").write_text("blank trial agent\n", encoding="utf-8")


def _mastery_score(
    level_names: list[str],
    mastery: dict[str, dict],
    threshold: float,
    tail_k: int = 3,
) -> tuple[float, float, float, dict]:
    """Return (optuna_score, min_wr, mean_wr, detail).

    Optuna maximizes the mean of the ``tail_k`` lowest per-level win rates so a
    single noisy showcase does not dominate, while promotion still keys off min.
    Missing levels count as 0.0.
    """
    rates = []
    detail = {}
    for name in level_names:
        entry = mastery.get(name) or {}
        wr = float(entry.get("win_rate") or 0.0)
        rates.append(wr)
        detail[name] = {
            "win_rate": wr,
            "victories": entry.get("victories", 0),
            "amount": entry.get("amount", 0),
            "meets_threshold": wr >= threshold,
        }
    if not rates:
        return 0.0, 0.0, 0.0, detail
    min_wr = min(rates)
    mean_wr = sum(rates) / len(rates)
    k = max(1, min(int(tail_k), len(rates)))
    worst = sorted(rates)[:k]
    optuna_score = sum(worst) / len(worst)
    return optuna_score, min_wr, mean_wr, detail


def run_tune(args):
    """Executes a hyperparameter search using Optuna with sequential mastery scoring."""
    print_json(
        "info",
        message=(
            f"Starting Optuna sequential-mastery study with {args.trials} trials "
            f"(eval_runs={args.eval_runs}, mastery_threshold={args.mastery_threshold}, "
            f"tail_k={getattr(args, 'tail_k', 3)}, "
            f"tune_architecture={bool(getattr(args, 'tune_architecture', False))})."
        ),
    )

    client_dir = Path(__file__).resolve().parents[3]
    level_names = [level.strip() for level in args.levels.split(",") if level.strip()]
    if not level_names:
        print_json("error", message="No valid levels provided to tune.")
        return

    tune_architecture = bool(getattr(args, "tune_architecture", False))
    mastery_threshold = float(getattr(args, "mastery_threshold", 0.8))
    eval_runs = max(1, int(getattr(args, "eval_runs", 15)))
    tail_k = max(1, int(getattr(args, "tail_k", 3)))
    if tune_architecture:
        print_json(
            "info",
            message=(
                "Architecture search enabled — prefer this as a second pass after "
                "rewards / LR / entropy have stabilized without --tune-architecture."
            ),
        )

    def objective(trial: optuna.Trial) -> float:
        learning_rate = trial.suggest_float("learning_rate", 5e-5, 8e-4, log=True)
        entropy_reg = trial.suggest_float("entropy_reg", 0.01, 0.20)
        finished_reward = trial.suggest_float("finished_reward", 80.0, 250.0)
        jump_reward = trial.suggest_float("jump_reward", -3.0, -0.05)
        goal_distance_reward_scale = trial.suggest_float(
            "goal_distance_reward_scale", 0.005, 0.05
        )
        turn_reward = trial.suggest_float("turn_reward", -0.5, 0.0)
        tile_exploration_reward = trial.suggest_float(
            "tile_exploration_reward", 0.05, 0.30
        )
        wall_hugging_reward = trial.suggest_float("wall_hugging_reward", -0.05, 0.0)

        overrides = {
            "learning_rate": f"{learning_rate:.6f}",
            "entropy_regularization": f"{entropy_reg:.4f}",
            "finished_reward": f"{finished_reward:.2f}",
            "jump_reward": f"{jump_reward:.2f}",
            "goal_distance_reward_scale": f"{goal_distance_reward_scale:.4f}",
            "turn_reward": f"{turn_reward:.2f}",
            "tile_exploration_reward": f"{tile_exploration_reward:.4f}",
            "wall_hugging_reward": f"{wall_hugging_reward:.4f}",
        }

        if tune_architecture:
            overrides["ppo_num_epochs"] = trial.suggest_categorical(
                "ppo_num_epochs", [2, 4, 6, 8]
            )
            overrides["value_coefficient"] = (
                f"{trial.suggest_float('value_coefficient', 0.25, 1.0):.4f}"
            )
            overrides["minibatch_size"] = trial.suggest_categorical(
                "minibatch_size", [128, 256, 384, 512]
            )
            overrides["local_feature_dim"] = trial.suggest_categorical(
                "local_feature_dim", [128, 256, 384]
            )
            overrides["lstm_hidden_size"] = trial.suggest_categorical(
                "lstm_hidden_size", [64, 128, 256]
            )
            overrides["mlp_hidden_dim"] = trial.suggest_categorical(
                "mlp_hidden_dim", [128, 256, 384]
            )

        trial_agent = f"{args.agent}_trial_{trial.number}"
        _reset_trial_agent(trial_agent)

        print_json(
            "info",
            message=(
                f"Starting Trial {trial.number} on agent '{trial_agent}' "
                f"with overrides={overrides}"
            ),
        )

        # 1) Sequential curriculum train (weight inheritance within the trial).
        train_code, _ = _run_train_subprocess(
            client_dir=client_dir,
            levels=args.levels,
            cycles=args.cycles,
            episodes_per_cycle=args.episodes_per_cycle,
            agent=trial_agent,
            server=args.server,
            play=False,
            overrides=overrides,
        )
        if train_code != 0:
            print_json(
                "info",
                message=(
                    f"Trial {trial.number} train exited with code {train_code}; scoring 0."
                ),
            )
            return 0.0

        # 2) Final curriculum mastery eval (argmax play across all levels).
        print_json(
            "info",
            message=(
                f"Trial {trial.number}: running mastery play eval "
                f"({eval_runs} run(s) × {len(level_names)} levels)."
            ),
        )
        eval_code, mastery = _run_train_subprocess(
            client_dir=client_dir,
            levels=args.levels,
            cycles=eval_runs,
            episodes_per_cycle=None,
            agent=trial_agent,
            server=args.server,
            play=True,
            overrides={},
        )
        if eval_code != 0:
            print_json(
                "info",
                message=(
                    f"Trial {trial.number} mastery eval exited with code {eval_code}; "
                    "scoring 0."
                ),
            )
            return 0.0

        # Prefer play-tagged mastery rows when both train and play emitted events.
        play_mastery = {
            name: data for name, data in mastery.items() if data.get("play")
        }
        score_source = play_mastery if play_mastery else mastery
        optuna_score, min_wr, mean_wr, detail = _mastery_score(
            level_names, score_source, mastery_threshold, tail_k=tail_k
        )
        meets = all(row["meets_threshold"] for row in detail.values()) and bool(detail)

        print_json(
            "info",
            message=(
                f"Finished Trial {trial.number}: optuna_score(tail_k={tail_k})={optuna_score:.4f}, "
                f"min_win_rate={min_wr:.4f}, mean_win_rate={mean_wr:.4f}, "
                f"mastery_met={meets}, per_level={detail}"
            ),
        )
        trial.set_user_attr("per_level_mastery", detail)
        trial.set_user_attr("mastery_met", meets)
        trial.set_user_attr("min_win_rate", min_wr)
        trial.set_user_attr("mean_win_rate", mean_wr)
        trial.set_user_attr("trial_agent", trial_agent)
        return optuna_score

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=args.trials)

    best_detail = study.best_trial.user_attrs.get("per_level_mastery", {})
    best_met = bool(study.best_trial.user_attrs.get("mastery_met", False))
    best_min = float(study.best_trial.user_attrs.get("min_win_rate", 0.0) or 0.0)
    best_mean = float(study.best_trial.user_attrs.get("mean_win_rate", 0.0) or 0.0)
    print_json(
        "completed",
        best_params=study.best_params,
        best_value=study.best_value,
        best_min_win_rate=best_min,
        best_mean_win_rate=best_mean,
        mastery_threshold=mastery_threshold,
        mastery_met=best_met,
        tail_k=tail_k,
        per_level_mastery=best_detail,
        message=(
            "Hyperparameter tuning study completed "
            f"(best tail-{tail_k} mean={study.best_value:.4f}, "
            f"min={best_min:.4f}, mean={best_mean:.4f}; "
            f"{'meets' if best_met else 'below'} mastery threshold {mastery_threshold})."
        ),
    )
