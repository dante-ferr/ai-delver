import argparse
import sys
import os

# Configure Python path using bootstrap setup (which resides in src/../)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bootstrap

from cli.commands.train import run_train
from cli.commands.stats import run_stats
from cli.commands.interrupt import run_interrupt

def main():
    parser = argparse.ArgumentParser(description="AI Delver CLI Client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: train
    train_p = subparsers.add_parser("train", help="Starts a training session")
    train_p.add_argument("--levels", required=True, help="Comma-separated level names")
    train_p.add_argument("--cycles", type=int, default=0, help="Amount of cycles for static mode")
    train_p.add_argument("--episodes-per-cycle", type=int, required=True, help="Episodes per cycle")
    train_p.add_argument("--mode", choices=["static", "dynamic"], required=True, help="Transitioning mode")
    train_p.add_argument("--agent", required=True, help="Agent name")
    train_p.add_argument("--server", default="localhost:8001", help="Training server URL")

    # Subcommand: stats
    stats_p = subparsers.add_parser("stats", help="Calculates and prints agent stats")
    stats_p.add_argument("--agent", required=True, help="Agent name")

    # Subcommand: interrupt
    int_p = subparsers.add_parser("interrupt", help="Interrupts a running session on the server")
    int_p.add_argument("--session-id", required=True, help="Training session ID to interrupt")
    int_p.add_argument("--server", default="localhost:8001", help="Training server URL")

    args = parser.parse_args()

    if args.command == "train":
        run_train(args)
    elif args.command == "stats":
        run_stats(args.agent)
    elif args.command == "interrupt":
        run_interrupt(args.session_id, args.server)

if __name__ == "__main__":
    main()
