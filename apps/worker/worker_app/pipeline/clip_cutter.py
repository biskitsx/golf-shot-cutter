from typing import Protocol


class ClipCutter(Protocol):
    def cut(self, *, source_path: str, t_start: float, t_end: float, out_path: str) -> None: ...
