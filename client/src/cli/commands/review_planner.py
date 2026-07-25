"""Bounded rehearsal planner for automatic forgetting prevention.

Arms at most K prior levels after E focus episodes; each review chunk uses a
fixed R episode budget per level. Curriculum commits only via
``commit_after_model_weights``.
"""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

DEFAULT_FOCUS_EPISODES_BETWEEN_PASSES = 8000
DEFAULT_REVIEW_EPISODES_PER_LEVEL = 100
DEFAULT_REVIEW_LEVELS_PER_ARM = 5

CURRICULUM_KEYS = ("trained_levels", "level_hashes", "review_state")


@dataclass
class ReviewPlan:
    """Pending session plan; commit only after model_weights are written."""

    is_review_pass: bool
    coach_levels: list[str]
    review_levels: list[str]
    session_levels: list[str]
    deferred_coach_levels: list[str] = field(default_factory=list)
    focus_budget_exceeded: bool = False
    focus_episodes_since_pass: int = 0
    focus_episodes_between_passes: int = DEFAULT_FOCUS_EPISODES_BETWEEN_PASSES
    review_episodes_per_level: int = DEFAULT_REVIEW_EPISODES_PER_LEVEL
    review_levels_per_arm: int = DEFAULT_REVIEW_LEVELS_PER_ARM
    review_pass_queue_remaining: int = 0
    target_episodes: int | None = None
    messages: list[str] = field(default_factory=list)


def default_review_state(
    focus_episodes_between_passes: int = DEFAULT_FOCUS_EPISODES_BETWEEN_PASSES,
    review_episodes_per_level: int = DEFAULT_REVIEW_EPISODES_PER_LEVEL,
    review_levels_per_arm: int = DEFAULT_REVIEW_LEVELS_PER_ARM,
) -> dict[str, Any]:
    return {
        "focus_episodes_between_passes": int(focus_episodes_between_passes),
        "focus_episodes_since_pass": 0,
        "review_episodes_per_level": int(review_episodes_per_level),
        "review_levels_per_arm": int(review_levels_per_arm),
        "review_pass_queue": [],
        "review_arm_cursor": 0,
    }


