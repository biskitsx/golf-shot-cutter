from .types import Onset


class StubAudioOnsetDetector:
    def __init__(self, fixed_onsets: list[Onset] | None = None) -> None:
        self._onsets = fixed_onsets if fixed_onsets is not None else []

    def detect(self, audio_path: str) -> list[Onset]:
        return list(self._onsets)
