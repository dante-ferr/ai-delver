import json
import sys

from agent.session_workspace import reset_session_workspace


def run_reset_agent_session(from_name: str | None = None):
    """Wipe the live ``__session__`` workspace (optionally re-seed from a named agent)."""
    try:
        result = reset_session_workspace(from_name=from_name)
        print(
            json.dumps(
                {
                    "event": "agent_session_reset",
                    **result,
                    "message": (
                        f"Session re-seeded from '{result['reseeded_from']}'."
                        if result.get("reseeded_from")
                        else "Session wiped to a blank workspace."
                    ),
                }
            ),
            flush=True,
        )
    except Exception as e:
        print(json.dumps({"event": "error", "message": str(e)}), flush=True)
        sys.exit(1)
