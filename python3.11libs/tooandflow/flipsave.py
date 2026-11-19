"""Main entry: ``tooandflow.flipsave.run(fmt)``.

Called from the shelf tool. Orchestrates:

  1. Validate hip
  2. Resolve paths (date + scene + roman)
  3. Save the working hip, then shutil-copy to the dated path
  4. Maximise viewport
  5. Flipbook to JPG (always — used directly for JPG/MP4 modes, also written
     when EXR is selected as a side artefact? — actually no, EXR is its own
     output. We write only the requested format.)
  6. For MP4: encode JPG sequence via hffmpeg, cleanup unless prefs say keep
  7. Restore viewport
  8. Notify with Reveal-in-Finder dialog
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import encoders, paths, prefs, viewport


VALID_FORMATS = {"mp4", "jpg", "exr"}


def run(fmt: str = "mp4") -> dict:
    """Save dated hip + flipbook in the requested format.

    Returns a dict with the resolved paths (handy for unit-style introspection
    and for tests). Returns ``{"ok": False, "reason": ...}`` on bail conditions.
    """
    import hou

    fmt = fmt.lower().strip()
    if fmt not in VALID_FORMATS:
        raise ValueError(f"unknown format {fmt!r}; expected one of {sorted(VALID_FORMATS)}")

    settings = prefs.load()

    # 1. Validate hip path
    hip_path = hou.hipFile.path()
    if not hip_path or Path(hip_path).name.startswith("untitled"):
        hou.ui.displayMessage(
            "Save your scene first — tooandflow won't flipbook an untitled hip.",
            severity=hou.severityType.Warning,
            title="tooandflow",
        )
        return {"ok": False, "reason": "untitled"}

    # 2. Resolve output paths
    p = paths.build_paths(hip_path)
    folder: Path = p["folder"]
    folder.mkdir(parents=True, exist_ok=True)

    # 3. Save working file + dated copy
    try:
        hou.hipFile.save()
    except hou.OperationFailed as e:
        hou.ui.displayMessage(f"Could not save working hip: {e}", severity=hou.severityType.Error,
                              title="tooandflow")
        return {"ok": False, "reason": "save_failed"}
    shutil.copy2(hou.hipFile.path(), p["hip"])
    print(f"[tooandflow] dated hip -> {p['hip']}")

    # 4. Optionally maximise the viewport. Off by default: a bigger pane is a
    #    different aspect ratio, and the point of the tool is what you *saw*.
    vp_state = {}
    if settings.get("maximise_viewport", False):
        vp_state = viewport.maximise()
        viewport.settle()

    # 5. Build flipbook + run
    final_output: Path
    try:
        sv = next((t for t in hou.ui.paneTabs() if isinstance(t, hou.SceneViewer)), None)
        if sv is None:
            raise RuntimeError("no SceneViewer pane found")

        fb = sv.flipbookSettings().stash()

        # playbackRange() = $RFSTART/$RFEND (the playbar's range); frameRange() is
        # the global $FSTART/$FEND, which ignores a trimmed playback range.
        f_start, f_end = hou.playbar.playbackRange()
        fb.frameRange((f_start, f_end))
        fb.outputToMPlay(False)

        # Resolution: match the viewport, full stop.
        #
        # GOTCHA (verified H22.0.429): with useResolution(True) Houdini honours
        # only the *width* you hand it — the height is always conformed to the
        # viewport's aspect ratio. Asking for 1024x1024 on a 1.96:1 viewport
        # writes 1024x522. So we don't ask: useResolution(False) is the API
        # equivalent of the flipbook dialog's "Use Viewport" and gives the
        # viewport's true device-pixel size (3980x2026 on a maximised pane on
        # this Retina Mac, where viewport.size() reports 1322x1013 points).
        res_override = settings.get("resolution_override")
        if res_override and isinstance(res_override, (list, tuple)) and len(res_override) == 2:
            rx, ry = int(res_override[0]), int(res_override[1])
            fb.useResolution(True)
            fb.resolution((rx, ry))
            res_note = (f"override {rx}x{ry} (width wins; Houdini conforms the "
                        f"height to the viewport aspect)")
        else:
            fb.useResolution(False)          # == "Use Viewport" in the dialog
            res_note = "viewport (as-seen)"

        # Output path depends on format
        if fmt == "mp4":
            fb.output(p["jpg_pattern"])
        elif fmt == "jpg":
            fb.output(p["jpg_pattern"])
        elif fmt == "exr":
            fb.output(p["exr_pattern"])
        print(f"[tooandflow] flipbook -> {fb.output()} @ {res_note}  "
              f"frames {int(f_start)}..{int(f_end)}")

        sv.flipbook(sv.curViewport(), fb)

        # Report what actually landed on disk, not what we asked for.
        pattern = p["exr_pattern"] if fmt == "exr" else p["jpg_pattern"]
        actual_res = viewport.probe_resolution(paths.frame_path(pattern, int(f_start)))
        if actual_res:
            print(f"[tooandflow] wrote {actual_res[0]}x{actual_res[1]}")

        if fmt == "mp4":
            encoders.encode_mp4(
                paths.jpg_glob_pattern(p["jpg_pattern"]),
                p["mp4"],
                fps=hou.fps(),
                crf=int(settings.get("mp4_crf", 16)),
                preset=str(settings.get("mp4_preset", "slow")),
                start_frame=int(f_start),
            )
            if not settings.get("keep_jpg_intermediate", False):
                removed = encoders.cleanup_frames(folder, p["base"])
                print(f"[tooandflow] cleaned {removed} intermediate jpg frames")
            final_output = p["mp4"]
        elif fmt == "jpg":
            final_output = folder  # whole sequence — open the folder
        else:  # exr
            final_output = folder

    finally:
        # 7. Restore viewport (even if flipbook raised)
        viewport.restore(vp_state)

    # 8. Notify + reveal
    prefs.save({"last_format": fmt})

    if settings.get("notify_when_done", True):
        choice = hou.ui.displayMessage(
            f"tooandflow done\n\n  hip:    {p['hip']}\n  render: {final_output}",
            buttons=("Reveal in Finder", "OK"),
            default_choice=0,
            close_choice=1,
            title="tooandflow",
        )
        if choice == 0:
            try:
                subprocess.Popen(["open", "-R", str(final_output)])
            except OSError as e:
                print(f"[tooandflow] reveal failed: {e!r}")

    return {
        "ok": True,
        "fmt": fmt,
        "hip": p["hip"],
        "render": final_output,
        "roman": p["roman"],
        "frames": (int(f_start), int(f_end)),
        "resolution": actual_res,
    }
