"""MP4 encode via Houdini's bundled ``hffmpeg`` binary.

Discovered at runtime from ``$HFS`` so we don't pin to a Houdini version.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _hffmpeg_path() -> str:
    """Resolve hffmpeg location from ``$HFS`` (Houdini's install dir)."""
    try:
        import hou
        hfs = hou.expandString("$HFS")
    except Exception:
        hfs = os.environ.get("HFS", "")
    if not hfs:
        raise RuntimeError("Could not resolve $HFS — is Houdini running?")
    return str(Path(hfs) / "bin" / "hffmpeg")


def encode_mp4(
    frame_pattern: str,
    out_mp4: str | os.PathLike[str],
    *,
    fps: float,
    crf: int = 16,
    preset: str = "slow",
    start_frame: int = 1,
) -> Path:
    """Encode an image sequence into an MP4 with h264 (CRF, slow preset).

    ``frame_pattern`` is the printf-style pattern (e.g. ``.../foo.%04d.jpg``).
    """
    out = Path(out_mp4)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        _hffmpeg_path(),
        "-y",
        "-framerate", str(fps),
        "-start_number", str(start_frame),
        "-i", str(frame_pattern),
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", preset,
        "-pix_fmt", "yuv420p",
        # Pad odd dimensions so libx264 doesn't choke on viewport sizes
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        str(out),
    ]
    print("[tooandflow] hffmpeg:", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise RuntimeError(f"hffmpeg encode failed (rc={proc.returncode})")
    # Stream the last bit of stderr so we see the summary line
    tail = "\n".join(proc.stderr.strip().splitlines()[-5:])
    print(tail)
    return out


def cleanup_frames(folder: Path, base: str, *, dry_run: bool = False) -> int:
    """Delete all ``<base>.NNNN.jpg`` files in ``folder``. Returns count removed."""
    from . import paths
    frames = paths.iter_jpg_files(folder, base)
    if dry_run:
        return len(frames)
    n = 0
    for f in frames:
        try:
            f.unlink()
            n += 1
        except OSError as e:
            print(f"[tooandflow] could not delete {f}: {e!r}")
    return n
