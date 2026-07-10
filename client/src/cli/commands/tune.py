import subprocess
import json
import os
import sys
import optuna
from pathlib import Path

def print_json(event: str, **kwargs):
    """Utility to print a structured JSON event to stdout."""
    payload = {"event": event, **kwargs}
    print(json.dumps(payload), flush=True)

def run_tune(args):
    """Executes a hyperparameter search using Optuna."""
    print_json("info", message=f"Starting Optuna hyperparameter study with {args.trials} trials...")

    # We want to run from the root client folder
    client_dir = Path(__file__).resolve().parents[3]

    def objective(trial):
        # 1. Suggest hyperparameters
        learning_rate = trial.suggest_float("learning_rate", 5e-5, 8e-4, log=True)
        entropy_reg = trial.suggest_float("entropy_reg", 0.05, 0.30)
        finished_reward = trial.suggest_float("finished_reward", 50.0, 200.0)

        print_json("info", message=f"Starting Trial {trial.number}: learning_rate={learning_rate:.6f}, entropy_reg={entropy_reg:.4f}, finished_reward={finished_reward:.2f}")

        # 2. Build training command
        cmd = [
            "poetry", "run", "python", "src/cli/main.py", "train",
            "--levels", args.levels,
            "--cycles", str(args.cycles),
            "--episodes-per-cycle", str(args.episodes_per_cycle),
            "--mode", "static",
            "--agent", args.agent,
            "--server", args.server,
            "--learning-rate", f"{learning_rate:.6f}",
            "--entropy-regularization", f"{entropy_reg:.4f}",
            "--finished-reward", f"{finished_reward:.2f}"
        ]

        # 3. Spawn training subprocess
        process = subprocess.Popen(
            cmd,
            cwd=client_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        final_win_rate = 0.0

        try:
            # 4. Stream and parse JSON output from the training subprocess
            for line in iter(process.stdout.readline, ""):
                if not line.strip():
                    continue
                try:
                    event_data = json.loads(line)
                    event_type = event_data.get("event")

                    if event_type == "metrics":
                        loss = event_data.get("loss")
                        if loss is not None and abs(loss) > 20.0:
                            # Prune trial early if loss has collapsed / diverged
                            print_json("info", message=f"Pruning Trial {trial.number} due to loss divergence: {loss}")
                            process.terminate()
                            raise optuna.exceptions.TrialPruned()

                    elif event_type == "stats":
                        stats = event_data.get("stats", {})
                        victories = stats.get("victories", 0)
                        amount = stats.get("amount", 1)
                        final_win_rate = victories / amount

                except json.JSONDecodeError:
                    continue

        except optuna.exceptions.TrialPruned:
            raise
        except Exception as e:
            print_json("error", message=f"Error during Trial {trial.number} execution: {e}")
            process.terminate()
        finally:
            process.wait()

        print_json("info", message=f"Finished Trial {trial.number} with win rate: {final_win_rate:.4f}")
        return final_win_rate

    # Create and optimize study
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=args.trials)

    print_json("completed", best_params=study.best_params, best_value=study.best_value, message="Hyperparameter tuning study completed.")
