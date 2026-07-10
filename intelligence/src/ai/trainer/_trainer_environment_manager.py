import functools
import logging
from tf_agents.environments import parallel_py_environment, tf_py_environment
from ai.environments.level.environment import LevelEnvironment
from ai.config import config
from typing import Optional


def _create_level_environment(
    env_id: int, level_json: dict, session_id: str, frame_counter, frame_lock
) -> LevelEnvironment:
    return LevelEnvironment(
        env_id=env_id,
        level_json=level_json,
        session_id=session_id,
        is_showcase=False,
        frame_counter=frame_counter,
        frame_lock=frame_lock,
    )


class TrainerEnvironmentManager:
    """Manages the creation, lifecycle, and transitioning of TF-Agents environments."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._tf_env: Optional[tf_py_environment.TFPyEnvironment] = None

    @property
    def tf_env(self) -> tf_py_environment.TFPyEnvironment:
        if self._tf_env is None:
            raise RuntimeError(
                "Environment not initialized. Call setup_environment first."
            )
        return self._tf_env

    def setup_environment(self, level_json: dict) -> None:
        """Creates or recreates the parallel environment for a specific level."""
        self.close()

        from ai.sessions import SESSION_REGISTRY
        session_objects = SESSION_REGISTRY[self.session_id]

        constructors = [
            functools.partial(
                _create_level_environment,
                env_id=i,
                level_json=level_json,
                session_id=self.session_id,
                frame_counter=session_objects["frame_counter"],
                frame_lock=session_objects["frame_lock"],
            )
            for i in range(config.ENV_BATCH_SIZE)
        ]

        py_env = parallel_py_environment.ParallelPyEnvironment(
            constructors, start_serially=True
        )
        self._tf_env = tf_py_environment.TFPyEnvironment(py_env)
        logging.info("Environment initialized.")

    def close(self) -> None:
        if self._tf_env:
            try:
                self._tf_env.close()
            except Exception as e:
                logging.warning(f"Error closing environment: {e}")
            self._tf_env = None
