import json
import sys
from agent.agent import Agent


def run_save_agent(name: str, from_name: str | None = None, force: bool = False):
    """Saves/persists an agent on disk with the given name.

    When ``from_name`` differs from ``name``, copies the source agent folder
    (weights, trajectories, checkpoints, etc.) into the destination first.
    """
    try:
        if not name or name.strip() == "":
            print(json.dumps({"event": "error", "message": "Agent name cannot be empty."}), flush=True)
            sys.exit(1)

        source = from_name.strip() if from_name and from_name.strip() else None
        agent = Agent.persist(name.strip(), from_name=source, force=force)
        copied_from = source if source and source != agent.name else None
        print(json.dumps({
            "event": "agent_saved",
            "name": agent.name,
            "path": str(agent.save_file_path.parent) if agent.save_file_path else "",
            "copied_from": copied_from,
        }), flush=True)
    except Exception as e:
        print(json.dumps({"event": "error", "message": str(e)}), flush=True)
        sys.exit(1)
