import asyncio
import json
import time
import signal
import logging
from client_requests.training_client import TrainingClient
from runtime.episode_trajectory import EpisodeTrajectoryFactory
from .stats import run_stats
from .nerd_stats_persistence import save_nerd_stats

# Global container for signal handler / graceful interrupt
client_instance = None
session_id = None
interrupted = False
completed_normally = False

def print_json(event: str, **kwargs):
    """Utility to print a structured JSON event to stdout."""
    payload = {"event": event, **kwargs}
    print(json.dumps(payload), flush=True)

async def interrupt_training(server_url: str):
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
                print_json("error", message=f"Server error on interrupt: {response.get('message')}")
        except Exception as e:
            print_json("error", message=f"Failed to interrupt training: {e}")

def raise_keyboard_interrupt(signum, frame):
    """Raises KeyboardInterrupt to bubble up through the running asyncio loop."""
    raise KeyboardInterrupt()

def run_train(args):
    """Executes a training session, streaming trajectories, and calculating final stats on exit."""
    global client_instance, session_id, interrupted, completed_normally
    interrupted = False
    completed_normally = False

    # Accumulated nerd stats (reset each run)
    nerd_step_history: list = []
    nerd_loss_history: list = []
    nerd_return_history: list = []

    # Register system signals for graceful shutdown
    signal.signal(signal.SIGINT, raise_keyboard_interrupt)
    signal.signal(signal.SIGTERM, raise_keyboard_interrupt)

    async def train_async():
        global client_instance, session_id, completed_normally
        client_instance = TrainingClient(server_url=args.server)

        levels_list = [l.strip() for l in args.levels.split(",") if l.strip()]
        if not levels_list:
            print_json("error", message="No valid levels provided.")
            return

        try:
            init_data = await client_instance.get_initial_info()
            env_batch_size = init_data.get("env_batch_size", 32)
        except Exception as e:
            print_json("error", message=f"Failed to connect to training server at {args.server}: {e}")
            return

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
            return

        # Load existing agent weights if present
        from agent.agent import Agent
        agent_obj = Agent(args.agent)
        
        # Resolve weights path
        weights_to_load = None
        if args.checkpoint:
            checkpoint_name = str(args.checkpoint)
            if not checkpoint_name.endswith(".zip"):
                # Try both 'cycle_{N}.zip' (if integer) and '{name}.zip'
                if checkpoint_name.isdigit():
                    possible_paths = [
                        agent_obj.weights_path.parent / "checkpoints" / f"cycle_{checkpoint_name}.zip",
                        agent_obj.weights_path.parent / "checkpoints" / f"{checkpoint_name}.zip",
                    ]
                else:
                    possible_paths = [
                        agent_obj.weights_path.parent / "checkpoints" / f"{checkpoint_name}.zip",
                        agent_obj.weights_path.parent / "checkpoints" / checkpoint_name,
                    ]
            else:
                possible_paths = [
                    agent_obj.weights_path.parent / "checkpoints" / checkpoint_name,
                ]

            for path in possible_paths:
                if path.is_file():
                    weights_to_load = path
                    break

            if not weights_to_load:
                print_json("error", message=f"Specified checkpoint '{args.checkpoint}' not found.")
                return
        else:
            # Default to latest weights
            if agent_obj.weights_path and agent_obj.weights_path.is_file():
                weights_to_load = agent_obj.weights_path

        # Load weights bytes
        model_bytes_b64 = None
        if weights_to_load and weights_to_load.is_file():
            import base64
            try:
                with open(weights_to_load, "rb") as f:
                    model_bytes_b64 = base64.b64encode(f.read()).decode("utf-8")
                print_json("info", message=f"Loaded policy weights from '{weights_to_load.name}' for warm-start.")
            except Exception as e:
                print_json("info", message=f"Failed to read weights from '{weights_to_load}': {e}")

        standard_keys = {"levels", "cycles", "episodes_per_cycle", "mode", "agent", "server", "command", "checkpoint"}
        config_overrides = {
            key: val for key, val in vars(args).items()
            if key not in standard_keys and val is not None
        }

        payload = client_instance.create_training_payload(
            levels_list,
            args.episodes_per_cycle,
            args.mode,
            args.cycles,
            config_overrides=config_overrides if config_overrides else None,
            model_bytes_b64=model_bytes_b64
        )

        print_json("request_sent", message=f"Sending training request to http://{args.server}/train...")
        try:
            response = await client_instance.submit_training(payload)
        except Exception as e:
            print_json("error", message=f"Failed to connect to training server: {e}")
            return

        session_id = response.get("session_id")
        if not session_id:
            print_json("error", message="No session_id received from server.")
            return

        print_json("session_created", session_id=session_id, message="Training session started successfully.")

        start_time = time.time()
        current_cycle = 0

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
            global completed_normally
            duration = time.time() - start_time
            print_json("completed", duration=f"{duration:.2f}s", message="Training completed successfully.")
            completed_normally = True

        def on_error(err):
            print_json("error", message=err)

        def on_metrics(step, loss, average_return, episodes):
            if step is not None:
                nerd_step_history.append(step)
                nerd_loss_history.append(round(loss, 6) if loss is not None else 0.0)
                nerd_return_history.append(round(average_return, 4) if average_return is not None else 0.0)
            print_json(
                "metrics",
                step=step,
                loss=round(loss, 6) if loss is not None else None,
                average_return=round(average_return, 4) if average_return is not None else None,
                episodes=episodes,
            )

        async def on_model_weights(model_bytes_b64):
            if model_bytes_b64:
                import base64
                try:
                    weights_data = base64.b64decode(model_bytes_b64)
                    # Re-instantiate agent_obj to ensure save paths exist
                    agent_obj = Agent(args.agent)
                    if agent_obj.weights_path:
                        agent_obj.weights_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(agent_obj.weights_path, "wb") as f:
                            f.write(weights_data)
                        print_json("info", message="Successfully saved downloaded model weights from server.")
                except Exception as e:
                    print_json("error", message=f"Failed to save downloaded model weights: {e}")

        async def on_checkpoint(cycle, model_bytes_b64):
            if model_bytes_b64:
                import base64
                try:
                    weights_data = base64.b64decode(model_bytes_b64)
                    agent_obj = Agent(args.agent)
                    if agent_obj.weights_path:
                        checkpoint_dir = agent_obj.weights_path.parent / "checkpoints"
                        checkpoint_dir.mkdir(parents=True, exist_ok=True)
                        checkpoint_path = checkpoint_dir / f"cycle_{cycle}.zip"
                        with open(checkpoint_path, "wb") as f:
                            f.write(weights_data)
                        print_json("info", message=f"Successfully saved checkpoint for cycle {cycle}.")
                except Exception as e:
                    print_json("error", message=f"Failed to save checkpoint for cycle {cycle}: {e}")

        try:
            await client_instance.listen_to_trajectory(
                session_id=session_id,
                on_trajectory=on_trajectory,
                on_level_transition=on_level_transition,
                on_completed=on_completed,
                on_error=on_error,
                on_metrics=on_metrics,
                on_model_weights=on_model_weights,
                on_checkpoint=on_checkpoint,
            )
        except Exception as e:
            print_json("error", message=f"WebSocket stream error: {e}")
        finally:
            if not completed_normally:
                await interrupt_training(args.server)

    try:
        asyncio.run(train_async())
    except KeyboardInterrupt:
        pass
    finally:
        # Calculate final stats locally to update metadata.json and output to stdout
        try:
            run_stats(args.agent)
        except Exception as e:
            print_json("error", message=f"Failed to calculate final stats: {e}")
        # Persist nerd stats so the Nerd Stats window has data on next session
        if nerd_loss_history:
            try:
                save_nerd_stats(args.agent, nerd_step_history, nerd_loss_history, nerd_return_history)
            except Exception as e:
                print_json("error", message=f"Failed to save nerd stats: {e}")
