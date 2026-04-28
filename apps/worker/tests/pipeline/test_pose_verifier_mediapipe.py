"""Smoke tests for MediaPipePoseVerifier.

Real ML behavior needs real golf-swing footage to validate; that footage is
out of scope for the test suite. These tests cover the orchestration and
the safe-failure paths only:

  - missing video file → False (don't crash the worker)
  - color-bar synthetic video (no person in frame) → False (correctly filtered)
"""

import shutil
import subprocess

import pytest

from worker_app.pipeline.pose_verifier_mediapipe import MediaPipePoseVerifier


@pytest.fixture
def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def test_returns_false_when_video_missing():
    v = MediaPipePoseVerifier()
    assert v.verify("/no/such/file.mp4", t_impact=1.0) is False


def test_returns_false_when_no_person_in_frame(has_ffmpeg, tmp_path):
    if not has_ffmpeg:
        pytest.skip("ffmpeg not on PATH")

    out_path = str(tmp_path / "noperson.mp4")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=3:size=320x240:rate=30",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-t",
            "3",
            out_path,
        ],
        check=True,
        capture_output=True,
    )

    v = MediaPipePoseVerifier(min_pose_detection_rate=0.5)
    # Color test pattern has no human → MediaPipe returns no pose landmarks
    # → pose_rate = 0 < 0.5 → False.
    assert v.verify(out_path, t_impact=1.5) is False
