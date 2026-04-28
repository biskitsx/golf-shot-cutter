"""Real PoseVerifier backed by MediaPipe Pose Landmarker (Tasks API).

Filters audio onsets that aren't real golf swings — crowd noise, practice
swings without contact, incidental impacts. Heuristic:

  1. Open the source video, seek to a window around `t_impact`
     (default: [-1.0s, +0.3s]).
  2. Sample every Nth frame and run pose landmarking.
  3. Require pose to be detected in at least `min_pose_detection_rate`
     of samples — i.e., a person is actually in frame.
  4. Compute the per-sample displacement of either wrist; require the peak
     to clear `min_wrist_velocity`. A real swing produces a sharp peak;
     ambient motion does not.

The MediaPipe landmarker model (.task file, ~5.5 MB) is auto-downloaded
from Google's public model registry on first use and cached under
`$GOLF_MODEL_CACHE` (default `~/.cache/golf-shot-cutter/`).
"""

from __future__ import annotations

import logging
import os
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

logger = logging.getLogger(__name__)

# Lite variant: small (~5.5MB), fast, good enough for golf-stance verification.
# Heavy/full variants live at the same URL prefix with different folder names
# if you ever want to swap up.
DEFAULT_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)


def _cache_dir() -> Path:
    return Path(
        os.environ.get("GOLF_MODEL_CACHE", str(Path.home() / ".cache" / "golf-shot-cutter"))
    )


def ensure_pose_model(model_url: str = DEFAULT_MODEL_URL) -> str:
    """Return a local path to the pose landmarker .task file.

    Downloads on first call and caches; subsequent calls are instant.
    """
    target_dir = _cache_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "pose_landmarker_lite.task"
    if not target.exists():
        logger.info("downloading MediaPipe pose model → %s", target)
        # Stream download with a sane timeout so we don't hang forever.
        with urllib.request.urlopen(model_url, timeout=60) as resp:
            target.write_bytes(resp.read())
        logger.info("MediaPipe pose model cached (%d bytes)", target.stat().st_size)
    return str(target)


class MediaPipePoseVerifier:
    # MediaPipe Pose landmark indices.
    _LEFT_WRIST = 15
    _RIGHT_WRIST = 16

    def __init__(
        self,
        *,
        sample_every_n_frames: int = 3,
        pre_window_seconds: float = 1.0,
        post_window_seconds: float = 0.3,
        min_pose_detection_rate: float = 0.5,
        min_wrist_velocity: float = 0.05,
        model_path: str | None = None,
    ) -> None:
        self._sample_every = sample_every_n_frames
        self._pre = pre_window_seconds
        self._post = post_window_seconds
        self._min_pose_rate = min_pose_detection_rate
        self._min_wrist_v = min_wrist_velocity
        self._model_path = model_path
        # Lazy: first verify() call constructs the landmarker (and triggers
        # the model download if needed). Tests that hit the missing-video
        # path can run without network.
        self._landmarker: vision.PoseLandmarker | None = None

    def __del__(self) -> None:
        try:
            if self._landmarker is not None:
                self._landmarker.close()
        except Exception:
            pass

    def _get_landmarker(self) -> vision.PoseLandmarker:
        if self._landmarker is not None:
            return self._landmarker
        path = self._model_path or ensure_pose_model()
        base_options = mp_python.BaseOptions(model_asset_path=path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        return self._landmarker

    def verify(self, video_path: str, t_impact: float) -> bool:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning("pose verifier: could not open %s", video_path)
            return False

        try:
            landmarker = self._get_landmarker()
        except Exception as exc:  # network failure, missing file, etc.
            logger.error("pose verifier: model unavailable, skipping verify (%s)", exc)
            cap.release()
            return False

        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            t_start = max(0.0, t_impact - self._pre)
            t_end = t_impact + self._post
            start_frame = int(t_start * fps)
            end_frame = int(t_end * fps)

            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

            wrist_l: list[tuple[float, float]] = []
            wrist_r: list[tuple[float, float]] = []
            detections = 0
            samples = 0

            frame_idx = start_frame
            while frame_idx <= end_frame:
                ok, frame = cap.read()
                if not ok:
                    break

                if (frame_idx - start_frame) % self._sample_every == 0:
                    samples += 1
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    result = landmarker.detect(mp_image)
                    if result.pose_landmarks:
                        detections += 1
                        pose = result.pose_landmarks[0]
                        wrist_l.append((pose[self._LEFT_WRIST].x, pose[self._LEFT_WRIST].y))
                        wrist_r.append((pose[self._RIGHT_WRIST].x, pose[self._RIGHT_WRIST].y))

                frame_idx += 1

            if samples == 0:
                return False

            pose_rate = detections / samples
            if pose_rate < self._min_pose_rate:
                logger.debug(
                    "pose verifier: rejecting t=%.2fs (pose rate %.2f < %.2f)",
                    t_impact,
                    pose_rate,
                    self._min_pose_rate,
                )
                return False

            peak_v = max(_peak_velocity(wrist_l), _peak_velocity(wrist_r))
            if peak_v < self._min_wrist_v:
                logger.debug(
                    "pose verifier: rejecting t=%.2fs (peak wrist v %.4f < %.4f)",
                    t_impact,
                    peak_v,
                    self._min_wrist_v,
                )
                return False

            return True
        finally:
            cap.release()


def _peak_velocity(positions: list[tuple[float, float]]) -> float:
    if len(positions) < 2:
        return 0.0
    return max(
        ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        for a, b in zip(positions[:-1], positions[1:], strict=False)
    )
