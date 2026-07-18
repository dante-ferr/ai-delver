# Error Handling Architecture

This document describes the **Domain-Bounded Custom Exception Model** and the **Unified Error Propagation Protocol** implemented across the **AI Delver** framework.

---

## 1. Domain-Bounded Exceptions

To keep package boundaries clean and preserve module decoupling, exceptions are organized by domain. Each editable module defines its own exception hierarchy instead of relying on a monolithic shared base.

### Level Module (`level`)
Handles level deserialization, validation, and file IO.
* `LevelError`: Base exception class.
* `LevelLoadError`: Raised when level JSON reading or file opening fails.
* `LevelValidationError`: Raised when a level's structure (e.g., coordinates, sizes, or paths) is invalid.

### Runtime Module (`runtime`)
Handles physics simulation, Pymunk coordinates, and collision loops.
* `SimulationError`: Base exception class.
* `EntityNotFoundError`: Raised when looking up or interacting with a non-existent entity.

### Agent Module (`agent`)
Handles agent state initialization, dill deserialization, and model network states.
* `AgentError`: Base exception class.
* `AgentLoadError`: Raised when loading a Dill-serialized agent file fails.
* `ModelLoadError`: Raised when tf-agents saved-model variables fail to unpack or apply.
* `ModelSerializationError`: Raised when saving the policy network weights fails.

### Intelligence Module (`intelligence`)
Handles training loops, multi-process reward tracking, and sessions.
* `IntelligenceError`: Base exception class.
* `SessionNotFoundError`: Raised when looking up an invalid or expired training session ID.
* `TrainerError`: Raised when metrics, evaluators, or dockets are accessed prior to initialization, or when the PPO loop fails.

### Client Requests Module (`client_requests`)
Handles HTTP queries, REST APIs, and WebSocket streams.
* `ClientError`: Base exception class.
* `APIError`: Translates standard HTTP status errors (e.g., 400, 404, 500) into structured debug reports.
* `WebSocketError`: Raised on sudden socket disconnects or connection failures.

---

## 2. Server-to-Client Error Propagation

When a background training worker crashes or encounters an exception, it is caught and serialized over the WebSocket:

```
[Background Training Thread]
            │ (catches Exception)
            ▼
[Safe Queue Push] ──────► session.replay_queue (type="error")
                                   │
                                   ▼
                       [FastAPI WebSocket Endpoint]
                                   │
                                   ▼ (Sends JSON over WS)
                           [TrainingClient]
                                   │
                                   ▼ (Triggers on_error callback)
                           [Client UI / CLI]
```

### Protocol Payload Schema
The error is pushed as a dictionary with the following schema:
```json
{
  "type": "error",
  "error_class": "ModelLoadError",
  "message": "Failed to load serialized model: Incompatible tensor shapes",
  "traceback": "...[stack trace string]..."
}
```

When received, the client halts the listener loop immediately and invokes the `on_error` callback rather than completing the session successfully, avoiding silent failures.

---

## 3. Developer Guidelines

1. **Be Specific**: Never raise raw `ValueError` or `Exception` for domain logic failures. Use the corresponding package custom exception.
2. **Do Not Swallow Critical Failures**: Avoid empty or purely-logging `except Exception:` blocks in managers. If recovery is impossible, catch the error, log it, and raise a custom exception from the original cause:
   ```python
   except Exception as e:
       logging.error(f"Failed: {e}")
       raise CustomError("Action failed") from e
   ```
3. **Map at Boundaries**: Translate generic exceptions to custom exceptions at package boundaries, and catch custom exceptions at user boundaries (CLI entrypoints, API controllers, GUI event loops) to present clean notifications.
