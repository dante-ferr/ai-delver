import asyncio
import base64
import json
import time
import signal
from client_requests.training_client import TrainingClient
from .stats import run_stats
from .nerd_stats_persistence import save_nerd_stats
from .checkpoint_store import (
    KIND_INTERVAL,
    KIND_PRE_LEVEL,
    load_checkpoint_curriculum,
    resolve_checkpoint,
    save_checkpoint,
)
from .review_planner import (
    commit_after_model_weights,
    curriculum_snapshot,
    ensure_review_state,
    estimate_session_episodes,
    plan_session,
)

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


def _level_hashes_for(levels: list[str]) -> dict[str, str]:
    """Hash on-disk level JSONs for curriculum resolvability."""
    from level import config as level_config
    from level import Level
    import os

    hashes: dict[str, str] = {}
    for level_name in levels:
        level_path = f"{level_config.LEVEL_SAVE_FOLDER_PATH}/{level_name}/level.json"
        if not os.path.exists(level_path):
            continue
        try:
            with open(level_path, "r", encoding="utf-8") as file:
                level_data = json.load(file)
            hashes[level_name] = Level.hash_json(level_data)
        except (OSError, json.JSONDecodeError):
            continue
    return hashes


def run_train(args):
    """Executes a training session, streaming trajectories, and calculating final stats on exit."""
    global client_instance, session_id, interrupted, completed_normally
    interrupted = False
    completed_normally = False

    # Accumulated nerd stats (reset each run)
    nerd_step_history: list = []
    nerd_loss_history: list = []
    nerd_return_history: list = []
    nerd_stats_persisted = False

    def persist_nerd_stats() -> None:
        """Saves session metrics once so completed/interrupted refreshes see latest_session."""
        nonlocal nerd_stats_persisted
        if nerd_stats_persisted or not nerd_loss_history:
            return
        try:
            save_nerd_stats(args.agent, nerd_step_history, nerd_loss_history, nerd_return_history)
            nerd_stats_persisted = True
        except Exception as e:
            print_json("error", message=f"Failed to save nerd stats: {e}")

    # Register system signals for graceful shutdown
    signal.signal(signal.SIGINT, raise_keyboard_interrupt)
    signal.signal(signal.SIGTERM, raise_keyboard_interrupt)

    async def train_async():
        global client_instance, session_id, completed_normally
        client_instance = TrainingClient(server_url=args.server)

        coach_levels = [l.strip() for l in args.levels.split(",") if l.strip()]
        if not coach_levels:
            print_json("error", message="No valid levels provided.")
            return

        try:
            init_data = await client_instance.get_initial_info()
            env_batch_size = init_data.get("env_batch_size", 32)
            episodes_per_run = init_data.get("episodes_per_run", 12)
            max_training_levels = int(init_data.get("max_training_levels", 10) or 10)
        except Exception as e:
            print_json("error", message=f"Failed to connect to training server at {args.server}: {e}")
            return

        is_play_mode = getattr(args, "play", False)
        runs_per_cycle = getattr(args, "runs_per_cycle", None)
        episodes_per_cycle_effective = None
        if is_play_mode:
            print_json("info", message=f"Play mode enabled: putting Delver to play {len(coach_levels)} selected level(s).")
            args.cycles = 1
        elif runs_per_cycle is not None and runs_per_cycle > 0:
            episodes_per_cycle_effective = runs_per_cycle * episodes_per_run
            print_json(
                "info",
                message=(
                    f"Using runs_per_cycle={runs_per_cycle}; server will convert to "
                    f"~{episodes_per_cycle_effective} episode slots "
                    f"({episodes_per_run} slots per run)."
                ),
            )
        else:
            if args.episodes_per_cycle is None or args.episodes_per_cycle <= 0:
                print_json("error", message="train requires --runs-per-cycle or a positive --episodes-per-cycle")
                return
            remainder = args.episodes_per_cycle % env_batch_size
            if remainder != 0:
                adjusted = max(env_batch_size, round(args.episodes_per_cycle / env_batch_size) * env_batch_size)
                print_json("info", message=f"Adjusted episodes-per-cycle from {args.episodes_per_cycle} to {adjusted} to align with env_batch_size ({env_batch_size}) constraints.")
                args.episodes_per_cycle = adjusted
            runs_per_cycle = None
            episodes_per_cycle_effective = args.episodes_per_cycle

        # Load existing agent weights if present
        from agent.agent import Agent
        agent_obj = Agent(args.agent)

        # Resolve weights path
        weights_to_load = None
        if args.checkpoint:
            weights_to_load = resolve_checkpoint(agent_obj, str(args.checkpoint))
            if not weights_to_load:
                print_json("error", message=f"Specified checkpoint '{args.checkpoint}' not found.")
                return
            # Align curriculum with the restored policy when possible
            snap = load_checkpoint_curriculum(agent_obj, str(args.checkpoint))
            if snap is not None:
                from runtime.episode_trajectory._trajectory_metadata_manager import TrajectoryMetadataManager
                from .review_planner import apply_curriculum_snapshot
                warm_meta_mgr = TrajectoryMetadataManager(args.agent)
                try:
                    warm_meta = await warm_meta_mgr.read_metadata()
                except Exception:
                    warm_meta = {"trajectory_count": 0, "stats": {"amount": 0, "victories": 0}}
                apply_curriculum_snapshot(warm_meta, snap)
                await warm_meta_mgr.write_metadata(warm_meta)
                print_json("info", message=f"Restored curriculum snapshot from checkpoint '{args.checkpoint}'.")
        else:
            # Default to latest weights
            if agent_obj.weights_path and agent_obj.weights_path.is_file():
                weights_to_load = agent_obj.weights_path

        # Load weights bytes
        model_bytes_b64 = None
        if weights_to_load and weights_to_load.is_file():
            try:
                with open(weights_to_load, "rb") as f:
                    model_bytes_b64 = base64.b64encode(f.read()).decode("utf-8")
                print_json("info", message=f"Loaded policy weights from '{weights_to_load.name}' for warm-start.")
            except Exception as e:
                print_json("info", message=f"Failed to read weights from '{weights_to_load}': {e}")

        from runtime.episode_trajectory._trajectory_metadata_manager import TrajectoryMetadataManager
        metadata_manager = TrajectoryMetadataManager(args.agent)
        try:
            metadata = await metadata_manager.read_metadata()
        except Exception:
            metadata = {"trajectory_count": 0, "stats": {"amount": 0, "victories": 0}}
        ensure_review_state(metadata)

        projected_episodes = 0
        if not is_play_mode:
            projected_episodes = estimate_session_episodes(
                cycles=args.cycles,
                runs_per_cycle=runs_per_cycle,
                episodes_per_run=episodes_per_run,
                episodes_per_cycle=episodes_per_cycle_effective,
            )

        review_plan = plan_session(
            coach_levels,
            metadata,
            max_training_levels,
            play=is_play_mode,
            projected_focus_episodes=projected_episodes,
        )
        levels_list = review_plan.session_levels
        if not levels_list:
            print_json("error", message="No levels left to train after review planning.")
            return

        for msg in review_plan.messages:
            print_json("info", message=msg)
        print_json(
            "review_plan",
            is_review_pass=review_plan.is_review_pass,
            review_levels=review_plan.review_levels,
            coach_levels=review_plan.coach_levels,
            session_levels=levels_list,
            deferred_coach_levels=review_plan.deferred_coach_levels,
            focus_episodes_since_pass=review_plan.focus_episodes_since_pass,
            focus_episodes_between_passes=review_plan.focus_episodes_between_passes,
            review_pass_queue_remaining=review_plan.review_pass_queue_remaining,
            message=(
                "Review pass session."
                if review_plan.is_review_pass
                else "Focus training session."
            ),
        )

        # Committed curriculum snapshot for interval/pre_level bundles (pre-session)
        session_start_curriculum = curriculum_snapshot(metadata)

        print_json("init_started", message="Preparing levels and verifying configuration...")
        try:
            client_instance.ensure_levels_saved(levels_list, args.agent)
        except Exception as e:
            print_json("error", message=f"Failed to prepare levels: {e}")
            return

        level_hashes = _level_hashes_for(levels_list)

        # Pre-level safety snapshots so each level has a rollback point
        if weights_to_load and weights_to_load.is_file():
            try:
                with open(weights_to_load, "rb") as f:
                    pre_bytes = f.read()
                for level in levels_list:
                    entry = save_checkpoint(
                        agent_obj,
                        pre_bytes,
                        level=level,
                        cycle=None,
                        kind=KIND_PRE_LEVEL,
                        curriculum=session_start_curriculum,
                    )
                    print_json(
                        "info",
                        message=(
                            f"Saved pre-level checkpoint for '{entry['level']}' "
                            f"({entry['id']})."
                        ),
                    )
            except Exception as e:
                print_json("error", message=f"Failed to save pre-level checkpoints: {e}")
                return

        previously_trained = metadata.get("trained_levels", [])
        new_levels = [lvl for lvl in coach_levels if lvl not in previously_trained]

        # If warm-starting and facing a new challenge (coach focus)
        if weights_to_load and new_levels and not review_plan.is_review_pass:
            if args.learning_rate is None:
                # Default is 0.0003; reduce to 0.000075 (1/4)
                args.learning_rate = 0.000075
                print_json("info", message=f"New challenge detected (levels: {', '.join(new_levels)}). Automatically reduced learning rate to 0.000075 to prevent catastrophic forgetting.")
            else:
                print_json("info", message=f"New challenge detected (levels: {', '.join(new_levels)}). Respecting user-specified learning rate override of {args.learning_rate}.")

        standard_keys = {
            "levels",
            "cycles",
            "episodes_per_cycle",
            "runs_per_cycle",
            "mode",
            "agent",
            "server",
            "command",
            "checkpoint",
            "play",
        }
        config_overrides = {
            key: val for key, val in vars(args).items()
            if key not in standard_keys and val is not None
        }

        payload = client_instance.create_training_payload(
            levels_list,
            args.mode,
            args.cycles,
            runs_per_cycle=runs_per_cycle,
            episodes_per_cycle=None if (runs_per_cycle or is_play_mode) else args.episodes_per_cycle,
            config_overrides=config_overrides if config_overrides else None,
            model_bytes_b64=model_bytes_b64,
            play=is_play_mode,
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
        levels_trained_count = 0
        current_level = levels_list[0]
        session_episodes_accumulated = 0
        curriculum_committed = False

        # Callback handlers for websocket stream
        async def on_trajectory(trajectory, level_episode_count):
            nonlocal current_cycle
            if trajectory:
                await trajectory.save(
                    args.agent, kind="play" if is_play_mode else "train"
                )
            current_cycle += 1
            print_json("progress", cycle=current_cycle, level_episode_count=level_episode_count, message=f"Completed cycle {current_cycle}")

        def on_level_transition(levels_trained):
            nonlocal levels_trained_count, current_level
            levels_trained_count = int(levels_trained) if levels_trained is not None else levels_trained_count + 1
            if 0 <= levels_trained_count < len(levels_list):
                current_level = levels_list[levels_trained_count]
            print_json(
                "level_transition",
                levels_trained=levels_trained_count,
                level=current_level,
                is_review=current_level in review_plan.review_levels,
                message="Transitioned to next level.",
            )

        def on_completed():
            global completed_normally
            if not is_play_mode:
                persist_nerd_stats()
            duration = time.time() - start_time
            print_json("completed", duration=f"{duration:.2f}s", message="Training completed successfully.")
            completed_normally = True

        def on_error(err):
            print_json("error", message=err)

        def on_metrics(step, loss, average_return, episodes):
            nonlocal session_episodes_accumulated
            if episodes is not None:
                try:
                    session_episodes_accumulated += int(episodes)
                except (TypeError, ValueError):
                    pass
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

        async def commit_curriculum() -> None:
            nonlocal curriculum_committed
            if curriculum_committed or is_play_mode:
                return
            curriculum_committed = True
            try:
                latest = await metadata_manager.read_metadata()
                ensure_review_state(latest)
                episodes_for_commit = session_episodes_accumulated
                if episodes_for_commit <= 0:
                    # Fallback when metrics never reported episodes
                    if completed_normally and projected_episodes > 0:
                        episodes_for_commit = projected_episodes
                    elif current_cycle > 0 and episodes_per_cycle_effective:
                        episodes_for_commit = current_cycle * int(episodes_per_cycle_effective)

                commit_after_model_weights(
                    latest,
                    review_plan,
                    session_episodes=episodes_for_commit,
                    level_hashes=level_hashes,
                )
                await metadata_manager.write_metadata(latest)
                state = latest.get("review_state", {})
                print_json(
                    "info",
                    message=(
                        "Updated curriculum after model weights "
                        f"(focus episodes since pass: {state.get('focus_episodes_since_pass', 0)}/"
                        f"{state.get('focus_episodes_between_passes', 0)}; "
                        f"review queue: {len(state.get('review_pass_queue') or [])})."
                    ),
                )
            except Exception as e:
                curriculum_committed = False
                print_json("error", message=f"Failed to update curriculum after model weights: {e}")

        async def on_model_weights(model_bytes_b64):
            if model_bytes_b64:
                try:
                    weights_data = base64.b64decode(model_bytes_b64)
                    # Re-instantiate agent_obj to ensure save paths exist
                    weights_agent = Agent(args.agent)
                    if weights_agent.weights_path:
                        weights_agent.weights_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(weights_agent.weights_path, "wb") as f:
                            f.write(weights_data)
                        print_json("info", message="Successfully saved downloaded model weights from server.")
                        await commit_curriculum()
                except Exception as e:
                    print_json("error", message=f"Failed to save downloaded model weights: {e}")

        async def on_checkpoint(cycle, model_bytes_b64):
            if model_bytes_b64:
                try:
                    weights_data = base64.b64decode(model_bytes_b64)
                    entry = save_checkpoint(
                        args.agent,
                        weights_data,
                        level=current_level,
                        cycle=int(cycle) if cycle is not None else None,
                        kind=KIND_INTERVAL,
                        curriculum=session_start_curriculum,
                    )
                    print_json(
                        "info",
                        message=(
                            f"Successfully saved checkpoint for cycle {cycle} "
                            f"on level '{current_level}' ({entry['id']})."
                        ),
                    )
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
        # Safety net if the run ended without a completed event (e.g. interrupt).
        # Play Levels still saves trajectories (kind=play) and refreshes stats so
        # the viewer updates, but must not persist training (nerd) metrics.
        if not getattr(args, "play", False):
            persist_nerd_stats()
        try:
            run_stats(args.agent)
        except Exception as e:
            print_json("error", message=f"Failed to calculate final stats: {e}")
