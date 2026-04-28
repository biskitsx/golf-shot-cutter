from app.services.processing_service import ShotCandidate
from worker_app.pipeline.pipeline import Pipeline
from worker_app.pipeline.types import Onset


class FakeAudioDetector:
    def __init__(self, onsets: list[Onset]) -> None:
        self._onsets = onsets

    def detect(self, audio_path: str) -> list[Onset]:
        return self._onsets


class FakePoseVerifier:
    def __init__(self, accept_all: bool = True) -> None:
        self._accept = accept_all

    def verify(self, video_path: str, t_impact: float) -> bool:
        return self._accept


class FakeClipCutter:
    def __init__(self) -> None:
        self.calls: list[tuple[float, float, str]] = []

    def cut(self, *, source_path: str, t_start: float, t_end: float, out_path: str) -> None:
        self.calls.append((t_start, t_end, out_path))


def test_pipeline_runs_end_to_end_with_two_onsets(tmp_path):
    audio = FakeAudioDetector(
        [
            Onset(t=10.0, confidence=0.9),
            Onset(t=30.0, confidence=0.85),
        ]
    )
    pose = FakePoseVerifier(accept_all=True)
    cutter = FakeClipCutter()

    pipeline = Pipeline(
        audio_onset=audio,
        pose_verifier=pose,
        clip_cutter=cutter,
    )

    clips_dir = str(tmp_path / "clips")
    candidates = pipeline.run(
        session_id="ses_1",
        source_video_path="/tmp/v.mp4",
        clips_dir=clips_dir,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
    )

    assert len(candidates) == 2
    assert all(isinstance(c, ShotCandidate) for c in candidates)
    assert candidates[0].t_impact == 10.0
    assert candidates[1].t_impact == 30.0
    assert candidates[0].clip_key == "clips/ses_1/shot_001.mp4"
    assert candidates[1].clip_key == "clips/ses_1/shot_002.mp4"

    expected_calls = [
        (8.0, 15.0, f"{clips_dir}/shot_001.mp4"),
        (28.0, 35.0, f"{clips_dir}/shot_002.mp4"),
    ]
    assert cutter.calls == expected_calls


def test_pipeline_filters_pose_rejected_onsets(tmp_path):
    audio = FakeAudioDetector(
        [
            Onset(t=10.0, confidence=0.9),
            Onset(t=30.0, confidence=0.85),
        ]
    )

    class _PartialPose:
        def verify(self, video_path: str, t_impact: float) -> bool:
            return t_impact < 20.0

    cutter = FakeClipCutter()
    pipeline = Pipeline(
        audio_onset=audio,
        pose_verifier=_PartialPose(),
        clip_cutter=cutter,
    )
    candidates = pipeline.run(
        session_id="ses_1",
        source_video_path="/tmp/v.mp4",
        clips_dir=str(tmp_path / "clips"),
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
    )
    assert len(candidates) == 1
    assert candidates[0].t_impact == 10.0


def test_pipeline_clamps_t_start_to_zero(tmp_path):
    audio = FakeAudioDetector([Onset(t=1.0, confidence=0.9)])
    pipeline = Pipeline(
        audio_onset=audio,
        pose_verifier=FakePoseVerifier(),
        clip_cutter=FakeClipCutter(),
    )
    candidates = pipeline.run(
        session_id="ses_x",
        source_video_path="/tmp/v.mp4",
        clips_dir=str(tmp_path / "clips"),
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
    )
    assert candidates[0].t_impact == 1.0


def test_pipeline_returns_empty_when_no_onsets(tmp_path):
    audio = FakeAudioDetector([])
    pipeline = Pipeline(
        audio_onset=audio,
        pose_verifier=FakePoseVerifier(),
        clip_cutter=FakeClipCutter(),
    )
    candidates = pipeline.run(
        session_id="ses_1",
        source_video_path="/tmp/v.mp4",
        clips_dir=str(tmp_path / "clips"),
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
    )
    assert candidates == []
