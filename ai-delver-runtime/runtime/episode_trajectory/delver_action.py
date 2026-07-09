from typing import TypedDict


class DelverAction(TypedDict):
    run: int  # -1 (left), 0 (no run), 1 (right)
    jump: bool
