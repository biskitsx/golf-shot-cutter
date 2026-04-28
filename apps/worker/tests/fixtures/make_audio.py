import numpy as np
import soundfile as sf


def synth_two_impacts(out_path: str, sr: int = 22050, duration_s: float = 5.0) -> None:
    """Write a WAV with two impact-like bursts at t=1.0s and t=3.0s."""
    n = int(sr * duration_s)
    sig = np.zeros(n, dtype=np.float32)

    rng = np.random.default_rng(seed=42)
    for t_burst in (1.0, 3.0):
        start = int(t_burst * sr)
        burst_len = int(0.05 * sr)
        envelope = np.exp(-np.linspace(0, 5, burst_len)).astype(np.float32)
        burst = rng.standard_normal(burst_len).astype(np.float32) * envelope
        sig[start : start + burst_len] += burst

    sig += rng.standard_normal(n).astype(np.float32) * 0.005

    sf.write(out_path, sig, sr)
