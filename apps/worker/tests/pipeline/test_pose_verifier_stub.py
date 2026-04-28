from worker_app.pipeline.pose_verifier_stub import StubPoseVerifier


def test_stub_always_returns_true():
    v = StubPoseVerifier()
    assert v.verify("/tmp/x.mp4", 1.0) is True
    assert v.verify("/tmp/x.mp4", 100.0) is True
