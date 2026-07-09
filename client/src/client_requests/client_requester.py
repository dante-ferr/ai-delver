"""
Client-side request handler for communicating with the AI training server.

This module provides the ClientRequester class which handles:
- Initial connection and server configuration
- Sending training requests with level data
- Interrupting ongoing training sessions
- Listening for training results via WebSockets
"""

import logging
import httpx
from loaders import level_loader
from loaders import agent_loader
from ._trajectory_listener import TrajectoryListener
from state_managers import training_state_manager
from app.components.overlay.message_overlay import MessageOverlay
import os
import time
from level import config as level_config
import json
from level import Level
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from level import Level

class ClientRequester:
    """
    Handles all client-side requests to the AI training server, including
    initiating training, interrupting training, and listening for results
    via WebSockets.
    """
    def __init__(self, server_url="localhost:8001"):
        self.server_url = server_url
        self.session_id: None | str = None
        self.start_time: float = 0.0

    async def initial_request(self):
        """Pings the server for the first time to get relevant initial data."""
        try:
            uri = f"http://{self.server_url}/init"
            response_json = await self._send_get_request(uri)

            training_state_manager.set_value(
                "env_batch_size", response_json.get("env_batch_size")
            )
            training_state_manager.set_value(
                "max_training_levels", response_json.get("max_training_levels")
            )
            training_state_manager.set_value("connected_to_server", "yes")

            return True

        except Exception as e:
            training_state_manager.set_value("connected_to_server", "no")

            return False

    async def send_training_request(self):
        """
        Initiates the training session.
        """
        training_state_manager.sending_training_request = True
        try:
            payload = self._create_training_payload()
            uri = f"http://{self.server_url}/train"

            response_json = await self._send_post_request(uri, payload)

            if not self._handle_training_response(response_json):
                return

            self._ensure_levels_saved()

            if not self.session_id:
                raise ValueError("No session ID received from the server.")

            listener = TrajectoryListener(
                self.server_url, self.session_id, self.start_time
            )
            await listener.listen()

        except Exception as e:
            self._handle_error(e)

    async def send_interrupt_training_request(self):
        """
        Sends a request to interrupt the current training session on the server.
        """
        try:
            training_state_manager.sending_interrupt_training_request = True

            uri = f"http://{self.server_url}/interrupt-training/{self.session_id}"

            response_json = await self._send_post_request(uri, {})

            if response_json.get("success"):
                pass

        except Exception as e:
            self._handle_error(e)

    def _create_training_payload(self) -> dict:
        """
        Builds the training request payload from selected levels and configuration.
        
        Creates a dictionary containing:
        - The JSON representations of all selected training levels
        - The number of episodes per training cycle
        - The level transitioning mode (dynamic or static) with related parameters
        
        Returns:
            dict: A payload dictionary ready to be sent to the training server.
            
        Raises:
            ValueError: If no levels have been selected for training.
        """
        if len(training_state_manager.training_levels) == 0:
            raise ValueError("No levels selected for training.")

        # Load all selected level JSON files from the save folder
        level_jsons = []
        for level_name in training_state_manager.training_levels:
            with open(
                f"{level_config.LEVEL_SAVE_FOLDER_PATH}/{level_name}/level.json", "r"
            ) as file:
                level_jsons.append(json.load(file))

        # Build base payload with levels and episodes per cycle
        payload = {
            "levels": level_jsons,
            "episodes_per_cycle": training_state_manager.episodes_per_cycle,
        }

        # Add level transitioning mode configuration
        # Dynamic mode: cycles run indefinitely (amount_of_cycles is None)
        # Static mode: cycles run for a fixed number of times
        level_transitioning_mode = training_state_manager.get_value(
            "level_transitioning_mode"
        )
        if level_transitioning_mode == "dynamic":
            payload = {
                **payload,
                "level_transitioning_mode": "dynamic",
                "amount_of_cycles": None,
            }
        elif level_transitioning_mode == "static":
            payload = {
                **payload,
                "level_transitioning_mode": "static",
                "amount_of_cycles": training_state_manager.amount_of_cycles,
            }

        return payload

    def _handle_training_response(self, response_json: dict) -> bool:
        """
        Processes the server's response to a training request.
        
        Extracts the session_id from the response and updates the training state
        accordingly. The session_id is used to identify this training session
        in subsequent requests (e.g., for interruption or trajectory listening).
        
        Args:
            response_json: The JSON response from the server containing session info.
            
        Returns:
            bool: True if a valid session_id was received and training state was
                  updated successfully; False otherwise.
        """
        session_id = response_json.get("session_id")
        if session_id:
            self.session_id = session_id
            training_state_manager.sending_training_request = False
            training_state_manager.training = True
            self.start_time = time.time()
            return True
        else:
            logging.error("Failed to get a valid session_id from the server.")
            training_state_manager.reset_states()
            return False

    def _ensure_levels_saved(self):
        """
        Saves each training level with a unique hash as filename.
        
        This ensures trajectories can reference specific level configurations
        by hash. When replaying a trajectory, the correct level will be loaded
        based on the hash stored in the trajectory data.
        
        Levels are only saved if they don't already exist at the target path
        to avoid unnecessary disk writes.
        """
        # Each level configuration is saved with a unique hash as its filename, into the agent's directory.
        # This is done in order to allow the trajectories to point to a specific level configuration through
        # its specific hash. So when the trajectory is loaded to render a replay, the correct level will be
        # loaded as well.
        for level_name in training_state_manager.training_levels:
            level_path = (
                f"{level_config.LEVEL_SAVE_FOLDER_PATH}/{level_name}/level.json"
            )
            level = Level.load(level_path)
            level_hash = level.to_hash()
            save_path = (
                f"data/agents/{agent_loader.agent.name}/level_saves/{level_hash}.json"
            )
            if not os.path.exists(save_path):
                level.save(save_path)

    def _handle_error(self, e: Exception):
        """
        Handles errors that occur during training requests.
        
        Logs the error, displays an error message overlay to the user,
        and resets the training state to allow for retrying.
        
        Args:
            e: The exception that was raised during the request process.
        """
        logging.error(f"An error occurred during the process: {e}")
        MessageOverlay(f"An error occurred during the process: {e}", subject="Error")
        training_state_manager.reset_states()

    async def _send_get_request(self, uri) -> dict:
        """
        A helper method to send a GET request to the server.

        Args:
            uri (str): The full URI for the request.

        Returns:
            The JSON response from the server as a dictionary.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(uri, timeout=30.0)
            return self._get_response_data(response)

    async def _send_post_request(self, uri, payload) -> dict:
        """
        A helper method to send a POST request to the server.

        Args:
            uri (str): The full URI for the request.
            payload (dict): The JSON payload to send.

        Returns:
            The JSON response from the server as a dictionary.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(uri, json=payload, timeout=30.0)
            return self._get_response_data(response)

    def _get_response_data(self, response) -> dict:
        """
        Extracts and validates JSON data from an HTTP response.
        
        Raises an HTTPError if the response status code indicates an error
        (4xx, 5xx). On success, logs the server's response message and
        returns the parsed JSON data.
        
        Args:
            response: The httpx Response object to extract data from.
            
        Returns:
            dict: The parsed JSON response data.
            
        Raises:
            httpx.HTTPStatusError: If the response indicates an HTTP error status.
        """
        response.raise_for_status()

        response_data = response.json()
        logging.info(f"Server responded: {response_data.get('message')}")
        return response_data


# Singleton instance used throughout the application for server communication
client_requester = ClientRequester()
