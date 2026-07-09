from pathlib import Path


def get_trajectory_dir(agent_name: str) -> Path:
    trajectory_dir = "data/agents" / Path(agent_name) / "trajectories"
    trajectory_dir.mkdir(parents=True, exist_ok=True)

    return trajectory_dir
