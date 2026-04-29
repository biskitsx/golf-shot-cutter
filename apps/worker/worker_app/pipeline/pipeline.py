import logging
import os
from concurrent.futures import ThreadPoolExecutor

from app.services.processing_service import ShotCandidate

from .audio_onset import AudioOnsetDetector
from .clip_cutter import ClipCutter
from .pose_verifier import PoseVerifier
from .types import Onset

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(
        self,
        *,
        audio_onset: AudioOnsetDetector,
        pose_verifier: PoseVerifier,
        clip_cutter: ClipCutter,
        max_clip_overlap_fraction: float = 0.5,
        pose_max_workers: int = 4,
    ) -> None:
        self._audio = audio_onset
        self._pose = pose_verifier
        self._cutter = clip_cutter
        self._max_overlap = max_clip_overlap_fraction
        self._pose_workers = max(1, pose_max_workers)

    def run(
        self,
        *,
        session_id: str,
        source_video_path: str,
        clips_dir: str,
        pre_roll_seconds: float,
        post_roll_seconds: float,
        audio_path: str | None = None,
    ) -> list[ShotCandidate]:
        os.makedirs(clips_dir, exist_ok=True)
        audio_source = audio_path or source_video_path
        onsets = self._audio.detect(audio_source)
        verified = self._verify_onsets_parallel(source_video_path, onsets)
        verified = _dedupe_overlapping(
            verified,
            pre_roll_seconds=pre_roll_seconds,
            post_roll_seconds=post_roll_seconds,
            max_overlap_fraction=self._max_overlap,
        )

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

    def _verify_onsets_parallel(self, source_video_path: str, onsets: list[Onset]) -> list[Onset]:
        if not onsets:
            return []
        if self._pose_workers <= 1 or len(onsets) <= 1:
            return [o for o in onsets if self._pose.verify(source_video_path, o.t)]

        def _verify(o: Onset) -> tuple[Onset, bool]:
            return o, self._pose.verify(source_video_path, o.t)

        with ThreadPoolExecutor(max_workers=self._pose_workers) as ex:
            results = list(ex.map(_verify, onsets))
        return [o for o, ok in results if ok]


def _dedupe_overlapping(
    onsets: list[Onset],
    *,
    pre_roll_seconds: float,
    post_roll_seconds: float,
    max_overlap_fraction: float,
) -> list[Onset]:
    """Drop later onsets whose clip windows overlap a previous kept onset by
    more than `max_overlap_fraction` of one clip's duration. The kept onset
    is the higher-confidence of each overlapping pair.

    A single golf swing can produce two close audio peaks (ball impact + ground
    tap, or someone else's club within the same window). After pose verifies
    both, this collapses them so the user sees one clip per swing.
    """
    if not onsets:
        return []

    by_time = sorted(onsets, key=lambda o: o.t)
    clip_dur = pre_roll_seconds + post_roll_seconds
    if clip_dur <= 0 or max_overlap_fraction <= 0:
        return by_time

    kept: list[Onset] = [by_time[0]]
    for nxt in by_time[1:]:
        prev = kept[-1]
        prev_end = prev.t + post_roll_seconds
        nxt_start = max(0.0, nxt.t - pre_roll_seconds)
        overlap = max(0.0, prev_end - nxt_start)
        frac = overlap / clip_dur

        if frac > max_overlap_fraction:
            logger.info(
                "pipeline: merging overlapping onsets t=%.2f & t=%.2f (overlap %.0f%%)",
                prev.t,
                nxt.t,
                frac * 100,
            )
            if nxt.confidence > prev.confidence:
                kept[-1] = nxt
        else:
            kept.append(nxt)

    return kept
