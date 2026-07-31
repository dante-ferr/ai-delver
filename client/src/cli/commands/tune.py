import json
import shutil
import subprocess
from pathlib import Path

import optuna

from src.cli.commands.review_planner import (
    DEFAULT_REVIEW_EPISODES_PER_LEVEL,
    DEFAULT_REVIEW_LEVELS_PER_ARM,
)
from src.config import config


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
    review_knobs: dict | None = None,
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

    if review_knobs and not play:
        for key, value in review_knobs.items():
            if value is None:
                continue
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
            # Surface curriculum/review lifecycle from child train into the tune log.
            if event_type in {"training_phase", "review_plan"} or (
                event_type == "info"
                and isinstance(event_data.get("message"), str)
                and (
                    "Applied review knobs" in event_data["message"]
                    or "Updated curriculum after model weights" in event_data["message"]
                    or "Review phase" in event_data["message"]
                    or "review" in event_data["message"].lower()
                )
            ):
                print(json.dumps(event_data), flush=True)

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
                        "mean_jumps": float(event_data.get("mean_jumps") or 0.0),
                        "max_jumps": int(event_data.get("max_jumps") or 0),
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
    *,
    polish_jumps: bool = False,
) -> tuple[float, float, float, float, float, dict]:
    """Return (optuna_score, tail_mean, min_wr, mean_wr, pack_mean_jumps, detail).

    Default Optuna maximizes a lexicographic WR scalar:
    ``tail_k_mean + 1e-3 * min_wr + 1e-6 * mean_wr``.

    When ``polish_jumps`` is true (``--tune-ej-only`` Stage B):
    - if any level is below mastery threshold → near-zero score (infeasible);
    - else maximize ``1.0 - pack_mean_jumps / (1 + pack_mean_jumps)`` plus tiny WR lex
      so fewer takeoffs win among masters.
    """
    rates = []
    jumps = []
    detail = {}
    for name in level_names:
        entry = mastery.get(name) or {}
        wr = float(entry.get("win_rate") or 0.0)
        mean_jumps = float(entry.get("mean_jumps") or 0.0)
        rates.append(wr)
        jumps.append(mean_jumps)
        detail[name] = {
            "win_rate": wr,
            "victories": entry.get("victories", 0),
            "amount": entry.get("amount", 0),
            "mean_jumps": mean_jumps,
            "max_jumps": entry.get("max_jumps", 0),
            "meets_threshold": wr >= threshold,
        }
    if not rates:
        return 0.0, 0.0, 0.0, 0.0, 0.0, detail
    min_wr = min(rates)
    mean_wr = sum(rates) / len(rates)
    pack_mean_jumps = sum(jumps) / len(jumps)
    k = max(1, min(int(tail_k), len(rates)))
    worst = sorted(rates)[:k]
    tail_mean = sum(worst) / len(worst)
    meets = all(row["meets_threshold"] for row in detail.values())

    if polish_jumps:
        if not meets:
            # Keep a tiny WR signal so partial clears still rank above total washouts.
            optuna_score = 1e-3 * tail_mean + 1e-6 * min_wr + 1e-9 * mean_wr
        else:
            # Map takeoffs into (0, 1]: 0 jumps → 1.0; more jumps → lower.
            neatness = 1.0 / (1.0 + pack_mean_jumps)
            optuna_score = (
                1.0
                + neatness
                + 1e-3 * min_wr
                + 1e-6 * mean_wr
            )
    else:
        optuna_score = tail_mean + 1e-3 * min_wr + 1e-6 * mean_wr
    return optuna_score, tail_mean, min_wr, mean_wr, pack_mean_jumps, detail


def _consolidation_levels(level_names: list[str], consolidate_csv: str) -> list[str]:
    """Filter consolidation targets to levels present in the curriculum."""
    from utils.level_groups import expand_level_list

    requested = expand_level_list(
        [level.strip() for level in consolidate_csv.split(",") if level.strip()]
    )
    present = set(level_names)
    return [name for name in requested if name in present]


