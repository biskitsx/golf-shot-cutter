import os
import shutil
import subprocess

import pytest

from worker_app.pipeline.clip_cutter_ffmpeg import FfmpegClipCutter
from fixtures.make_video import synth_test_video


@pytest.fixture
def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@pytest.fixture
def sample_video(has_ffmpeg, tmp_path):
    if not has_ffmpeg:
        pytest.skip("ffmpeg/ffprobe not on PATH")
    path = str(tmp_path / "v.mp4")
    synth_test_video(path, duration_s=5)
    return path


def test_cut_produces_clip_of_expected_length(sample_video: str, tmp_path):
    out_path = str(tmp_path / "clip.mp4")
    cutter = FfmpegClipCutter()
    cutter.cut(source_path=sample_video, t_start=1.0, t_end=4.0, out_path=out_path)

    assert os.path.exists(out_path) and os.path.getsize(out_path) > 0

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            out_path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    duration = float(probe.stdout.strip())
    assert 2.5 < duration < 3.5  # ~3s expected, allow margin for keyframe snapping


def test_cut_rejects_inverted_window(tmp_path):
    cutter = FfmpegClipCutter()
    with pytest.raises(ValueError):
        cutter.cut(
            source_path="/dev/null",
            t_start=5.0,
            t_end=3.0,  # inverted
            out_path=str(tmp_path / "x.mp4"),
        )
