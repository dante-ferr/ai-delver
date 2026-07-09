import json
import sys
from agent.agent import Agent

def run_create_agent(name: str):
    """Creates a new agent on disk with the given name."""
    try:
        if not name or name.strip() == "":
            print(json.dumps({"event": "error", "message": "Agent name cannot be empty."}), flush=True)
            sys.exit(1)
            
        agent = Agent(name.strip())
        agent.save()
        print(json.dumps({
            "event": "agent_created",
            "name": agent.name,
            "path": str(agent.save_file_path.parent) if agent.save_file_path else ""
        }), flush=True)
    except Exception as e:
        print(json.dumps({"event": "error", "message": str(e)}), flush=True)
        sys.exit(1)