def _positive_int(value: Any, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return max(1, int(default))


def ensure_review_state(metadata: dict[str, Any]) -> dict[str, Any]:
    """Normalize curriculum fields on a metadata dict (mutates and returns it)."""
    if not isinstance(metadata.get("trained_levels"), list):
        metadata["trained_levels"] = []
    if not isinstance(metadata.get("level_hashes"), dict):
        metadata["level_hashes"] = {}

    state = metadata.get("review_state")
    if not isinstance(state, dict):
        metadata["review_state"] = default_review_state()
        return metadata

    if not isinstance(state.get("review_pass_queue"), list):
        state["review_pass_queue"] = []

    # Migrate older agents that still have E=2000 default without R/K keys
    if "review_episodes_per_level" not in state and "review_levels_per_arm" not in state:
        try:
            old_e = int(state.get("focus_episodes_between_passes", 0))
        except (TypeError, ValueError):
            old_e = 0
        if old_e == 2000:
            state["focus_episodes_between_passes"] = DEFAULT_FOCUS_EPISODES_BETWEEN_PASSES

    state["focus_episodes_between_passes"] = _positive_int(
        state.get("focus_episodes_between_passes"),
        DEFAULT_FOCUS_EPISODES_BETWEEN_PASSES,
    )
    try:
        since = int(state.get("focus_episodes_since_pass", 0))
    except (TypeError, ValueError):
        since = 0
    state["focus_episodes_since_pass"] = max(0, since)
    state["review_episodes_per_level"] = _positive_int(
        state.get("review_episodes_per_level"),
        DEFAULT_REVIEW_EPISODES_PER_LEVEL,
    )
    state["review_levels_per_arm"] = _positive_int(
        state.get("review_levels_per_arm"),
        DEFAULT_REVIEW_LEVELS_PER_ARM,
    )
    try:
        cursor = int(state.get("review_arm_cursor", 0))
    except (TypeError, ValueError):
        cursor = 0
    state["review_arm_cursor"] = max(0, cursor)
    metadata["review_state"] = state
    return metadata


def curriculum_snapshot(metadata: dict[str, Any]) -> dict[str, Any]:
    """Copy curriculum fields for checkpoint bundles."""
    ensure_review_state(metadata)
    return {
        "trained_levels": list(metadata.get("trained_levels", [])),
        "level_hashes": dict(metadata.get("level_hashes", {})),
        "review_state": deepcopy(metadata.get("review_state", default_review_state())),
    }


def apply_curriculum_snapshot(metadata: dict[str, Any], snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Replace curriculum fields from a checkpoint snapshot."""
    if not snapshot or not isinstance(snapshot, dict):
        return metadata
    for key in CURRICULUM_KEYS:
        if key in snapshot:
            metadata[key] = deepcopy(snapshot[key])
    return ensure_review_state(metadata)


def estimate_session_episodes(
    *,
    cycles: int,
    runs_per_cycle: int | None = None,
    episodes_per_run: int = 12,
    episodes_per_cycle: int | None = None,
) -> int:
    """Estimate episode slots for a session (fallback when metrics are incomplete)."""
    cycles = max(0, int(cycles or 0))
    if runs_per_cycle is not None and runs_per_cycle > 0:
        return cycles * int(runs_per_cycle) * max(1, int(episodes_per_run))
    if episodes_per_cycle is not None and episodes_per_cycle > 0:
        return cycles * int(episodes_per_cycle)
    return 0


def review_session_budget(
    review_level_count: int,
    *,
    review_episodes_per_level: int,
    episodes_per_cycle: int,
) -> tuple[int, int]:
    """Return (cycles, target_episodes) for a review-only chunk."""
    level_count = max(0, int(review_level_count))
    r = max(1, int(review_episodes_per_level))
    ep_cycle = max(1, int(episodes_per_cycle))
    target = max(1, r * max(1, level_count))
    cycles = max(1, int(math.ceil(target / ep_cycle)))
    return cycles, target


def _unique_levels(levels: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for lvl in levels:
        if lvl and lvl not in seen:
            seen.add(lvl)
            out.append(lvl)
    return out


def _arm_review_batch(metadata: dict[str, Any]) -> list[str]:
    """Enqueue up to K priors via round-robin over trained_levels. Returns newly added.

    Uses ``review_arm_cursor`` so successive arms walk the career instead of
    always re-scheduling the oldest K maps.
    """
    ensure_review_state(metadata)
    state = metadata["review_state"]
    k = int(state["review_levels_per_arm"])
    queue = [lvl for lvl in state["review_pass_queue"] if isinstance(lvl, str) and lvl]
    if len(queue) >= k:
        return []
    trained = [lvl for lvl in metadata.get("trained_levels", []) if isinstance(lvl, str) and lvl]
    if not trained:
        return []

    queued = set(queue)
    cursor = int(state.get("review_arm_cursor", 0)) % len(trained)
    slots = k - len(queue)
    added: list[str] = []
    walked = 0
    for i in range(len(trained)):
        if len(added) >= slots:
            break
        lvl = trained[(cursor + i) % len(trained)]
        walked = i + 1
        if lvl in queued:
            continue
        queue.append(lvl)
        queued.add(lvl)
        added.append(lvl)

    if walked:
        state["review_arm_cursor"] = (cursor + walked) % len(trained)
    state["review_pass_queue"] = queue
    metadata["review_state"] = state
    return added


def plan_session(
    coach_levels: list[str],
    metadata: dict[str, Any],
    max_training_levels: int,
    *,
    play: bool = False,
    projected_focus_episodes: int = 0,
) -> ReviewPlan:
    """Build the level mix for this train request without mutating metadata."""
    ensure_review_state(metadata)
    coach_unique = _unique_levels(coach_levels)

    state = metadata["review_state"]
    between = int(state["focus_episodes_between_passes"])
    since = int(state["focus_episodes_since_pass"])
    r = int(state["review_episodes_per_level"])
    k = int(state["review_levels_per_arm"])
    queue = [lvl for lvl in state["review_pass_queue"] if isinstance(lvl, str) and lvl]
    cap = max(1, int(max_training_levels or 1))

    if play or not metadata.get("trained_levels"):
        return ReviewPlan(
            is_review_pass=False,
            coach_levels=coach_unique,
            review_levels=[],
            session_levels=coach_unique[:cap],
            deferred_coach_levels=coach_unique[cap:],
            focus_budget_exceeded=False,
            focus_episodes_since_pass=since,
            focus_episodes_between_passes=between,
            review_episodes_per_level=r,
            review_levels_per_arm=k,
            review_pass_queue_remaining=len(queue),
            messages=[],
        )

    messages: list[str] = []

    if queue:
        # Review-only mix so R is not diluted by coach leftovers
        review_take = min(len(queue), cap, k)
        review_levels = queue[:review_take]
        target = r * len(review_levels)
        messages.append(
            f"Review phase: {len(review_levels)} prior level(s), ~{target} episode slots "
            f"({r} per level). Coach level(s) deferred until this batch finishes."
        )
        if coach_unique:
            messages.append(
                "Deferred coach level(s): " + ", ".join(coach_unique) + "."
            )
        return ReviewPlan(
            is_review_pass=True,
            coach_levels=[],
            review_levels=review_levels,
            session_levels=list(review_levels),
            deferred_coach_levels=list(coach_unique),
            focus_budget_exceeded=False,
            focus_episodes_since_pass=since,
            focus_episodes_between_passes=between,
            review_episodes_per_level=r,
            review_levels_per_arm=k,
            review_pass_queue_remaining=len(queue),
            target_episodes=target,
            messages=messages,
        )

    # Focus session
    session_levels = coach_unique[:cap]
    deferred = coach_unique[cap:]
    focus_budget_exceeded = False
    if projected_focus_episodes > 0 and (since + projected_focus_episodes) >= between:
        focus_budget_exceeded = True
        messages.append(
            f"Focus budget (~{projected_focus_episodes} episodes) will meet or exceed "
            f"the review threshold ({between}). A review batch (up to {k} levels) may "
            "auto-chain after this focus phase."
        )
    else:
        messages.append(
            f"Focus session ({since}/{between} focus episodes since last review arm; "
            f"R={r}, K={k})."
        )

    return ReviewPlan(
        is_review_pass=False,
        coach_levels=session_levels,
        review_levels=[],
        session_levels=session_levels,
        deferred_coach_levels=deferred,
        focus_budget_exceeded=focus_budget_exceeded,
        focus_episodes_since_pass=since,
        focus_episodes_between_passes=between,
        review_episodes_per_level=r,
        review_levels_per_arm=k,
        review_pass_queue_remaining=0,
        messages=messages,
    )


def _merge_level_hashes(
    metadata: dict[str, Any],
    level_hashes: dict[str, str] | None,
) -> None:
    if not level_hashes:
        return
    existing = metadata.setdefault("level_hashes", {})
    if not isinstance(existing, dict):
        metadata["level_hashes"] = {}
        existing = metadata["level_hashes"]
    for name, digest in level_hashes.items():
        if name and digest:
            existing[str(name)] = str(digest)


def _append_trained_levels(metadata: dict[str, Any], levels: list[str]) -> None:
    trained = metadata.setdefault("trained_levels", [])
    if not isinstance(trained, list):
        trained = []
        metadata["trained_levels"] = trained
    for lvl in levels:
        if lvl and lvl not in trained:
            trained.append(lvl)


def commit_after_model_weights(
    metadata: dict[str, Any],
    plan: ReviewPlan,
    *,
    session_episodes: int,
    level_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Apply curriculum mutations after model weights were written successfully."""
    ensure_review_state(metadata)
    state = metadata["review_state"]
    between = int(state["focus_episodes_between_passes"])
    episodes = max(0, int(session_episodes or 0))

    _merge_level_hashes(metadata, level_hashes)

    if plan.is_review_pass:
        included = set(plan.review_levels)
        queue = [lvl for lvl in state["review_pass_queue"] if lvl not in included]
        state["review_pass_queue"] = queue
        _append_trained_levels(metadata, plan.coach_levels)
        _append_trained_levels(metadata, plan.deferred_coach_levels)
    else:
        _append_trained_levels(metadata, plan.session_levels)
        _append_trained_levels(metadata, plan.deferred_coach_levels)
        state["focus_episodes_since_pass"] = int(state["focus_episodes_since_pass"]) + episodes
        if state["focus_episodes_since_pass"] >= between and metadata.get("trained_levels"):
            state["focus_episodes_since_pass"] = 0
            metadata["review_state"] = state
            _arm_review_batch(metadata)
            return metadata

    metadata["review_state"] = state
    return metadata


def queue_needs_review(metadata: dict[str, Any]) -> bool:
    ensure_review_state(metadata)
    queue = metadata["review_state"].get("review_pass_queue") or []
    return bool(queue)
