import asyncio
import json
from client_requests.training_client import TrainingClient

def run_interrupt(session_id: str, server_url: str):
    """Sends HTTP POST to interrupt training on the server for session_id."""
    client = TrainingClient(server_url=server_url)
    try:
        response = asyncio.run(client.interrupt_training(session_id))
        if response.get("success"):
            print(json.dumps({
                "event": "interrupted",
                "message": "Training successfully interrupted."
            }), flush=True)
        else:
            print(json.dumps({
                "event": "error",
                "message": f"Server error: {response.get('message')}"
            }), flush=True)
    except Exception as e:
        print(json.dumps({
            "event": "error",
            "message": f"Failed to interrupt training: {e}"
        }), flush=True)
