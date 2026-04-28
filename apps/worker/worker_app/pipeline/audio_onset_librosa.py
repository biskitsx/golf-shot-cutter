import librosa
import numpy as np

from .types import Onset


class LibrosaAudioOnsetDetector:
    """Onset detection via librosa.onset.onset_detect with a min-separation filter.

    Designed for golf-impact transients — sharp broadband attacks ~3-8ms.

    Optional filters to reduce false positives:
    - Bandpass: golf impact has dominant energy in 2-8kHz; voice/wind/AC live
      below ~1kHz. Pass `bandpass_low_hz` + `bandpass_high_hz` to gate them out.
    - `min_strength_factor`: ignore onsets quieter than this fraction of the
      loudest event in the same clip (relative gate, adapts to recording level).
    """

    def __init__(
        self,
        *,
        sr: int = 22050,
        hop_length: int = 512,
        min_separation_seconds: float = 0.5,
        delta: float = 0.07,
        bandpass_low_hz: float | None = None,
        bandpass_high_hz: float | None = None,
        min_strength_factor: float = 0.0,
    ) -> None:
        self._sr = sr
        self._hop_length = hop_length
        self._min_separation = min_separation_seconds
        self._delta = delta
        self._bandpass_low = bandpass_low_hz
        self._bandpass_high = bandpass_high_hz
        self._min_strength_factor = min_strength_factor

    def detect(self, audio_path: str) -> list[Onset]:
        y, sr = librosa.load(audio_path, sr=self._sr, mono=True)

        if self._bandpass_low and self._bandpass_high:
            from scipy.signal import butter, sosfiltfilt

            sos = butter(
                4,
                [self._bandpass_low, self._bandpass_high],
                btype="band",
                fs=sr,
                output="sos",
            )
            y = sosfiltfilt(sos, y).astype("float32")

        env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=self._hop_length)
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=env,
            sr=sr,
            hop_length=self._hop_length,
            backtrack=False,
            delta=self._delta,
            units="frames",
        )
        if onset_frames.size == 0:
            return []

        max_env = float(np.max(env)) if env.size > 0 else 1.0
        min_strength = self._min_strength_factor * max_env

        onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=self._hop_length)

        onsets: list[Onset] = []
        last_t = -float("inf")
        for t, frame in zip(onset_times, onset_frames, strict=False):
            if t - last_t < self._min_separation:
                continue
            strength = float(env[frame]) if frame < env.size else 0.0
            if strength < min_strength:
                continue  # too quiet relative to the strongest event
            confidence = min(1.0, max(0.0, strength / (max_env or 1.0)))
            onsets.append(Onset(t=float(t), confidence=confidence))
            last_t = float(t)

        return onsets
