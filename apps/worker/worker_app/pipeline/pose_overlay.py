"""Render a clip with the detected pose skeleton drawn on every frame.

Used by the on-demand "show pose" preview. Reads frames with OpenCV, runs
MediaPipe Pose Landmarker in VIDEO mode (smoother tracking), draws the
skeleton with cv2, then pipes raw BGR frames into ffmpeg to encode H.264
yuv420p MP4 (the format that plays in every browser). Audio is dropped —
this is a visual debugging preview.
"""

from __future__ import annotations

import logging
import subprocess

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .pose_verifier_mediapipe import ensure_pose_model

logger = logging.getLogger(__name__)

# MediaPipe Pose 33-landmark skeleton. Subset of edges that read well visually
# (skip face mesh — too cluttered for a swing preview).
_POSE_EDGES: tuple[tuple[int, int], ...] = (
    (11, 12), (11, 13), (13, 15),
    (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (27, 29), (27, 31), (29, 31),
    (24, 26), (26, 28), (28, 30), (28, 32), (30, 32),
    (15, 17), (15, 19), (15, 21), (17, 19),
    (16, 18), (16, 20), (16, 22), (18, 20),
)

_LANDMARK_COLOR = (0, 255, 0)   # green dots
_EDGE_COLOR = (0, 200, 255)     # orange skeleton (BGR)


def _draw_pose(frame, landmarks, width: int, height: int) -> None:
    pts: list[tuple[int, int]] = []
    for lm in landmarks:
        x = int(lm.x * width)
        y = int(lm.y * height)
        pts.append((x, y))

    for a, b in _POSE_EDGES:
        if a < len(pts) and b < len(pts):
            cv2.line(frame, pts[a], pts[b], _EDGE_COLOR, 2, cv2.LINE_AA)

    for x, y in pts:
        cv2.circle(frame, (x, y), 3, _LANDMARK_COLOR, -1, cv2.LINE_AA)


def render_pose_overlay(input_path: str, output_path: str) -> None:
    """Re-render `input_path` to `output_path` with pose skeleton overlaid.

    Output is H.264 / yuv420p MP4 with +faststart for streaming. Audio is
    dropped. Raises subprocess.CalledProcessError if ffmpeg fails.
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise RuntimeError(f"could not open input video: {input_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "bgr24",
        "-r", f"{fps}",
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        "-movflags", "+faststart",
        output_path,
    ]
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    base_options = mp_python.BaseOptions(model_asset_path=ensure_pose_model())
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
    )

    try:
        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            frame_idx = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = int((frame_idx / fps) * 1000)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if result.pose_landmarks:
                    _draw_pose(frame, result.pose_landmarks[0], width, height)

                if proc.stdin is not None:
                    proc.stdin.write(frame.tobytes())
                frame_idx += 1
    finally:
        cap.release()
        if proc.stdin is not None:
            proc.stdin.close()
        rc = proc.wait()
        if rc != 0:
            raise subprocess.CalledProcessError(rc, ffmpeg_cmd)