def run_tune(args):
    """Executes a hyperparameter search using Optuna with sequential mastery scoring."""
    from utils.level_groups import expand_level_list

    client_dir = Path(__file__).resolve().parents[3]
    level_names = expand_level_list(
        [level.strip() for level in args.levels.split(",") if level.strip()]
    )
    if not level_names:
        print_json("error", message="No valid levels provided to tune.")
        return
    # Subprocess train calls reuse the expanded CSV so @groups are not re-parsed there.
    args.levels = ",".join(level_names)

    tune_architecture = bool(getattr(args, "tune_architecture", False))
    tune_ej_only = bool(getattr(args, "tune_ej_only", False))
    if tune_architecture and tune_ej_only:
        print_json(
            "error",
            message="Cannot combine --tune-architecture with --tune-ej-only.",
        )
        return
    mastery_threshold = float(getattr(args, "mastery_threshold", 0.8))
    eval_runs = max(1, int(getattr(args, "eval_runs", 15)))
    tail_k = max(1, int(getattr(args, "tail_k", 3)))
    consolidate_csv = str(
        getattr(args, "consolidate_levels", "")
        or ""
    )
    consolidate_names = _consolidation_levels(level_names, consolidate_csv)
    consolidation_cycles_arg = getattr(args, "consolidation_cycles", None)
    if consolidation_cycles_arg is None:
        consolidation_cycles = max(10, int(args.cycles) // 2)
    else:
        consolidation_cycles = max(1, int(consolidation_cycles_arg))

    review_knobs = {
        "focus_episodes_between_passes": getattr(
            args,
            "focus_episodes_between_passes",
            int(config.REVIEW.TUNE_FOCUS_EPISODES_BETWEEN_PASSES),
        ),
        "review_episodes_per_level": getattr(
            args,
            "review_episodes_per_level",
            DEFAULT_REVIEW_EPISODES_PER_LEVEL,
        ),
        "review_levels_per_arm": getattr(
            args,
            "review_levels_per_arm",
            DEFAULT_REVIEW_LEVELS_PER_ARM,
        ),
    }

    print_json(
        "info",
        message=(
            f"Starting Optuna sequential-mastery study with {args.trials} trials "
            f"(eval_runs={eval_runs}, mastery_threshold={mastery_threshold}, "
            f"tail_k={tail_k}, tune_architecture={tune_architecture}, "
            f"tune_ej_only={tune_ej_only}, "
            f"review_E={review_knobs['focus_episodes_between_passes']}, "
            f"review_R={review_knobs['review_episodes_per_level']}, "
            f"review_K={review_knobs['review_levels_per_arm']})."
        ),
    )

    if consolidate_names:
        print_json(
            "info",
            message=(
                f"Rise consolidation enabled after curriculum: levels={consolidate_names}, "
                f"cycles={consolidation_cycles}."
            ),
        )
    else:
        print_json("info", message="Rise consolidation disabled (no matching levels).")

    if tune_ej_only:
        print_json(
            "info",
            message=(
                "E+J-only Stage B (secondary): Optuna varies tile_exploration_reward and "
                "jump_reward; scores mastery lock then minimizes pack mean takeoffs. "
                "Prefer discovery-safe J; primary neatness is lock + post-clear jump anneal. "
                "Other HPs remain at intelligence server/config defaults."
            ),
        )

    if tune_architecture:
        print_json(
            "info",
            message=(
                "Architecture search enabled — prefer this as a second pass after "
                "rewards / LR / entropy have stabilized without --tune-architecture."
            ),
        )

    def objective(trial: optuna.Trial) -> float:
        # Per-tile explore rates are ~8× smaller than the old boolean step bonus.
        jump_reward = trial.suggest_float("jump_reward", -3.0, -0.05)
        tile_exploration_reward = trial.suggest_float(
            "tile_exploration_reward", 0.005, 0.08
        )

        if tune_ej_only:
            overrides = {
                "jump_reward": f"{jump_reward:.2f}",
                "tile_exploration_reward": f"{tile_exploration_reward:.4f}",
            }
        else:
            learning_rate = trial.suggest_float("learning_rate", 5e-5, 8e-4, log=True)
            entropy_reg = trial.suggest_float("entropy_reg", 0.01, 0.20)
            finished_reward = trial.suggest_float("finished_reward", 80.0, 250.0)
            goal_distance_reward_scale = trial.suggest_float(
                "goal_distance_reward_scale", 0.005, 0.05
            )
            turn_reward = trial.suggest_float("turn_reward", -0.5, 0.0)
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
            review_knobs=review_knobs,
        )
        if train_code != 0:
            print_json(
                "info",
                message=(
                    f"Trial {trial.number} train exited with code {train_code}; scoring 0."
                ),
            )
            return 0.0

        # 2) Rise consolidation: re-focus mid-pack rises before play eval.
        if consolidate_names:
            print_json(
                "info",
                message=(
                    f"Trial {trial.number}: consolidating rises "
                    f"{consolidate_names} for {consolidation_cycles} cycle(s)."
                ),
            )
            consol_code, _ = _run_train_subprocess(
                client_dir=client_dir,
                levels=",".join(consolidate_names),
                cycles=consolidation_cycles,
                episodes_per_cycle=args.episodes_per_cycle,
                agent=trial_agent,
                server=args.server,
                play=False,
                overrides=overrides,
                review_knobs=review_knobs,
            )
            if consol_code != 0:
                print_json(
                    "info",
                    message=(
                        f"Trial {trial.number} consolidation exited with code "
                        f"{consol_code}; scoring 0."
                    ),
                )
                return 0.0

        # 3) Final curriculum mastery eval (argmax play across all levels).
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
        optuna_score, tail_mean, min_wr, mean_wr, pack_mean_jumps, detail = _mastery_score(
            level_names,
            score_source,
            mastery_threshold,
            tail_k=tail_k,
            polish_jumps=tune_ej_only,
        )
        meets = all(row["meets_threshold"] for row in detail.values()) and bool(detail)

        print_json(
            "info",
            message=(
                f"Finished Trial {trial.number}: "
                f"optuna_score={optuna_score:.6f} "
                f"(tail_k={tail_k} mean={tail_mean:.4f} + lex"
                f"{', polish_jumps' if tune_ej_only else ''}), "
                f"min_win_rate={min_wr:.4f}, mean_win_rate={mean_wr:.4f}, "
                f"pack_mean_jumps={pack_mean_jumps:.4f}, "
                f"mastery_met={meets}, per_level={detail}"
            ),
        )
        trial.set_user_attr("per_level_mastery", detail)
        trial.set_user_attr("mastery_met", meets)
        trial.set_user_attr("min_win_rate", min_wr)
        trial.set_user_attr("mean_win_rate", mean_wr)
        trial.set_user_attr("pack_mean_jumps", pack_mean_jumps)
        trial.set_user_attr("tail_mean", tail_mean)
        trial.set_user_attr("trial_agent", trial_agent)
        return optuna_score

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=args.trials)

    best_detail = study.best_trial.user_attrs.get("per_level_mastery", {})
    best_met = bool(study.best_trial.user_attrs.get("mastery_met", False))
    best_min = float(study.best_trial.user_attrs.get("min_win_rate", 0.0) or 0.0)
    best_mean = float(study.best_trial.user_attrs.get("mean_win_rate", 0.0) or 0.0)
    best_tail = float(study.best_trial.user_attrs.get("tail_mean", 0.0) or 0.0)
    best_jumps = float(study.best_trial.user_attrs.get("pack_mean_jumps", 0.0) or 0.0)
    print_json(
        "completed",
        best_params=study.best_params,
        best_value=study.best_value,
        best_tail_mean=best_tail,
        best_min_win_rate=best_min,
        best_mean_win_rate=best_mean,
        best_pack_mean_jumps=best_jumps,
        mastery_threshold=mastery_threshold,
        mastery_met=best_met,
        polish_jumps=tune_ej_only,
        tail_k=tail_k,
        consolidate_levels=consolidate_names,
        consolidation_cycles=consolidation_cycles if consolidate_names else 0,
        review_knobs=review_knobs,
        per_level_mastery=best_detail,
        message=(
            "Hyperparameter tuning study completed "
            f"(best score={study.best_value:.6f}, tail-{tail_k}={best_tail:.4f}, "
            f"min={best_min:.4f}, mean={best_mean:.4f}, "
            f"pack_mean_jumps={best_jumps:.4f}; "
            f"{'meets' if best_met else 'below'} mastery threshold {mastery_threshold})."
        ),
    )
