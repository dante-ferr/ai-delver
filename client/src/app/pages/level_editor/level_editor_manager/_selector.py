from typing import Callable, Any


class LevelSelector:
    def __init__(self):
        self._selections: dict[str, Any] = {}
        self._selection_callbacks: dict[str, list[Callable[[Any], None]]] = {}

    def set_selection(self, selection_name: str, selection_value: Any):
        self._selections[selection_name] = selection_value

        for callback in self._selection_callbacks.get(selection_name, []):
            callback(selection_value)

    def get_selection(self, selection_name: str) -> Any:
        return self._selections[selection_name]

    def set_select_callback(self, selection_name: str, callback: Callable[[Any], None]):
        """Replace all callbacks for ``selection_name`` with a single callback."""
        self._selection_callbacks[selection_name] = [callback]

    def add_select_callback(self, selection_name: str, callback: Callable[[Any], None]):
        """Append a callback for ``selection_name`` without removing existing ones."""
        self._selection_callbacks.setdefault(selection_name, []).append(callback)
