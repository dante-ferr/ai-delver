from typing import Any, Dict, List, TYPE_CHECKING
from pymunk import Vec2d

if TYPE_CHECKING:
    from runtime.episode_trajectory.snapshots import FrameSnapshot


def lerp(a: float, b: float, alpha: float) -> float:
    """Linearly interpolates between two scalar values."""
    return a + alpha * (b - a)


def lerp_vec(v1: List[float], v2: List[float], alpha: float) -> List[float]:
    """Linearly interpolates between two vectors represented as lists."""
    interpolated_vec = Vec2d(v1[0], v1[1]).interpolate_to(Vec2d(v2[0], v2[1]), alpha)
    return [interpolated_vec.x, interpolated_vec.y]


def _interpolate_state_dicts(
    prev_state_dict: Dict[str, Any], next_state_dict: Dict[str, Any], alpha: float
) -> Dict[str, Any]:
    """
    Internal helper that generates a new state dictionary by interpolating between two others.
    """
    interpolated_state: Dict[str, Any] = {}

    for key, next_value in next_state_dict.items():
        if key not in prev_state_dict:
            interpolated_state[key] = next_value
            continue

        prev_value = prev_state_dict[key]

        if isinstance(next_value, (int, float)) and isinstance(
            prev_value, (int, float)
        ):
            interpolated_state[key] = lerp(prev_value, next_value, alpha)
        elif (
            isinstance(next_value, list)
            and isinstance(prev_value, list)
            and all(isinstance(n, (int, float)) for n in next_value)
            and all(isinstance(n, (int, float)) for n in prev_value)
        ):
            interpolated_state[key] = lerp_vec(prev_value, next_value, alpha)
        else:
            interpolated_state[key] = next_value

    return interpolated_state


def interpolate_frame_snapshots(
    prev_snapshot: "FrameSnapshot", next_snapshot: "FrameSnapshot", alpha: float
) -> "FrameSnapshot":
    """
    Generates a new FrameSnapshot by interpolating between a previous and next snapshot.

    It automatically interpolates numeric values (floats, vectors) for each entity
    and carries over non-numeric values from the next snapshot.
    """
    from runtime.episode_trajectory.snapshots import FrameSnapshot

    interpolated_snapshot = FrameSnapshot()
    prev_states = {s.entity_id: s for s in prev_snapshot.entities}

    for next_entity_state in next_snapshot.entities:
        entity_id = next_entity_state.entity_id
        prev_entity_state = prev_states.get(entity_id)

        if not prev_entity_state:
            continue

        # Convert dataclasses to dictionaries to pass to the interpolator
        prev_dict = prev_entity_state.__dict__
        next_dict = next_entity_state.__dict__

        # Generate the interpolated state dictionary using the helper
        interpolated_dict = _interpolate_state_dicts(prev_dict, next_dict, alpha)

        # Add the new entity state to our virtual snapshot using your existing factory logic
        interpolated_snapshot.add_entity_from_json(interpolated_dict)

    return interpolated_snapshot
