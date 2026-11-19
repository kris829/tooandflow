"""Tiny JSON prefs store living at ``$HOUDINI_USER_PREF_DIR/tooandflow_prefs.json``.

The Houdini dependency is soft — when ``hou`` is unavailable (e.g. running
tests from a shell) we fall back to ``~/.tooandflow_prefs.json``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULTS: dict[str, Any] = {
    "last_format": "mp4",
    "mp4_crf": 16,
    "mp4_preset": "slow",
    "keep_jpg_intermediate": False,
    "resolution_override": None,   # null => match the viewport; else [w, h]
    "maximise_viewport": False,    # True => maximise the pane first (reframes)
    "notify_when_done": True,
    "cops_resolution": [1080, 1080],  # copsave render size (2x-upscale-ready)
    "gif_fps": 15,
    "gif_scale": 0.5,              # 0.5 of cops_resolution => 540x540 gifs
}


def _prefs_path() -> Path:
    """Resolve the prefs file location. Prefers ``$HOUDINI_USER_PREF_DIR``."""
    try:
        import hou  # type: ignore
        root = hou.expandString("$HOUDINI_USER_PREF_DIR")
        if root:
            return Path(root) / "tooandflow_prefs.json"
    except Exception:
        pass
    return Path.home() / ".tooandflow_prefs.json"


def load() -> dict[str, Any]:
    """Return prefs, with defaults applied for missing keys."""
    path = _prefs_path()
    merged = dict(DEFAULTS)
    if path.exists():
        try:
            merged.update(json.loads(path.read_text()))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[tooandflow] prefs load failed ({e!r}); using defaults")
    return merged


def save(updates: dict[str, Any]) -> None:
    """Merge ``updates`` into the on-disk prefs."""
    path = _prefs_path()
    current = load()
    current.update(updates)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    except OSError as e:
        print(f"[tooandflow] prefs save failed ({e!r})")
