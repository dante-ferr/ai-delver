import json
import sys
from pathlib import Path
from agent.agent import Agent
from agent.config import SESSION_STORAGE_KEY


def run_load_agent(path: str):
    """Validates that an agent directory can be loaded (GUI performs the session adopt)."""
    try:
        agent_path = Path(path)
        if not agent_path.is_dir():
            print(json.dumps({
                "event": "error",
                "message": f"Agent directory not found: {agent_path}",
            }), flush=True)
            sys.exit(1)
        if agent_path.name == SESSION_STORAGE_KEY:
            print(json.dumps({
                "event": "error",
                "message": "Cannot load the reserved session workspace as a named agent.",
            }), flush=True)
            sys.exit(1)

        file_path = agent_path / "agent.json"
        if file_path.is_file():
            agent = Agent.load(file_path, storage_key=agent_path.name)
            name = agent.name
        else:
            name = agent_path.name

        print(json.dumps({
            "event": "agent_loaded",
            "name": name,
            "path": str(path),
        }), flush=True)
    except Exception as e:
        print(json.dumps({"event": "error", "message": str(e)}), flush=True)
        sys.exit(1)
