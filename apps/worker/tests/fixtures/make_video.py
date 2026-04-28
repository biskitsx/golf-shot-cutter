import subprocess


def synth_test_video(out_path: str, duration_s: int = 5) -> None:
    """Generate a small mp4 with a color-changing test pattern + silent audio.

    Uses ffmpeg's testsrc + anullsrc filters; no external assets needed.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration_s}:size=320x240:rate=30",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=22050",
        "-shortest",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-t",
        str(duration_s),
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
