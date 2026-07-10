import multiprocessing as std_mp
import threading

SESSION_REGISTRY: dict = {}
REGISTRY_LOCK = std_mp.Lock()

# Lazy-initialized shared manager — created on first use from the main process,
# never at module import time (which would crash inside spawned worker children).
_manager_lock = threading.Lock()
_shared_manager: "std_mp.managers.SyncManager | None" = None


def get_shared_manager() -> "std_mp.managers.SyncManager":
    """Return the process-wide Manager, creating it on the first call."""
    global _shared_manager
    if _shared_manager is None:
        with _manager_lock:
            if _shared_manager is None:
                _shared_manager = std_mp.Manager()
    return _shared_manager
