import customtkinter as ctk
from typing import Callable, Dict, Any, Union, List

CtkVariable = Union[ctk.BooleanVar, ctk.StringVar, ctk.IntVar, ctk.DoubleVar]


class StateManager:
    """
    Base class for state managers that use CustomTkinter variables with callbacks.
    """

    def __init__(self):
        self.vars: Dict[str, CtkVariable] = {}
        self._variable_defs: Dict[str, tuple[type[CtkVariable], Any]] = {}
        self._callbacks: Dict[str, List[Callable[[Any], None]]] = {}

    def add_variable(self, name: str, var_class: type[CtkVariable], value: Any):
        """Registers a variable definition to be initialized later."""
        self._variable_defs[name] = (var_class, value)
        self._callbacks[name] = []

    def add_callback(self, name: str, callback: Callable[[Any], None]):
        """Register a callback for a state variable change."""
        if name not in self._variable_defs:
            raise ValueError(f"Unknown state variable: {name}")

        self._callbacks[name].append(callback)
        # If already initialized, call immediately with current value
        if name in self.vars:
            callback(self.vars[name].get())

    def initialize(self):
        """
        Creates the actual CustomTkinter variables and triggers initial callbacks.
        This must be called after the root CTk window has been created.
        """
        for name, (var_class, value) in self._variable_defs.items():
            if name not in self.vars:
                var = var_class(value=value)
                self.vars[name] = var
                # Use a lambda that captures the name correctly
                var.trace_add("write", lambda *args, n=name: self._notify_callbacks(n))

                # Immediately notify callbacks with the initial value
                self._notify_callbacks(name)

    def _notify_callbacks(self, name: str):
        if name in self.vars:
            value = self.vars[name].get()
            for callback in self._callbacks[name]:
                callback(value)

    def get_value(self, name: str) -> Any:
        if name not in self.vars:
            return self._variable_defs[name][1]
        return self.vars[name].get()

    def set_value(self, name: str, value: Any):
        if name not in self.vars:
            var_class, _ = self._variable_defs[name]
            self._variable_defs[name] = (var_class, value)
            return
        self.vars[name].set(value)
