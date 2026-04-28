import os

from app.services.processing_service import ShotCandidate

from .audio_onset import AudioOnsetDetector
from .clip_cutter import ClipCutter
from .pose_verifier import PoseVerifier
from .types import Onset


class Pipeline:
    def __init__(
        self,
        *,
        audio_onset: AudioOnsetDetector,
        pose_verifier: PoseVerifier,
        clip_cutter: ClipCutter,
    ) -> None:
        self._audio = audio_onset
        self._pose = pose_verifier
        self._cutter = clip_cutter

    def run(
        self,
        *,
        session_id: str,
        source_video_path: str,
        clips_dir: str,
        pre_roll_seconds: float,
        post_roll_seconds: float,
    ) -> list[ShotCandidate]:
        os.makedirs(clips_dir, exist_ok=True)
        onsets = self._audio.detect(source_video_path)
        verified: list[Onset] = [o for o in onsets if self._pose.verify(source_video_path, o.t)]

        candidates: list[ShotCandidate] = []
        for index, onset in enumerate(verified, start=1):
            t_start = max(0.0, onset.t - pre_roll_seconds)
            t_end = onset.t + post_roll_seconds
            clip_filename = f"shot_{index:03d}.mp4"
            clip_path = os.path.join(clips_dir, clip_filename)
            clip_key = f"clips/{session_id}/{clip_filename}"

            self._cutter.cut(
                source_path=source_video_path,
                t_start=t_start,
                t_end=t_end,
                out_path=clip_path,
            )
            candidates.append(
                ShotCandidate(
                    t_impact=onset.t,
                    confidence=onset.confidence,
                    clip_key=clip_key,
                )
            )
        return candidates
