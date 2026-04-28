import pathlib


class StubClipCutter:
    def cut(self, *, source_path: str, t_start: float, t_end: float, out_path: str) -> None:
        pathlib.Path(out_path).touch()
