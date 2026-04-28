import os
import tempfile

import pytest

from worker_app.pipeline.audio_onset_librosa import LibrosaAudioOnsetDetector
from fixtures.make_audio import synth_two_impacts


@pytest.fixture
def synth_wav():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "synth.wav")
        synth_two_impacts(path)
        yield path


def test_detects_both_impacts(synth_wav):
    detector = LibrosaAudioOnsetDetector(min_separation_seconds=0.5)
    onsets = detector.detect(synth_wav)
    times = [o.t for o in onsets]

    found_first = any(abs(t - 1.0) < 0.2 for t in times)
    found_second = any(abs(t - 3.0) < 0.2 for t in times)
    assert found_first, f"missed first impact (~1.0s); got {times}"
    assert found_second, f"missed second impact (~3.0s); got {times}"


def test_min_separation_dedupes_close_events(synth_wav):
    detector = LibrosaAudioOnsetDetector(min_separation_seconds=0.05)
    onsets = detector.detect(synth_wav)
    times = sorted(o.t for o in onsets)
    for a, b in zip(times, times[1:]):
        assert b - a >= 0.05
