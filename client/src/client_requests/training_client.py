import os
import json
import httpx
import websockets
from level import config as level_config
from level import Level
from runtime.episode_trajectory import EpisodeTrajectoryFactory

class TrainingClient:
    """
    Pure Python client for interacting with the AI training server.
    This class is completely decoupled from any GUI library (like Tkinter)
    and is safe to use in headless or command-line contexts.
    """
    def __init__(self, server_url="localhost:8001"):
        self.server_url = server_url

    async def get_initial_info(self) -> dict:
        """Pings the server init endpoint to retrieve environment configurations."""
        uri = f"http://{self.server_url}/init"
        async with httpx.AsyncClient() as client:
            response = await client.get(uri, timeout=10.0)
            response.raise_for_status()
            return response.json()

    def ensure_levels_saved(self, levels: list[str], agent_name: str):
        """Hashes and saves referenced training levels under the agent's folder structure."""
        for level_name in levels:
            level_path = f"{level_config.LEVEL_SAVE_FOLDER_PATH}/{level_name}/level.json"
            if not os.path.exists(level_path):
                raise FileNotFoundError(f"Level file not found at: {level_path}")
            level = Level.load(level_path)
            level_hash = level.to_hash()
            save_dir = f"data/agents/{agent_name}/level_saves"
            os.makedirs(save_dir, exist_ok=True)
            save_path = f"{save_dir}/{level_hash}.json"
            if not os.path.exists(save_path):
                level.save(save_path)

    def create_training_payload(self, levels: list[str], episodes_per_cycle: int, mode: str, amount_of_cycles: int) -> dict:
        """Builds the request payload dictionary expected by the server."""
        level_jsons = []
        for level_name in levels:
            level_path = f"{level_config.LEVEL_SAVE_FOLDER_PATH}/{level_name}/level.json"
            with open(level_path, "r") as file:
                level_jsons.append(json.load(file))

        payload = {
            "levels": level_jsons,
            "episodes_per_cycle": episodes_per_cycle,
            "level_transitioning_mode": mode,
            "amount_of_cycles": amount_of_cycles if mode == "static" else None
        }
        return payload

    async def submit_training(self, payload: dict) -> dict:
        """Submits a training request to the server and returns the response."""
        uri = f"http://{self.server_url}/train"
        async with httpx.AsyncClient() as client:
            response = await client.post(uri, json=payload, timeout=30.0)
            response.raise_for_status()
            return response.json()

    async def interrupt_training(self, session_id: str) -> dict:
        """Requests training session interruption on the server."""
        uri = f"http://{self.server_url}/interrupt-training/{session_id}"
        async with httpx.AsyncClient() as client:
            response = await client.post(uri, json={}, timeout=10.0)
            response.raise_for_status()
            return response.json()

    async def listen_to_trajectory(
        self,
        session_id: str,
        on_trajectory: callable,
        on_level_transition: callable,
        on_completed: callable,
        on_error: callable
    ):
        """Connects to the WebSocket endpoint and streams trajectory results via callbacks."""
        uri = f"ws://{self.server_url}/episode-trajectory/{session_id}"
        trajectory_factory = EpisodeTrajectoryFactory()
        
        async with websockets.connect(uri) as websocket:
            async for message in websocket:
                try:
                    response_json = json.loads(message)
                except json.JSONDecodeError:
                    on_error("Received invalid JSON from server websocket.")
                    continue
                
                if response_json.get("end"):
                    on_completed()
                    break
                    
                response_type = response_json.get("type")
                if response_type == "showcase":
                    trajectory_data = response_json.get("trajectory")
                    trajectory = None
                    if trajectory_data:
                        trajectory = trajectory_factory.from_json(trajectory_data)
                    level_episode_count = response_json.get("level_episode_count")
                    if level_episode_count is not None:
                        level_episode_count = int(level_episode_count)
                    await on_trajectory(trajectory, level_episode_count)
                    
                elif response_type == "level_transition":
                    levels_trained = response_json.get("levels_trained")
                    if levels_trained is not None:
                        levels_trained = int(levels_trained)
                    on_level_transition(levels_trained)
