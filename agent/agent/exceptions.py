class AgentError(Exception):
    """Base exception for agent-related errors."""
    pass


class AgentLoadError(AgentError):
    """Raised when an agent package doesn't exist or is corrupt."""
    pass


class ModelLoadError(AgentError):
    """Raised when the neural network policy weights fail to load."""
    pass


class ModelSerializationError(AgentError):
    """Raised when the agent's policy network fails to serialize."""
    pass
