#!/usr/bin/env python3
"""
Standalone CLI client for executing AI Delver training sessions.
It uses the modular TrainingClient class under the hood to manage
network requests, and handles event callbacks by logging JSON lines to stdout.
"""

import sys
import os
import argparse
import asyncio
import json
import time
import signal

# Configure Python path using bootstrap setup
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bootstrap

from client_requests.training_client import TrainingClient

# Global container for signal handler / graceful interrupt
client_instance = None
session_id = None
interrupted = False

def print_json(event: str, **kwargs):
    """Utility to print a structured JSON event to stdout."""
    payload = {"event": event, **kwargs}
    print(json.dumps(payload), flush=True)

async def interrupt_training():
    """Sends the interrupt request to the training server if a session is active."""
    global interrupted
    if client_instance and session_id:
        if interrupted:
            return
        interrupted = True
        print_json("interrupt_started", message="Sending interrupt request to training server...")
        try:
            response = await client_instance.interrupt_training(session_id)
            if response.get("success"):
                print_json("interrupted", message="Training successfully interrupted.")
            else:
                print_json("error", message=f"Server returned error on interrupt: {response.get('message')}")
        except Exception as e:
            print_json("error", message=f"Failed to interrupt training: {e}")

def raise_keyboard_interrupt(signum, frame):
    """Raises KeyboardInterrupt to bubble up through the running asyncio loop."""
    raise KeyboardInterrupt()

# Register system signals for graceful shutdown
signal.signal(signal.SIGINT, raise_keyboard_interrupt)
signal.signal(signal.SIGTERM, raise_keyboard_interrupt)

async def main_async(args):
    global client_instance, session_id
    
    client_instance = TrainingClient(server_url=args.server)
    
    levels_list = [l.strip() for l in args.levels.split(",") if l.strip()]
    if not levels_list:
        print_json("error", message="No valid levels provided.")
        sys.exit(1)
        
    try:
        init_data = await client_instance.get_initial_info()
        env_batch_size = init_data.get("env_batch_size", 32)
    except Exception as e:
        print_json("error", message=f"Failed to connect to training server at {args.server}: {e}")
        sys.exit(1)
        
    remainder = args.episodes_per_cycle % env_batch_size
    if remainder != 0:
        adjusted = max(env_batch_size, round(args.episodes_per_cycle / env_batch_size) * env_batch_size)
        print_json("info", message=f"Adjusted episodes-per-cycle from {args.episodes_per_cycle} to {adjusted} to align with env_batch_size ({env_batch_size}) constraints.")
        args.episodes_per_cycle = adjusted

    print_json("init_started", message="Preparing levels and verifying configuration...")
    try:
        client_instance.ensure_levels_saved(levels_list, args.agent)
    except Exception as e:
        print_json("error", message=f"Failed to prepare levels: {e}")
        sys.exit(1)

    payload = client_instance.create_training_payload(levels_list, args.episodes_per_cycle, args.mode, args.cycles)
    
    print_json("request_sent", message=f"Sending training request to http://{args.server}/train...")
    try:
        response = await client_instance.submit_training(payload)
    except Exception as e:
        print_json("error", message=f"Failed to connect to training server: {e}")
        sys.exit(1)
            
    session_id = response.get("session_id")
    if not session_id:
        print_json("error", message="No session_id received from server.")
        sys.exit(1)
        
    print_json("session_created", session_id=session_id, message="Training session started successfully.")
    
    start_time = time.time()
    current_cycle = 0
    completed_normally = False
    
    # Callback handlers for websocket stream
    async def on_trajectory(trajectory, level_episode_count):
        nonlocal current_cycle
        if trajectory:
            await trajectory.save(args.agent)
        current_cycle += 1
        print_json("progress", cycle=current_cycle, level_episode_count=level_episode_count, message=f"Completed cycle {current_cycle}")

    def on_level_transition(levels_trained):
        print_json("level_transition", levels_trained=levels_trained, message="Transitioned to next level.")

    def on_completed():
        nonlocal completed_normally
        duration = time.time() - start_time
        print_json("completed", duration=f"{duration:.2f}s", message="Training completed successfully.")
        completed_normally = True

    def on_error(err):
        print_json("error", message=err)

    try:
        await client_instance.listen_to_trajectory(
            session_id=session_id,
            on_trajectory=on_trajectory,
            on_level_transition=on_level_transition,
            on_completed=on_completed,
            on_error=on_error
        )
    except Exception as e:
        print_json("error", message=f"WebSocket stream error: {e}")
    finally:
        if not completed_normally:
            await interrupt_training()

        # Calculate final stats locally to update metadata.json and output to stdout
        try:
            from runtime.episode_trajectory import TrajectoryStatsCalculator
            calculator = TrajectoryStatsCalculator(args.agent)
            stats = await calculator.get_stats()
            print_json(
                "stats",
                amount=stats.get("amount", 0),
                victories=stats.get("victories", 0),
                message=f"Final stats: {stats.get('victories', 0)} victories out of {stats.get('amount', 0)} episodes."
            )
        except Exception as e:
            print_json("error", message=f"Failed to calculate stats: {e}")

def main():
    parser = argparse.ArgumentParser(description="AI Delver CLI Training Client")
    parser.add_argument("--levels", required=True, help="Comma-separated level names")
    parser.add_argument("--cycles", type=int, default=0, help="Amount of cycles for static mode")
    parser.add_argument("--episodes-per-cycle", type=int, required=True, help="Episodes per cycle")
    parser.add_argument("--mode", choices=["static", "dynamic"], required=True, help="Transitioning mode")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--server", default="localhost:8001", help="Training server URL")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        # Graceful interrupt handling in main_async's finally block has run/is running,
        # so we catch the KeyboardInterrupt here to exit cleanly.
        pass

if __name__ == "__main__":
    main()
