from typing import Callable, Any


class LevelSelector:
    def __init__(self):
        self._selections: dict[str, Any] = {}
        self._selection_callbacks: dict[str, Callable[[str], None]] = {}

    def set_selection(self, selection_name: str, selection_value: Any):
        self._selections[selection_name] = selection_value

        callback = self._selection_callbacks.get(selection_name)
        if callback is not None:
            callback(selection_value)

    def get_selection(self, selection_name: str) -> Any:
        return self._selections[selection_name]

    def set_select_callback(self, selection_name: str, callback: Callable[[str], None]):
        self._selection_callbacks[selection_name] = callback
