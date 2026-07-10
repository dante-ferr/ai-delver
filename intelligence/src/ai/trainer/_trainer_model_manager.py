from tf_agents.policies import policy_saver, actor_policy
import tempfile
import shutil
import os
import logging
import tensorflow as tf
from tensorflow.python.trackable import autotrackable
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .trainer import Trainer


class TrainerModelManager:
    def __init__(self, trainer: "Trainer"):
        self.trainer = trainer

    def get_serialized_model(self) -> None | bytes:
        """
        Saves the agent's policy to a temporary directory, archives it as a zip file,
        and returns the resulting bytes.
        """
        try:
            agent = self.trainer.agent_manager.agent
            if not agent:
                logging.error("Cannot serialize model: Agent not initialized.")
                return None

            saver = policy_saver.PolicySaver(agent.policy)

            with tempfile.TemporaryDirectory() as temp_dir:
                policy_dir = os.path.join(temp_dir, "policy")

                saver.save(policy_dir)

                archive_base_name = os.path.join(temp_dir, "model_archive")
                archive_path = shutil.make_archive(
                    base_name=archive_base_name, format="zip", root_dir=policy_dir
                )

                with open(archive_path, "rb") as f:
                    model_bytes = f.read()

                logging.info(
                    f"Successfully serialized model policy to {len(model_bytes)} bytes."
                )
                return model_bytes
        except Exception as e:
            logging.error(f"Failed to serialize model: {e}")
            from ai.exceptions import ModelSerializationError
            raise ModelSerializationError(f"Failed to serialize model: {e}") from e

    def load_serialized_model(self, model_bytes: bytes) -> None:
        try:
            agent = self.trainer.agent_manager.agent
            if not agent:
                logging.error("Cannot load model: Agent not initialized.")
                return

            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, "model.zip")
                with open(zip_path, "wb") as f:
                    f.write(model_bytes)

                policy_dir = os.path.join(temp_dir, "policy")
                shutil.unpack_archive(zip_path, policy_dir)

                loaded_policy = tf.saved_model.load(policy_dir)

                if not isinstance(loaded_policy, autotrackable.AutoTrackable):
                    raise ValueError(
                        "Loaded policy is not an instance of AutoTrackable."
                    )

                # Map loaded variables by (name, shape) to avoid collisions
                loaded_vars_dict = {}
                model_vars = loaded_policy.model_variables if hasattr(loaded_policy, "model_variables") else loaded_policy.variables
                for v in model_vars:
                    loaded_vars_dict[(v.name, tuple(v.shape))] = v.numpy()

                # Helper to assign variables by name + shape match
                def assign_variables(net_vars) -> int:
                    assigned_count = 0
                    for v in net_vars:
                        key = (v.name, tuple(v.shape))
                        if key in loaded_vars_dict:
                            v.assign(loaded_vars_dict[key])
                            assigned_count += 1
                        else:
                            name_without_port = v.name.split(':')[0]
                            for (name, shape), val in loaded_vars_dict.items():
                                if name.split(':')[0] == name_without_port and shape == tuple(v.shape):
                                    v.assign(val)
                                    assigned_count += 1
                                    break
                    return assigned_count

                # Load into actor network
                actor_vars = agent.actor_net.variables if (hasattr(agent, "actor_net") and agent.actor_net) else (agent._actor_net.variables if hasattr(agent, "_actor_net") else [])
                actor_loaded = assign_variables(actor_vars)
                logging.info(f"Loaded {actor_loaded} variables into actor network.")

                # Load into value network
                value_vars = agent.value_net.variables if (hasattr(agent, "value_net") and agent.value_net) else (agent._value_net.variables if hasattr(agent, "_value_net") else [])
                value_loaded = assign_variables(value_vars)
                logging.info(f"Loaded {value_loaded} variables into value network.")

                logging.info(
                    "Successfully loaded weights from the provided model into the agent's policy network."
                )
        except Exception as e:
            logging.error(f"Failed to load serialized model: {e}")
            from ai.exceptions import ModelLoadError
            raise ModelLoadError(f"Failed to load serialized model: {e}") from e
