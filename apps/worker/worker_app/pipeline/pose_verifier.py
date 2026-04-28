from typing import Protocol


class PoseVerifier(Protocol):
    def verify(self, video_path: str, t_impact: float) -> bool: ...
