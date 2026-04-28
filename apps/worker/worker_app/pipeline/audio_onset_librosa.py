import numpy as np
import librosa

from .types import Onset


class LibrosaAudioOnsetDetector:
    """Onset detection via librosa.onset.onset_detect with a min-separation filter.

    Designed for golf-impact transients — sharp broadband attacks ~3-8ms.
    """

    def __init__(
        self,
        *,
        sr: int = 22050,
        hop_length: int = 512,
        min_separation_seconds: float = 0.5,
        delta: float = 0.07,
    ) -> None:
        self._sr = sr
        self._hop_length = hop_length
        self._min_separation = min_separation_seconds
        self._delta = delta

    def detect(self, audio_path: str) -> list[Onset]:
        y, sr = librosa.load(audio_path, sr=self._sr, mono=True)
        onset_frames = librosa.onset.onset_detect(
            y=y,
            sr=sr,
            hop_length=self._hop_length,
            backtrack=False,
            delta=self._delta,
            units="frames",
        )
        onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=self._hop_length)
        if onset_times.size == 0:
            return []

        env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=self._hop_length)
        max_env = float(np.max(env)) if env.size > 0 else 1.0

        onsets: list[Onset] = []
        last_t = -float("inf")
        for t in onset_times:
            if t - last_t < self._min_separation:
                continue
            frame = int(t * sr / self._hop_length)
            strength = float(env[frame]) if frame < env.size else 0.0
            confidence = min(1.0, max(0.0, strength / (max_env or 1.0)))
            onsets.append(Onset(t=float(t), confidence=confidence))
            last_t = float(t)

        return onsets
