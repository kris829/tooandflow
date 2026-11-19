"""MP4 encode for tooandflow.

Prefers a real ``ffmpeg`` with the ``libx264`` encoder (standard, maximally
compatible output) and falls back to Houdini's bundled ``hffmpeg`` — which on
macOS ships *without* libx264, so we use ``h264_videotoolbox``/``mpeg4`` there.

Always writes a limited-range ``yuv420p`` H.264 with ``+faststart`` so the
result plays in QuickTime, browsers, and mobile (the bundled hffmpeg's
videotoolbox path otherwise emits full-range ``yuvj420p`` that some players
display as a single frame).
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


def _encoders_list(binary: str) -> str:
    try:
        return subprocess.run([binary, "-hide_banner", "-encoders"],
                              capture_output=True, text=True).stdout
    except OSError:
        return ""


def _pick_ffmpeg() -> tuple[str, str, bool]:
    """Return ``(binary, encoder, use_crf)``.

    Prefers a real ffmpeg (Homebrew/system) with ``libx264``; else falls back
    to bundled hffmpeg with the best available encoder.
    """
    for cand in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg",
                 shutil.which("ffmpeg") or ""):
        if cand and Path(cand).exists() and "libx264" in _encoders_list(cand):
            return cand, "libx264", True
    hff = _hffmpeg_path()
    avail = _encoders_list(hff)
    for enc in ("libx264", "h264_videotoolbox", "libopenh264", "mpeg4"):
        if enc in avail:
            return hff, enc, enc == "libx264"
    return hff, "mpeg4", False


def encode_mp4(
    frame_pattern: str,
    out_mp4: str | os.PathLike[str],
    *,
    fps: float,
    crf: int = 16,
    preset: str = "slow",
    start_frame: int = 1,
) -> Path:
    """Encode an image sequence into a widely-compatible H.264 MP4.

    ``frame_pattern`` is the printf-style pattern (e.g. ``.../foo.%04d.jpg``).
    """
    out = Path(out_mp4)
    out.parent.mkdir(parents=True, exist_ok=True)

    binary, enc, use_crf = _pick_ffmpeg()

    cmd = [
        binary,
        "-y",
        "-framerate", str(fps),
        "-start_number", str(start_frame),
        "-i", str(frame_pattern),
        "-c:v", enc,
    ]
    if use_crf:
        cmd += ["-crf", str(crf), "-preset", preset]
    else:
        cmd += ["-b:v", "12M"]
    cmd += [
        "-pix_fmt", "yuv420p",
        "-color_range", "tv",
        # Pad odd dimensions so the encoder doesn't choke on viewport sizes
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-movflags", "+faststart",
        str(out),
    ]
    print("[tooandflow] encode:", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise RuntimeError(f"encode failed (rc={proc.returncode}) with {enc}")
    tail = "\n".join(proc.stderr.strip().splitlines()[-5:])
    print(tail)
    return out


def encode_gif(
    frame_pattern: str,
    out_gif: str | os.PathLike[str],
    *,
    fps: float,
    gif_fps: float = 15,
    scale: float = 0.5,
    start_frame: int = 1,
    max_colors: int = 256,
) -> Path:
    """Encode an image sequence into a palette-optimised GIF.

    Frames are resampled to ``gif_fps`` and scaled by ``scale`` (0.5 of a
    1080x1080 master = 540x540) to keep file size sane. Uses the
    palettegen/paletteuse two-stage filter in a single pass via ``split``.
    """
    out = Path(out_gif)
    out.parent.mkdir(parents=True, exist_ok=True)

    binary, _enc, _crf = _pick_ffmpeg()  # gif encoder is built into every build

    filtergraph = (
        f"[0:v]fps={gif_fps},scale=iw*{scale}:-1:flags=lanczos,split[a][b];"
        f"[a]palettegen=max_colors={max_colors}:stats_mode=diff[p];"
        f"[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle"
    )
    cmd = [
        binary,
        "-y",
        "-framerate", str(fps),
        "-start_number", str(start_frame),
        "-i", str(frame_pattern),
        "-filter_complex", filtergraph,
        "-loop", "0",
        str(out),
    ]
    print("[tooandflow] encode gif:", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise RuntimeError(f"gif encode failed (rc={proc.returncode})")
    size_mb = out.stat().st_size / 1e6
    print(f"[tooandflow] gif -> {out} ({size_mb:.1f} MB)")
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
