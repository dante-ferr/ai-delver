from typing import Callable
from customtkinter import BooleanVar


class LevelToggler:
    def __init__(self):
        self.vars: dict[str, BooleanVar] = {}

    def _add_var(self, var_name: str, value: bool = False):
        var = BooleanVar(value=value)
        self.vars[var_name] = var
        return var

    def get_var(self, var_name: str):
        if var_name not in self.vars:
            return self._add_var(var_name)

        return self.vars[var_name]

    def set_toggle_callback(self, var_name: str, callback: Callable[[bool], None]):
        if var_name not in self.vars:
            self._add_var(var_name)

        def formatted_callback(*args):
            callback(self.vars[var_name].get())

        self.vars[var_name].trace_add("write", formatted_callback)


# self.var.trace_add("write", self.on_toggle)
