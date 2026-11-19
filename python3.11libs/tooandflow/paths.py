"""Date / scene-stem / roman-numeral / output path helpers.

Pure Python — no ``hou`` import — so the logic is testable from the shell.
"""

from __future__ import annotations

import datetime
import os
import re
from pathlib import Path


_ROMAN_RE = re.compile(r"^[ivxlcdm]+$")


def today_string(now: datetime.datetime | None = None) -> str:
    """Return today as ``YYYY_MMDD`` to match the existing flipbook folders."""
    now = now or datetime.datetime.now()
    return now.strftime("%Y_%m%d")


def scene_stem(hip_path: str | os.PathLike[str]) -> str:
    """Return the scene name without extension. ``foo.hiplc`` -> ``foo``."""
    return Path(hip_path).stem


def int_to_roman(n: int) -> str:
    """Lowercase roman numerals — i, ii, iii, iv, v, ..."""
    if n < 1:
        raise ValueError("roman numerals start at 1")
    pairs = (
        (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"),
        (100, "c"),  (90,  "xc"), (50,  "l"), (40,  "xl"),
        (10,  "x"),  (9,   "ix"), (5,   "v"), (4,   "iv"),
        (1,   "i"),
    )
    out = []
    for value, glyph in pairs:
        while n >= value:
            out.append(glyph)
            n -= value
    return "".join(out)


def roman_to_int(s: str) -> int | None:
    """Reverse of ``int_to_roman``. Returns ``None`` for invalid input."""
    if not s or not _ROMAN_RE.match(s):
        return None
    values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    total = 0
    prev = 0
    for ch in reversed(s):
        v = values[ch]
        total += -v if v < prev else v
        prev = v
    return total


def day_folder(hip_path: str | os.PathLike[str], *, date_str: str | None = None) -> Path:
    """``$HIP/flipbook/YYYY_MMDD/<scene_stem>/``.

    Created lazily by callers — this function only computes the path.
    """
    hip = Path(hip_path)
    stem = scene_stem(hip)
    return hip.parent / "flipbook" / (date_str or today_string()) / stem


def next_roman(folder: Path, scene: str, date_str: str) -> str:
    """Scan ``folder`` for existing ``<scene>_<date>_<roman>.hiplc`` files
    and return the next free roman in lowercase.
    """
    if not folder.exists():
        return "i"
    pattern = re.compile(
        rf"^{re.escape(scene)}_{re.escape(date_str)}_([ivxlcdm]+)\.hiplc$",
        re.IGNORECASE,
    )
    highest = 0
    for entry in folder.iterdir():
        m = pattern.match(entry.name)
        if not m:
            continue
        n = roman_to_int(m.group(1).lower())
        if n and n > highest:
            highest = n
    return int_to_roman(highest + 1)


def build_paths(hip_path: str | os.PathLike[str]) -> dict[str, Path | str]:
    """Compute all the output paths for one flipsave run.

    Returns a dict with:

    - ``folder``       — the day folder
    - ``base``         — ``<scene>_<date>_<roman>`` (no extension)
    - ``hip``          — dated hip copy
    - ``mp4``          — mp4 path
    - ``jpg_pattern``  — ``...$F4.jpg`` for Houdini's flipbook
    - ``exr_pattern``  — ``...$F4.exr`` for Houdini's flipbook
    - ``roman``        — the lowercase roman string used
    - ``date_str``     — the ``YYYY_MMDD`` string used
    """
    hip = Path(hip_path)
    stem = scene_stem(hip)
    now = datetime.datetime.now()
    date_str = now.strftime("%Y_%m%d")
    time_str = now.strftime("%H%M%S")
    folder = day_folder(hip, date_str=date_str)
    # Name = HIPNAME_YYYY_MMDD_HHMMSS — unique, sortable, no roman roll-over.
    base = f"{stem}_{date_str}_{time_str}"
    return {
        "folder": folder,
        "base": base,
        "hip": folder / f"{base}.hiplc",
        "mp4": folder / f"{base}.mp4",
        "jpg_pattern": str(folder / f"{base}.$F4.jpg"),
        "exr_pattern": str(folder / f"{base}.$F4.exr"),
        "roman": time_str,
        "date_str": date_str,
    }


def frame_path(pattern: str | os.PathLike[str], frame: int) -> Path:
    """Resolve a ``...$F4.ext`` pattern to one concrete frame on disk.

    ``$F``, ``$F4`` and friends are all handled — ``$F4`` with frame 7 gives
    ``0007``, bare ``$F`` gives ``7``.
    """
    def sub(m: re.Match) -> str:
        width = int(m.group(1)) if m.group(1) else 0
        return str(int(frame)).zfill(width)
    return Path(re.sub(r"\$F(\d*)", sub, str(pattern)))


def jpg_glob_pattern(base_str_pattern: str) -> str:
    """Turn ``...$F4.jpg`` into ``...%04d.jpg`` for ffmpeg input."""
    return base_str_pattern.replace("$F4", "%04d")


def iter_jpg_files(folder: Path, base: str) -> list[Path]:
    """List all rendered frames matching ``<base>.NNNN.jpg`` (sorted)."""
    if not folder.exists():
        return []
    rx = re.compile(rf"^{re.escape(base)}\.\d+\.jpg$")
    return sorted(p for p in folder.iterdir() if rx.match(p.name))
