import logging
import time
from .training_client import TrainingClient
from state_managers import training_state_manager
from app.components.overlay.message_overlay import MessageOverlay
from loaders import agent_loader

class GuiTrainingClient(TrainingClient):
    """
    GUI-aware subclass of TrainingClient.
    Binds the training event cycles directly to CustomTkinter's
    training_state_manager variables and MessageOverlay components.
    """
    def __init__(self, server_url="localhost:8001"):
        super().__init__(server_url)
        self.session_id = None
        self.start_time = 0.0
        self._current_cycle = 0

    async def initial_request(self) -> bool:
        """GUI initialization request to check server status."""
        try:
            info = await self.get_initial_info()
            training_state_manager.set_value("env_batch_size", info.get("env_batch_size"))
            training_state_manager.set_value("max_training_levels", info.get("max_training_levels"))
            training_state_manager.set_value("connected_to_server", "yes")
            return True
        except Exception as e:
            logging.error(f"GUI failed to connect to server: {e}")
            training_state_manager.set_value("connected_to_server", "no")
            return False

    async def send_training_request(self):
        """Asynchronously triggers training directly within the GUI thread context."""
        training_state_manager.sending_training_request = True
        try:
            if len(training_state_manager.training_levels) == 0:
                raise ValueError("No levels selected for training.")
                
            self.ensure_levels_saved(training_state_manager.training_levels, agent_loader.agent.name)
            
            payload = self.create_training_payload(
                levels=training_state_manager.training_levels,
                runs_per_cycle=training_state_manager.runs_per_cycle,
                mode=training_state_manager.get_value("level_transitioning_mode"),
                amount_of_cycles=training_state_manager.amount_of_cycles
            )
            
            response = await self.submit_training(payload)
            session_id = response.get("session_id")
            if not session_id:
                raise ValueError("No session ID received from server.")
                
            self.session_id = session_id
            training_state_manager.sending_training_request = False
            training_state_manager.training = True
            self.start_time = time.time()
            self._current_cycle = 0
            
            async def on_trajectory(trajectory, level_episode_count):
                if trajectory:
                    await trajectory.save(agent_loader.agent.name)
                training_state_manager.set_value("level_episode_count", level_episode_count)
                self._current_cycle += 1
                training_state_manager.update_training_process_log(self._current_cycle)
                from state_managers import trajectory_stats_state_manager
                trajectory_stats_state_manager.notify_trajectory_added()

            def on_level_transition(levels_trained):
                training_state_manager.set_value("levels_trained", levels_trained)

            def on_completed():
                duration = time.time() - self.start_time
                minutes, seconds = divmod(duration, 60)
                time_str = f"{int(minutes)}m {int(seconds)}s" if minutes > 0 else f"{seconds:.2f}s"
                training_state_manager.reset_states()
                from state_managers import trajectory_stats_state_manager
                trajectory_stats_state_manager.refresh_stats()
                MessageOverlay(f"Training session completed in {time_str}.", subject="Success")

            def on_error(err):
                logging.error(f"Training loop WebSocket error: {err}")
                training_state_manager.reset_states()
                MessageOverlay(f"Training error: {err}", subject="Error")

            await self.listen_to_trajectory(
                session_id,
                on_trajectory,
                on_level_transition,
                on_completed,
                on_error
            )
            
        except Exception as e:
            logging.error(f"GUI training submission failed: {e}")
            MessageOverlay(f"An error occurred: {e}", subject="Error")
            training_state_manager.reset_states()

    async def send_interrupt_training_request(self):
        """Sends the HTTP post to interrupt the current training session."""
        try:
            training_state_manager.sending_interrupt_training_request = True
            response = await self.interrupt_training(self.session_id)
            if response.get("success"):
                pass
        except Exception as e:
            logging.error(f"GUI interrupt request failed: {e}")
            MessageOverlay(f"Interrupt error: {e}", subject="Error")
            training_state_manager.reset_states()

gui_training_client = GuiTrainingClient()
