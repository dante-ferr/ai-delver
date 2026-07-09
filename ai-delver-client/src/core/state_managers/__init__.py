from .trajectory_stats_state_manager import trajectory_stats_state_manager
from .state_manager import StateManager
from .canvas_state_manager import canvas_state_manager
from .training_state_manager import training_state_manager


def initialize_all_state_managers():
    """Initializes all global state managers. Should be called after creating the CTk root."""
    canvas_state_manager.initialize()
    training_state_manager.initialize()
    trajectory_stats_state_manager.initialize()


__all__ = [
    "canvas_state_manager",
    "training_state_manager",
    "trajectory_stats_state_manager",
    "StateManager",
    "initialize_all_state_managers",
]
