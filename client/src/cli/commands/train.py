import asyncio
import base64
import json
import math
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
    apply_review_knobs,
    ensure_review_state,
    estimate_session_episodes,
    plan_session,
    queue_needs_review,
    review_session_budget,
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


def _count_jump_takeoffs_from_actions(actions) -> int:
    """Fallback takeoff count: rising edges of the jump action bit."""
    takeoffs = 0
    prev = False
    for action in actions:
        if isinstance(action, dict):
            jump = bool(action.get("jump", False))
        else:
            jump = bool(getattr(action, "jump", False))
        if jump and not prev:
            takeoffs += 1
        prev = jump
    return takeoffs


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
    """Executes training, optionally auto-chaining a budgeted review phase after focus."""
    global client_instance, session_id, interrupted, completed_normally
    interrupted = False
    completed_normally = False

    nerd_step_history: list = []
    nerd_loss_history: list = []
    nerd_return_history: list = []
    nerd_stats_persisted = False

    def persist_nerd_stats() -> None:
        nonlocal nerd_stats_persisted
        if nerd_stats_persisted or not nerd_loss_history:
            return
        try:
            save_nerd_stats(args.agent, nerd_step_history, nerd_loss_history, nerd_return_history)
            nerd_stats_persisted = True
        except Exception as e:
            print_json("error", message=f"Failed to save nerd stats: {e}")

    signal.signal(signal.SIGINT, raise_keyboard_interrupt)
    signal.signal(signal.SIGTERM, raise_keyboard_interrupt)

    async def train_async():
        global client_instance, session_id, completed_normally, interrupted
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
        early_stop = bool(getattr(args, "early_stop", False)) and not is_play_mode
        base_runs_per_cycle = getattr(args, "runs_per_cycle", None)
        base_episodes_per_cycle = getattr(args, "episodes_per_cycle", None)
        base_cycles = int(args.cycles)

        if is_play_mode:
            print_json(
                "info",
                message=(
                    f"Play mode enabled: putting Delver to play {len(coach_levels)} selected "
                    f"level(s) for {base_cycles} showcase run(s) each."
                ),
            )
            base_runs_per_cycle = None
            base_episodes_per_cycle = None
        else:
            if early_stop:
                print_json(
                    "info",
                    message=(
                        "Early-stop enabled: each level stops once the policy converges "
                        "(showcase mastery or return plateau), up to the configured cycle budget."
                    ),
                )
            if base_runs_per_cycle is not None and base_runs_per_cycle > 0:
                print_json(
                    "info",
                    message=(
                        f"Using runs_per_cycle={base_runs_per_cycle}; server will convert to "
                        f"~{base_runs_per_cycle * episodes_per_run} episode slots "
                        f"({episodes_per_run} slots per run)."
                    ),
                )
            else:
                if base_episodes_per_cycle is None or base_episodes_per_cycle <= 0:
                    print_json("error", message="train requires --runs-per-cycle or a positive --episodes-per-cycle")
                    return
                remainder = base_episodes_per_cycle % env_batch_size
                if remainder != 0:
                    adjusted = max(env_batch_size, round(base_episodes_per_cycle / env_batch_size) * env_batch_size)
                    print_json("info", message=f"Adjusted episodes-per-cycle from {base_episodes_per_cycle} to {adjusted} to align with env_batch_size ({env_batch_size}) constraints.")
                    base_episodes_per_cycle = adjusted
                    args.episodes_per_cycle = adjusted
                base_runs_per_cycle = None

        def episodes_per_cycle_for(runs, episodes_per_cycle):
            if runs is not None and runs > 0:
                return int(runs) * int(episodes_per_run)
            return int(episodes_per_cycle or 0)

        from agent.agent import Agent
        agent_obj = Agent(args.agent)

        weights_to_load = None
        if args.checkpoint:
            weights_to_load = resolve_checkpoint(agent_obj, str(args.checkpoint))
            if not weights_to_load:
                print_json("error", message=f"Specified checkpoint '{args.checkpoint}' not found.")
                return
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
            if agent_obj.weights_path and agent_obj.weights_path.is_file():
                weights_to_load = agent_obj.weights_path

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
            "early_stop",
            "checkpoint_interval",
            "no_learning",
            # Review knobs are client curriculum state, not server HPs.
            "focus_episodes_between_passes",
            "review_episodes_per_level",
            "review_levels_per_arm",
        }
        config_overrides = {
            key: val for key, val in vars(args).items()
            if key not in standard_keys and val is not None
        }

        async def reload_metadata():
            try:
                return await metadata_manager.read_metadata()
            except Exception:
                return {"trajectory_count": 0, "stats": {"amount": 0, "victories": 0}}

        # Apply CLI review E/R/K before any focus/review planning.
        review_override_e = getattr(args, "focus_episodes_between_passes", None)
        review_override_r = getattr(args, "review_episodes_per_level", None)
        review_override_k = getattr(args, "review_levels_per_arm", None)
        if (
            review_override_e is not None
            or review_override_r is not None
            or review_override_k is not None
        ):
            bootstrap_meta = ensure_review_state(await reload_metadata())
            apply_review_knobs(
                bootstrap_meta,
                focus_episodes_between_passes=review_override_e,
                review_episodes_per_level=review_override_r,
                review_levels_per_arm=review_override_k,
            )
            await metadata_manager.write_metadata(bootstrap_meta)
            print_json(
                "info",
                message=(
                    "Applied review knobs: "
                    f"E={bootstrap_meta['review_state']['focus_episodes_between_passes']}, "
                    f"R={bootstrap_meta['review_state']['review_episodes_per_level']}, "
                    f"K={bootstrap_meta['review_state']['review_levels_per_arm']}."
                ),
            )

        chain_start_time = time.time()
        overall_completed = False
        pre_level_saved_levels: set[str] = set()
        lr_scaled_for_challenge = False
        # Cumulative focus showcase count across sequential per-level sessions (GUI bar).
        focus_progress_base = 0
        total_focus_progress_steps = max(1, base_cycles * len(coach_levels))

        async def execute_phase(
            *,
            force_review: bool,
            cycles: int,
            runs_per_cycle,
            episodes_per_cycle,
            projected_episodes: int,
            focus_levels: list[str] | None = None,
            progress_base: int | None = None,
            progress_total: int | None = None,
        ) -> bool:
            """Run one focus or review /train. Returns True if completed with weights path OK.

            Focus sessions pass a single level via ``focus_levels`` so coach levels run
            sequentially (n cycles each). Review sessions keep the full coach list for
            deferred messaging and still static-mix the review queue.
            """
            global session_id, completed_normally, interrupted

            levels_for_plan = focus_levels if focus_levels is not None else coach_levels

            metadata = ensure_review_state(await reload_metadata())
            # Prefer draining an existing queue before more focus
            prefer_review = force_review or (not is_play_mode and queue_needs_review(metadata))
            if force_review and not queue_needs_review(metadata):
                # Caller asked to drain review but nothing is queued — do not fall
                # through into a multi-level focus mix.
                return True
            if (
                not force_review
                and not is_play_mode
                and queue_needs_review(metadata)
            ):
                # Sequential focus must not be hijacked into a review session (would
                # corrupt per-level progress accounting). Phase chain drains first.
                print_json(
                    "error",
                    message=(
                        "Focus phase requested while a review queue is pending; "
                        "drain the review batch before continuing sequential focus."
                    ),
                )
                return False
            review_plan = plan_session(
                levels_for_plan,
                metadata,
                max_training_levels,
                play=is_play_mode,
                projected_focus_episodes=0 if prefer_review else projected_episodes,
            )
            if prefer_review and not review_plan.is_review_pass and queue_needs_review(metadata):
                # queue present but plan_session should have selected it — re-plan after ensure
                review_plan = plan_session(
                    levels_for_plan,
                    metadata,
                    max_training_levels,
                    play=False,
                    projected_focus_episodes=0,
                )
            if prefer_review and not review_plan.is_review_pass:
                print_json(
                    "error",
                    message="Review was requested but planner returned a focus session; aborting phase.",
                )
                return False

            phase_cycles = cycles
            phase_runs = runs_per_cycle
            phase_episodes_per_cycle = episodes_per_cycle
            phase_projected = projected_episodes

            if review_plan.is_review_pass and not is_play_mode:
                ep_cycle = episodes_per_cycle_for(phase_runs, phase_episodes_per_cycle)
                if ep_cycle <= 0:
                    ep_cycle = max(1, int(episodes_per_run))
                    phase_runs = 1
                    phase_episodes_per_cycle = None
                phase_cycles, target_eps = review_session_budget(
                    len(review_plan.review_levels),
                    review_episodes_per_level=review_plan.review_episodes_per_level,
                    episodes_per_cycle=ep_cycle,
                )
                review_plan.target_episodes = target_eps
                phase_projected = target_eps
                print_json(
                    "info",
                    message=(
                        f"Review budget override: {phase_cycles} cycle(s) for "
                        f"~{target_eps} episode slots "
                        f"({review_plan.review_episodes_per_level} per level × "
                        f"{len(review_plan.review_levels)} levels)."
                    ),
                )

            levels_list = review_plan.session_levels
            if not levels_list:
                print_json("error", message="No levels left to train after review planning.")
                return False

            phase_name = "review" if review_plan.is_review_pass else "focus"
            # Showcase count ≈ cycles × levels in mix (one showcase per level per cycle).
            # Focus uses an overall N×L total so the GUI bar spans sequential per-level sessions.
            phase_showcase_steps = max(1, phase_cycles * len(levels_list))
            if phase_name == "focus" and progress_total is not None:
                expected_progress_steps = max(1, int(progress_total))
            else:
                expected_progress_steps = phase_showcase_steps
            phase_progress_base = int(progress_base or 0) if phase_name == "focus" else 0

            for msg in review_plan.messages:
                print_json("info", message=msg)

            if phase_name == "focus" and focus_levels is not None:
                print_json(
                    "info",
                    message=(
                        f"Focus level '{levels_list[0]}' "
                        f"({phase_cycles} cycle(s); sequential coaching)."
                    ),
                )

            print_json(
                "training_phase",
                phase=phase_name,
                expected_progress_steps=expected_progress_steps,
                progress_base=phase_progress_base,
                cycles=phase_cycles,
                levels=levels_list,
                message=f"Starting {phase_name} phase.",
            )
            print_json(
                "review_plan",
                is_review_pass=review_plan.is_review_pass,
                review_levels=review_plan.review_levels,
                coach_levels=review_plan.coach_levels,
                session_levels=levels_list,
                deferred_coach_levels=review_plan.deferred_coach_levels,
                focus_episodes_since_pass=review_plan.focus_episodes_since_pass,
                focus_episodes_between_passes=review_plan.focus_episodes_between_passes,
                review_episodes_per_level=review_plan.review_episodes_per_level,
                review_levels_per_arm=review_plan.review_levels_per_arm,
                review_pass_queue_remaining=review_plan.review_pass_queue_remaining,
                target_episodes=review_plan.target_episodes,
                cycles=phase_cycles,
                message=(
                    "Review pass session."
                    if review_plan.is_review_pass
                    else "Focus training session."
                ),
            )

            session_start_curriculum = curriculum_snapshot(metadata)

            print_json("init_started", message="Preparing levels and verifying configuration...")
            try:
                client_instance.ensure_levels_saved(levels_list, args.agent)
            except Exception as e:
                print_json("error", message=f"Failed to prepare levels: {e}")
                return False

            level_hashes = _level_hashes_for(levels_list)
            review_hashes = {
                level_hashes[name]
                for name in review_plan.review_levels
                if name in level_hashes and level_hashes[name]
            }

            nonlocal lr_scaled_for_challenge, model_bytes_b64
            if (
                weights_to_load
                and weights_to_load.is_file()
                and not review_plan.is_review_pass
            ):
                pending_pre = [lvl for lvl in levels_list if lvl not in pre_level_saved_levels]
                if pending_pre:
                    try:
                        with open(weights_to_load, "rb") as f:
                            pre_bytes = f.read()
                        for level in pending_pre:
                            entry = save_checkpoint(
                                agent_obj,
                                pre_bytes,
                                level=level,
                                cycle=None,
                                kind=KIND_PRE_LEVEL,
                                curriculum=session_start_curriculum,
                            )
                            pre_level_saved_levels.add(level)
                            print_json(
                                "info",
                                message=(
                                    f"Saved pre-level checkpoint for '{entry['level']}' "
                                    f"({entry['id']})."
                                ),
                            )
                    except Exception as e:
                        print_json("error", message=f"Failed to save pre-level checkpoints: {e}")
                        return False

            previously_trained = metadata.get("trained_levels", [])
            # Detect new challenges against the full coach list for this Train click
            new_levels = [lvl for lvl in coach_levels if lvl not in previously_trained]
            if (
                weights_to_load
                and new_levels
                and not review_plan.is_review_pass
                and not lr_scaled_for_challenge
            ):
                if args.learning_rate is None:
                    args.learning_rate = 0.000075
                    config_overrides["learning_rate"] = 0.000075
                    print_json(
                        "info",
                        message=(
                            f"New challenge detected (levels: {', '.join(new_levels)}). "
                            "Automatically reduced learning rate to 0.000075 to prevent "
                            "catastrophic forgetting."
                        ),
                    )
                else:
                    print_json(
                        "info",
                        message=(
                            f"New challenge detected (levels: {', '.join(new_levels)}). "
                            f"Respecting user-specified learning rate override of {args.learning_rate}."
                        ),
                    )
                lr_scaled_for_challenge = True

            # Refresh warm-start bytes from disk (previous phase may have written new weights)
            phase_agent = Agent(args.agent)
            if phase_agent.weights_path and phase_agent.weights_path.is_file():
                try:
                    with open(phase_agent.weights_path, "rb") as f:
                        model_bytes_b64 = base64.b64encode(f.read()).decode("utf-8")
                except Exception:
                    pass

            payload = client_instance.create_training_payload(
                levels_list,
                args.mode,
                phase_cycles,
                runs_per_cycle=phase_runs,
                episodes_per_cycle=None if (phase_runs or is_play_mode) else phase_episodes_per_cycle,
                config_overrides=config_overrides if config_overrides else None,
                model_bytes_b64=model_bytes_b64,
                play=is_play_mode,
                # Only early-stop single-level focus; review mixes should run their budget.
                early_stop=early_stop and phase_name == "focus" and len(levels_list) == 1,
            )

            print_json("request_sent", message=f"Sending training request to http://{args.server}/train...")
            try:
                response = await client_instance.submit_training(payload)
            except Exception as e:
                print_json("error", message=f"Failed to connect to training server: {e}")
                return False

            session_id = response.get("session_id")
            if not session_id:
                print_json("error", message="No session_id received from server.")
                return False

            print_json("session_created", session_id=session_id, message="Training session started successfully.")

            completed_normally = False
            interrupted = False
            current_cycle = 0
            levels_trained_count = 0
            current_level = levels_list[0]
            session_episodes_accumulated = 0
            curriculum_committed = False
            ep_cycle_eff = episodes_per_cycle_for(phase_runs, phase_episodes_per_cycle)
            phase_showcase_victories = 0
            phase_showcase_amount = 0
            phase_jump_takeoffs: list[int] = []
            phase_victorious_jump_takeoffs: list[int] = []

            async def on_trajectory(trajectory, level_episode_count):
                nonlocal current_cycle, phase_showcase_victories, phase_showcase_amount
                is_review_showcase = False
                persisted = False
                if trajectory is not None:
                    traj_hash = getattr(trajectory, "level_hash", "") or ""
                    is_review_showcase = bool(traj_hash) and traj_hash in review_hashes
                    if not is_review_showcase:
                        await trajectory.save(
                            args.agent,
                            kind="play" if is_play_mode else "train",
                            cycle=current_cycle,
                        )
                        persisted = True
                        phase_showcase_amount += 1
                        takeoffs = getattr(trajectory, "jump_takeoffs", None)
                        if takeoffs is None:
                            # Fallback for older servers: count rising edges of jump bit.
                            takeoffs = _count_jump_takeoffs_from_actions(
                                getattr(trajectory, "delver_actions", None) or []
                            )
                        try:
                            takeoffs_i = int(takeoffs)
                        except (TypeError, ValueError):
                            takeoffs_i = 0
                        phase_jump_takeoffs.append(takeoffs_i)
                        if getattr(trajectory, "victorious", False):
                            phase_showcase_victories += 1
                            phase_victorious_jump_takeoffs.append(takeoffs_i)
                current_cycle += 1
                # Focus progress is absolute across sequential levels for the GUI bar
                progress_cycle = (
                    phase_progress_base + current_cycle
                    if phase_name == "focus"
                    else current_cycle
                )
                print_json(
                    "progress",
                    cycle=progress_cycle,
                    phase_cycle=current_cycle,
                    level_episode_count=level_episode_count,
                    is_review=is_review_showcase or review_plan.is_review_pass,
                    persisted=persisted,
                    training_phase=phase_name,
                    victorious=bool(getattr(trajectory, "victorious", False)) if trajectory is not None else False,
                    message=f"Completed cycle {progress_cycle}",
                )

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
                    training_phase=phase_name,
                    message="Transitioned to next level.",
                )

            def on_completed():
                global completed_normally
                if not is_play_mode:
                    persist_nerd_stats()
                print_json(
                    "info",
                    message=f"{phase_name.capitalize()} phase completed.",
                )
                completed_normally = True

            def on_error(err):
                print_json("error", message=err)

            def on_server_info(payload):
                message = payload.get("message")
                if not message:
                    return
                print_json(
                    "info",
                    message=message,
                    early_stop=bool(payload.get("early_stop")),
                    cycle=payload.get("cycle"),
                    mastery=payload.get("mastery"),
                    plateau=payload.get("plateau"),
                )

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
                    training_phase=phase_name,
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
                    # Metrics "episodes" count completed trajectories, which under-counts
                    # parallel env slots. Prefer the planned focus budget so review E arms
                    # on actual training volume (cycles × episodes_per_cycle).
                    if phase_projected > 0:
                        episodes_for_commit = max(episodes_for_commit, int(phase_projected))
                    elif episodes_for_commit <= 0:
                        if completed_normally and phase_projected > 0:
                            episodes_for_commit = phase_projected
                        elif current_cycle > 0 and ep_cycle_eff:
                            # current_cycle counts showcases; approximate episodes from server cycles
                            server_cycles = max(1, math.ceil(current_cycle / max(1, len(levels_list))))
                            episodes_for_commit = server_cycles * int(ep_cycle_eff)

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

            async def on_model_weights(model_bytes_b64_in):
                nonlocal model_bytes_b64
                if model_bytes_b64_in:
                    try:
                        weights_data = base64.b64decode(model_bytes_b64_in)
                        weights_agent = Agent(args.agent)
                        if weights_agent.weights_path:
                            weights_agent.weights_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(weights_agent.weights_path, "wb") as f:
                                f.write(weights_data)
                            model_bytes_b64 = model_bytes_b64_in
                            print_json("info", message="Successfully saved downloaded model weights from server.")
                            await commit_curriculum()
                    except Exception as e:
                        print_json("error", message=f"Failed to save downloaded model weights: {e}")

            async def on_checkpoint(cycle, model_bytes_b64_in):
                if model_bytes_b64_in:
                    try:
                        weights_data = base64.b64decode(model_bytes_b64_in)
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
                    on_info=on_server_info,
                )
            except Exception as e:
                print_json("error", message=f"WebSocket stream error: {e}")
            finally:
                if not completed_normally:
                    await interrupt_training(args.server)

            # Per-level mastery for single-level focus / play sessions (used by tune).
            if (
                completed_normally
                and phase_name == "focus"
                and focus_levels is not None
                and len(levels_list) == 1
                and phase_showcase_amount > 0
            ):
                win_rate = phase_showcase_victories / phase_showcase_amount
                # Prefer victorious-only takeoff averages for neatness; fall back to all runs.
                jump_source = (
                    phase_victorious_jump_takeoffs
                    if phase_victorious_jump_takeoffs
                    else phase_jump_takeoffs
                )
                mean_jumps = (
                    sum(jump_source) / len(jump_source) if jump_source else 0.0
                )
                max_jumps = max(jump_source) if jump_source else 0
                print_json(
                    "level_mastery",
                    level=levels_list[0],
                    victories=phase_showcase_victories,
                    amount=phase_showcase_amount,
                    win_rate=round(win_rate, 6),
                    mean_jumps=round(mean_jumps, 4),
                    max_jumps=int(max_jumps),
                    jump_metric="takeoffs",
                    training_phase=phase_name,
                    play=bool(is_play_mode),
                    message=(
                        f"Level mastery '{levels_list[0]}': "
                        f"{phase_showcase_victories}/{phase_showcase_amount} "
                        f"({win_rate:.1%}), mean_takeoffs={mean_jumps:.2f}"
                    ),
                )

            return completed_normally

        # --- Phase chain -------------------------------------------------
        # Focus: n cycles per coach level in list order (sequential), not a
        # static multi-level mix. Reviews stay review-only static mixes and
        # can auto-chain between (or mid) focus levels when E is crossed.
        # Play mode uses the same sequential per-level showcase loop (cycles
        # honor --cycles) so tune can score final curriculum mastery.
        if is_play_mode:
            overall_completed = True
            for level_index, level in enumerate(coach_levels):
                print_json(
                    "info",
                    message=(
                        f"Play eval {level_index + 1}/{len(coach_levels)}: "
                        f"'{level}' for {base_cycles} showcase run(s)."
                    ),
                )
                ok = await execute_phase(
                    force_review=False,
                    cycles=base_cycles,
                    runs_per_cycle=None,
                    episodes_per_cycle=None,
                    projected_episodes=0,
                    focus_levels=[level],
                    progress_base=focus_progress_base,
                    progress_total=total_focus_progress_steps,
                )
                if ok:
                    focus_progress_base += base_cycles
                else:
                    overall_completed = False
                    break
        else:
            metadata = ensure_review_state(await reload_metadata())
            ep_cycle = episodes_per_cycle_for(base_runs_per_cycle, base_episodes_per_cycle)

            async def drain_review_if_needed() -> bool:
                meta = ensure_review_state(await reload_metadata())
                if not queue_needs_review(meta):
                    return True
                # Pass full coach list so deferred messaging stays informative
                return await execute_phase(
                    force_review=True,
                    cycles=base_cycles,
                    runs_per_cycle=base_runs_per_cycle,
                    episodes_per_cycle=base_episodes_per_cycle,
                    projected_episodes=estimate_session_episodes(
                        cycles=base_cycles,
                        runs_per_cycle=base_runs_per_cycle,
                        episodes_per_run=episodes_per_run,
                        episodes_per_cycle=base_episodes_per_cycle,
                    ),
                    focus_levels=coach_levels,
                )

            # If a review queue is already pending, drain one review batch first
            if not await drain_review_if_needed():
                return

            for level_index, level in enumerate(coach_levels):
                metadata = ensure_review_state(await reload_metadata())
                since = int(metadata["review_state"]["focus_episodes_since_pass"])
                between = int(metadata["review_state"]["focus_episodes_between_passes"])
                remaining = max(0, between - since)

                level_projected_full = estimate_session_episodes(
                    cycles=base_cycles,
                    runs_per_cycle=base_runs_per_cycle,
                    episodes_per_run=episodes_per_run,
                    episodes_per_cycle=base_episodes_per_cycle,
                )

                focus_cycles = base_cycles
                leftover_cycles = 0
                if remaining > 0 and level_projected_full > remaining and ep_cycle > 0:
                    focus_cycles = max(1, int(math.ceil(remaining / ep_cycle)))
                    focus_cycles = min(focus_cycles, base_cycles)
                    leftover_cycles = max(0, base_cycles - focus_cycles)
                    if leftover_cycles:
                        print_json(
                            "info",
                            message=(
                                f"Splitting focus on '{level}': {focus_cycles} cycle(s) until "
                                f"review threshold ({remaining} episodes remaining to "
                                f"E={between}), then review, then {leftover_cycles} leftover "
                                f"cycle(s) on this level."
                            ),
                        )

                async def run_focus_chunk(cycles: int, focus_level: str) -> bool:
                    nonlocal focus_progress_base
                    if cycles <= 0:
                        return True
                    projected = estimate_session_episodes(
                        cycles=cycles,
                        runs_per_cycle=base_runs_per_cycle,
                        episodes_per_run=episodes_per_run,
                        episodes_per_cycle=base_episodes_per_cycle,
                    )
                    ok_inner = await execute_phase(
                        force_review=False,
                        cycles=cycles,
                        runs_per_cycle=base_runs_per_cycle,
                        episodes_per_cycle=base_episodes_per_cycle,
                        projected_episodes=projected,
                        focus_levels=[focus_level],
                        progress_base=focus_progress_base,
                        progress_total=total_focus_progress_steps,
                    )
                    if ok_inner:
                        # One showcase per cycle for a single-level focus session
                        focus_progress_base += cycles
                    return ok_inner

                print_json(
                    "info",
                    message=(
                        f"Sequential focus {level_index + 1}/{len(coach_levels)}: "
                        f"'{level}' for {base_cycles} cycle(s)."
                    ),
                )

                if not await run_focus_chunk(focus_cycles, level):
                    return

                if not await drain_review_if_needed():
                    return

                if leftover_cycles > 0:
                    if not await run_focus_chunk(leftover_cycles, level):
                        return
                    if not await drain_review_if_needed():
                        return

            overall_completed = True

        if overall_completed:
            duration = time.time() - chain_start_time
            print_json("completed", duration=f"{duration:.2f}s", message="Training completed successfully.")
            completed_normally = True

    try:
        asyncio.run(train_async())
    except KeyboardInterrupt:
        pass
    finally:
        if not getattr(args, "play", False):
            persist_nerd_stats()
        try:
            run_stats(args.agent)
        except Exception as e:
            print_json("error", message=f"Failed to calculate final stats: {e}")
