import subprocess


class FfmpegClipCutter:
    """Stream-copy clip cutter via ffmpeg subprocess.

    Uses `-ss -to -c copy` for fast cuts without re-encoding. Quality stays
    identical to source; cuts may snap to nearest keyframe.
    """

    def cut(self, *, source_path: str, t_start: float, t_end: float, out_path: str) -> None:
        if t_end <= t_start:
            raise ValueError("t_end must be greater than t_start")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(t_start),
                "-to",
                str(t_end),
                "-i",
                source_path,
                "-c",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                out_path,
            ],
            check=True,
            capture_output=True,
        )
