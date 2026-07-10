class IntelligenceError(Exception):
    """Base exception for intelligence and training errors."""
    pass


class SessionNotFoundError(IntelligenceError):
    """Raised when looking up an active training session that does not exist or has expired."""

    def __init__(self, session_id: str):
        super().__init__(f"Training session '{session_id}' not found.")
        self.session_id = session_id


class TrainerError(IntelligenceError):
    """Raised when the PPO training loop fails to run or transitions invalidly."""
    pass


class ModelSerializationError(IntelligenceError):
    """Raised when the model policy fails to serialize."""
    pass


class ModelLoadError(IntelligenceError):
    """Raised when the loaded model weights fail to apply."""
    pass
