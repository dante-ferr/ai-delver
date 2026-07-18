import argparse
import sys
import os

# Configure Python path using bootstrap setup (which resides in src/../)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bootstrap


def main():
    parser = argparse.ArgumentParser(description="AI Delver CLI Client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: train
    train_p = subparsers.add_parser("train", help="Starts a training session")
    train_p.add_argument("--levels", required=True, help="Comma-separated level names")
    train_p.add_argument("--cycles", type=int, default=0, help="Amount of cycles for static mode")
    train_p.add_argument(
        "--runs-per-cycle",
        type=int,
        default=None,
        help="Full-length run equivalents per cycle (preferred; server converts to episode slots)",
    )
    train_p.add_argument(
        "--episodes-per-cycle",
        type=int,
        default=None,
        help="Legacy collect-window slot budget (used when --runs-per-cycle is omitted)",
    )
    train_p.add_argument("--mode", choices=["static", "dynamic"], required=True, help="Transitioning mode")
    train_p.add_argument("--agent", required=True, help="Agent name")
    train_p.add_argument("--server", default="localhost:8001", help="Training server URL")
    train_p.add_argument("--checkpoint-interval", type=int, default=0, help="Cycle interval to save checkpoints (0 to disable)")
    train_p.add_argument("--checkpoint", default=None, help="Name or cycle number of checkpoint to load for warm-start")
    train_p.add_argument("--no-learning", action="store_true", help="Execute random actions only without gradient updates for profiling/testing")

    # Optional hyperparameter overrides
    train_p.add_argument("--learning-rate", type=float, default=None, help="Learning rate (PPO)")
    train_p.add_argument("--gamma", type=float, default=None, help="Discount factor gamma")
    train_p.add_argument("--entropy-regularization", type=float, default=None, help="Entropy regularization coefficient")
    train_p.add_argument("--not-finished-reward", type=float, default=None, help="Penalty for not finishing the level")
    train_p.add_argument("--finished-reward", type=float, default=None, help="Reward for finishing the level")
    train_p.add_argument("--turn-reward", type=float, default=None, help="Reward/penalty for turning")
    train_p.add_argument("--frame-step-reward", type=float, default=None, help="Time penalty per step")
    train_p.add_argument("--tile-exploration-reward", type=float, default=None, help="Reward for tile exploration")
    train_p.add_argument("--jump-reward", type=float, default=None, help="Penalty for jumping")
    train_p.add_argument("--wall-hugging-reward", type=float, default=None, help="Penalty for wall hugging")
    train_p.add_argument("--goal-distance-reward-scale", type=float, default=None, help="Scale factor for goal distance reward")

    # Subcommand: stats
    stats_p = subparsers.add_parser("stats", help="Calculates and prints agent stats")
    stats_p.add_argument("--agent", required=True, help="Agent name")

    # Subcommand: interrupt
    int_p = subparsers.add_parser("interrupt", help="Interrupts a running session on the server")
    int_p.add_argument("--session-id", required=True, help="Training session ID to interrupt")
    int_p.add_argument("--server", default="localhost:8001", help="Training server URL")

    # Subcommand: create-agent
    create_p = subparsers.add_parser("create-agent", help="Creates a new agent on disk")
    create_p.add_argument("--name", required=True, help="Agent name")

    # Subcommand: save-agent
    save_p = subparsers.add_parser("save-agent", help="Saves an agent on disk")
    save_p.add_argument("--name", required=True, help="Agent name")

    # Subcommand: load-agent
    load_p = subparsers.add_parser("load-agent", help="Loads an agent from a path")
    load_p.add_argument("--path", required=True, help="Path to the agent directory")

    # Subcommand: tune
    tune_p = subparsers.add_parser("tune", help="Runs automated hyperparameter tuning using Optuna")
    tune_p.add_argument("--levels", required=True, help="Comma-separated level names")
    tune_p.add_argument("--cycles", type=int, default=5, help="Cycles per trial")
    tune_p.add_argument("--episodes-per-cycle", type=int, default=32, help="Episodes per cycle")
    tune_p.add_argument("--agent", required=True, help="Agent name")
    tune_p.add_argument("--trials", type=int, default=10, help="Number of Optuna trials")
    tune_p.add_argument("--server", default="localhost:8001", help="Training server URL")

    # Subcommand: import-level-sketch
    sketch_p = subparsers.add_parser(
        "import-level-sketch",
        help="Imports a simplified level sketch JSON into a full editor level save",
    )
    sketch_p.add_argument(
        "--from",
        dest="from_path",
        required=True,
        help="Path to the level sketch JSON file",
    )
    sketch_p.add_argument(
        "--name",
        default=None,
        help="Override the saved level name (defaults to sketch name)",
    )
    sketch_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing level save with the same name",
    )

    # Subcommand: platforming-limits
    limits_p = subparsers.add_parser(
        "platforming-limits",
        help="Compute jump/gap authoring limits from runtime physics TOML configs",
    )
    limits_p.add_argument(
        "--delver-toml",
        default=None,
        help="Optional path to delver.toml (defaults to runtime/src/world_objects/delver/delver.toml)",
    )
    limits_p.add_argument(
        "--world-toml",
        default=None,
        help="Optional path to world.toml (defaults to runtime/src/engine/world.toml)",
    )

    args = parser.parse_args()

    if args.command == "train":
        if getattr(args, "runs_per_cycle", None) is None and getattr(args, "episodes_per_cycle", None) is None:
            parser.error("train requires --runs-per-cycle or --episodes-per-cycle")
        from cli.commands.train import run_train
        run_train(args)
    elif args.command == "stats":
        from cli.commands.stats import run_stats
        run_stats(args.agent)
    elif args.command == "interrupt":
        from cli.commands.interrupt import run_interrupt
        run_interrupt(args.session_id, args.server)
    elif args.command == "create-agent":
        from cli.commands.agent_create import run_create_agent
        run_create_agent(args.name)
    elif args.command == "save-agent":
        from cli.commands.agent_save import run_save_agent
        run_save_agent(args.name)
    elif args.command == "load-agent":
        from cli.commands.agent_load import run_load_agent
        run_load_agent(args.path)
    elif args.command == "tune":
        from cli.commands.tune import run_tune
        run_tune(args)
    elif args.command == "import-level-sketch":
        from cli.commands.import_level_sketch import run_import_level_sketch
        run_import_level_sketch(args)
    elif args.command == "platforming-limits":
        from cli.commands.platforming_limits import run_platforming_limits
        run_platforming_limits(args)

if __name__ == "__main__":
    main()
