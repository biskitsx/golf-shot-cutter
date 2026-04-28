from typing import Protocol

from .types import Onset


class AudioOnsetDetector(Protocol):
    def detect(self, audio_path: str) -> list[Onset]: ...
