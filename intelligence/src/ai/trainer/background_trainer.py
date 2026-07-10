import logging
import multiprocessing as std_mp
from ai.sessions.session_manager import session_manager
from ai.sessions import REGISTRY_LOCK, SESSION_REGISTRY, get_shared_manager


def run_training_in_background(session_id: str):
    """Initializes shared objects for a specific session and starts training."""
    global SESSION_REGISTRY, REGISTRY_LOCK

    import tensorflow as tf
    tf.keras.backend.clear_session()

    session = session_manager.get_session(session_id)
    if not session:
        logging.error(f"FATAL: Background worker could not find session {session_id}.")
        return
    if not session.trainer:
        logging.error(
            f"FATAL: Background worker could not find trainer for session {session_id}."
        )

    # Use the long-lived shared manager to create picklable proxy objects
    manager = get_shared_manager()
    with REGISTRY_LOCK:
        SESSION_REGISTRY[session_id] = {
            "frame_counter": manager.Value("i", 0),
            "frame_lock": manager.Lock(),
        }

    try:
        session.trainer.setup_env_and_agent()
        session.trainer.train()

        # Extract and send final model weights over the WebSocket queue
        if hasattr(session.trainer, "model_manager"):
            try:
                model_bytes = session.trainer.model_manager.get_serialized_model()
                if model_bytes:
                    import base64
                    model_bytes_b64 = base64.b64encode(model_bytes).decode("utf-8")
                    payload = {
                        "type": "model_weights",
                        "model_bytes_b64": model_bytes_b64
                    }
                    if session.trainer.loop:
                        session.trainer.loop.call_soon_threadsafe(
                            session.replay_queue.put_nowait, payload
                        )
                    else:
                        session.replay_queue.put_nowait(payload)
            except Exception as e:
                logging.error(f"Failed to serialize model weights for session {session_id}: {e}")
    except Exception as e:
        import traceback
        logging.error(
            f"Error during training for session {session_id}: {e}", exc_info=True
        )
        error_payload = {
            "type": "error",
            "error_class": e.__class__.__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
        if session.trainer and session.trainer.loop:
            session.trainer.loop.call_soon_threadsafe(
                session.replay_queue.put_nowait, error_payload
            )
        else:
            session.replay_queue.put_nowait(error_payload)
    finally:
        with REGISTRY_LOCK:
            SESSION_REGISTRY.pop(session_id, None)

        logging.info(f"Cleaning up session: {session_id}")
        session_manager.delete_session(session_id)
