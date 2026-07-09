import websockets
from runtime.episode_trajectory import EpisodeTrajectoryFactory
from state_managers import trajectory_stats_state_manager
import logging
import json
from state_managers import training_state_manager
from app.components.overlay.message_overlay import MessageOverlay
from loaders import agent_loader
import time


class TrajectoryListener:
    """
    Handles the WebSocket connection for receiving episode trajectories.
    """

    def __init__(self, server_url: str, session_id: str, start_time: float):
        self.server_url = server_url
        self.session_id = session_id
        self.start_time = start_time
        self.current_cycle = 0
        self.trajectory_factory = EpisodeTrajectoryFactory()

    async def listen(self):
        """
        Connects to the WebSocket and processes incoming messages.
        """
        uri = f"ws://{self.server_url}/episode-trajectory/{self.session_id}"
        logging.info(
            f"Connecting to WebSocket at {uri} to receive episode trajectory data..."
        )

        try:
            async with websockets.connect(uri) as websocket:
                logging.info(
                    "WebSocket connection established. Waiting for episode trajectory frames..."
                )
                async for response in websocket:
                    await self._process_message(response)

        except websockets.exceptions.ConnectionClosed as e:
            logging.warning(f"WebSocket connection closed: {e}")
            training_state_manager.reset_states()
        except Exception as e:
            logging.error(f"An unexpected error occurred in WebSocket listener: {e}")
            training_state_manager.reset_states()
            raise

    async def _process_message(self, response: str | bytes):
        try:
            response_json = json.loads(response)
        except json.JSONDecodeError:
            logging.error("Received invalid JSON from server.")
            return

        is_end_signal = response_json.get("end")
        if is_end_signal:
            self._handle_end_signal()

        response_type = response_json.get("type")
        if response_type == "showcase":
            trajectory_data = response_json.get("trajectory")
            if trajectory_data:
                await self._handle_trajectory(trajectory_data)

            level_episode_count = int(response_json.get("level_episode_count"))
            if level_episode_count:
                training_state_manager.set_value(
                    "level_episode_count", level_episode_count
                )

        elif response_type == "level_transition":
            levels_trained = response_json.get("levels_trained")
            if levels_trained:
                training_state_manager.set_value("levels_trained", levels_trained)

    async def _handle_trajectory(self, trajectory_data: str):
        trajectory = self.trajectory_factory.from_json(trajectory_data)
        await trajectory.save(agent_loader.agent.name)

        self.current_cycle += 1
        training_state_manager.update_training_process_log(self.current_cycle)

    def _handle_end_signal(self):
        duration = time.time() - self.start_time
        time_str = self._format_duration(duration)

        training_state_manager.training = False
        training_state_manager.sending_interrupt_training_request = False
        trajectory_stats_state_manager.refresh_stats()

        MessageOverlay(
            f"Training session completed in {time_str}.",
            subject="Success",
        )

    def _format_duration(self, duration: float) -> str:
        minutes, seconds = divmod(duration, 60)
        if minutes > 0:
            return f"{int(minutes)}m {int(seconds)}s"
        return f"{seconds:.2f}s"
