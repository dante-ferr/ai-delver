"""Episode-budget review-pass planner for automatic forgetting prevention.

After enough focus episodes, arms a review pass that includes each previous
level once (chunked by max_training_levels). Curriculum commits only when
callers apply ``commit_after_model_weights``.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

DEFAULT_FOCUS_EPISODES_BETWEEN_PASSES = 2000

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
    review_pass_queue_remaining: int = 0
    messages: list[str] = field(default_factory=list)


def default_review_state(
    focus_episodes_between_passes: int = DEFAULT_FOCUS_EPISODES_BETWEEN_PASSES,
) -> dict[str, Any]:
    return {
        "focus_episodes_between_passes": int(focus_episodes_between_passes),
        "focus_episodes_since_pass": 0,
        "review_pass_queue": [],
    }


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
    try:
        between = int(state.get("focus_episodes_between_passes", DEFAULT_FOCUS_EPISODES_BETWEEN_PASSES))
    except (TypeError, ValueError):
        between = DEFAULT_FOCUS_EPISODES_BETWEEN_PASSES
    state["focus_episodes_between_passes"] = max(1, between)
    try:
        since = int(state.get("focus_episodes_since_pass", 0))
    except (TypeError, ValueError):
        since = 0
    state["focus_episodes_since_pass"] = max(0, since)
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
    coach = [lvl for lvl in coach_levels if lvl]
    # Preserve order, drop duplicates
    seen: set[str] = set()
    coach_unique: list[str] = []
    for lvl in coach:
        if lvl not in seen:
            seen.add(lvl)
            coach_unique.append(lvl)

    state = metadata["review_state"]
    between = int(state["focus_episodes_between_passes"])
    since = int(state["focus_episodes_since_pass"])
    queue = [lvl for lvl in state["review_pass_queue"] if isinstance(lvl, str) and lvl]
    cap = max(1, int(max_training_levels or 1))

    if play or not metadata.get("trained_levels"):
        # Play mode / blank history: never inject reviews
        return ReviewPlan(
            is_review_pass=False,
            coach_levels=coach_unique,
            review_levels=[],
            session_levels=coach_unique[:cap],
            deferred_coach_levels=coach_unique[cap:],
            focus_budget_exceeded=False,
            focus_episodes_since_pass=since,
            focus_episodes_between_passes=between,
            review_pass_queue_remaining=len(queue),
            messages=[],
        )

    messages: list[str] = []
    focus_budget_exceeded = False

    if queue:
        review_take = min(len(queue), cap)
        review_levels = queue[:review_take]
        free = max(0, cap - len(review_levels))
        coach_included = [lvl for lvl in coach_unique if lvl not in review_levels][:free]
        deferred = [lvl for lvl in coach_unique if lvl not in review_levels and lvl not in coach_included]
        session_levels = list(review_levels) + list(coach_included)
        if deferred:
            messages.append(
                "Review pass in progress: deferred coach level(s) "
                f"{', '.join(deferred)} until the review queue has room."
            )
        messages.append(
            f"Review pass session: including {len(review_levels)} prior level(s) "
            f"({len(queue) - review_take} remaining after this chunk if committed)."
        )
        return ReviewPlan(
            is_review_pass=True,
            coach_levels=coach_included,
            review_levels=review_levels,
            session_levels=session_levels,
            deferred_coach_levels=deferred,
            focus_budget_exceeded=False,
            focus_episodes_since_pass=since,
            focus_episodes_between_passes=between,
            review_pass_queue_remaining=len(queue),
            messages=messages,
        )

    # Focus session
    session_levels = coach_unique[:cap]
    deferred = coach_unique[cap:]
    if projected_focus_episodes > 0 and (since + projected_focus_episodes) >= between:
        focus_budget_exceeded = projected_focus_episodes >= between
        if focus_budget_exceeded:
            messages.append(
                f"Focus session budget (~{projected_focus_episodes} episodes) meets or exceeds "
                f"the review threshold ({between}). A review pass will arm after model weights "
                "are saved if this session completes."
            )
        else:
            messages.append(
                f"Focus progress {since}/{between} episodes; this session may arm a review pass."
            )
    else:
        messages.append(
            f"Focus session ({since}/{between} focus episodes since last review pass)."
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
        # Coach leftovers join trained_levels but not the current pass queue
        _append_trained_levels(metadata, plan.coach_levels)
        _append_trained_levels(metadata, plan.deferred_coach_levels)
        # Review-pass episodes do not advance the focus counter
    else:
        _append_trained_levels(metadata, plan.session_levels)
        _append_trained_levels(metadata, plan.deferred_coach_levels)
        state["focus_episodes_since_pass"] = int(state["focus_episodes_since_pass"]) + episodes
        if state["focus_episodes_since_pass"] >= between and metadata.get("trained_levels"):
            # Arm next pass from full history (oldest-first trained_levels order)
            state["review_pass_queue"] = list(metadata["trained_levels"])
            state["focus_episodes_since_pass"] = 0

    metadata["review_state"] = state
    return metadata
