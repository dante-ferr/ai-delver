"""
Nerd stats persistence helpers.

Provides save_nerd_stats() to write deep learning metrics history
(loss, average return per training step) into the agent's metadata.json
at the end of a training run.

Loading is handled by TrajectoryStatsCalculator.get_nerd_stats(), which is
called by the `stats` CLI command and consumed by the GUI via that subprocess.
"""
import json
from runtime.episode_trajectory._get_trajectory_dir import get_trajectory_dir

METADATA_FILE = "metadata.json"

_EMPTY_HISTORY = {
    "step_history": [],
    "loss_history": [],
    "return_history": [],
}


def _read_metadata(agent_name: str) -> dict:
    path = get_trajectory_dir(agent_name) / METADATA_FILE
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"trajectory_count": 0, "stats": {"amount": 0, "victories": 0}}


def _write_metadata(agent_name: str, metadata: dict) -> None:
    path = get_trajectory_dir(agent_name) / METADATA_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(metadata, f, indent=4)


def save_nerd_stats(
    agent_name: str,
    step_history: list,
    loss_history: list,
    return_history: list,
) -> None:
    """
    Appends the latest nerd stats from a training run into the agent's
    metadata.json under the 'nerd_stats' key, and replaces 'latest_session'
    with this run's metrics so they survive app restarts.

    Each training run appends its data to the existing all-time history so the
    All Stats window shows the full learning curve across all sessions.
    """
    metadata = _read_metadata(agent_name)

    existing = metadata.get("nerd_stats", dict(_EMPTY_HISTORY))
    existing.setdefault("step_history", [])
    existing.setdefault("loss_history", [])
    existing.setdefault("return_history", [])

    existing["step_history"].extend(step_history)
    existing["loss_history"].extend(loss_history)
    existing["return_history"].extend(return_history)

    existing["latest_session"] = {
        "step_history": list(step_history),
        "loss_history": list(loss_history),
        "return_history": list(return_history),
    }

    metadata["nerd_stats"] = existing
    _write_metadata(agent_name, metadata)
