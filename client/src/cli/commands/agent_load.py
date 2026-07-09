import json
import sys
from pathlib import Path
from agent.agent_loader import AgentLoader

def run_load_agent(path: str):
    """Loads an agent from the specified directory path."""
    try:
        loader = AgentLoader()
        agent = loader.load_agent(Path(path))
        print(json.dumps({
            "event": "agent_loaded",
            "name": agent.name,
            "path": str(path)
        }), flush=True)
    except Exception as e:
        print(json.dumps({"event": "error", "message": str(e)}), flush=True)
        sys.exit(1)
