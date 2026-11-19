"""COP flipbook + save: ``tooandflow.copsave.run(fmt)``.

Same contract as :mod:`flipsave`, but the source is a selected Copernicus
node instead of the viewport. A temporary ``rop_image`` node is created next
to the selection, pointed at it via ``coppath``, rendered over the playbar
range, then destroyed — so there is never any manual ROP setup.

Formats: mp4 (default), jpg, exr, gif.

  * mp4 / jpg / gif render JPGs with the OCIO display/view baked in
    (``colorconversion = bakeocio``) so the output matches the COP viewer.
  * exr renders linear (``colorconversion = ocio``) — a real pipeline export.

Resolution is forced via the rop's Default Resolution (``setres`` / ``res``),
default 1080x1080 (prefs key ``cops_resolution``) so everything is ready for
a clean 2x upscale in Resolve. Set that pref to ``null`` to render the COP at
its own native resolution instead.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import encoders, paths, prefs, viewport

VALID_FORMATS = {"mp4", "jpg", "exr", "gif"}

_TMP_ROP_NAME = "tooandflow_copsave_tmp"


def _find_target_cop():
    """Return the COP node to render, from the current selection.

    Accepts either a Copernicus node itself, or a network container
    (copnet) — in which case its display node is used.
    """
    import hou

    for node in hou.selectedNodes():
        if node.type().category().name() == "Cop":
            return node
        child_cat = node.childTypeCategory()
        if child_cat is not None and child_cat.name() == "Cop":
            disp = node.displayNode()
            if disp is not None:
                return disp
    return None


def run(fmt: str = "mp4") -> dict:
    """Render the selected COP node + save a dated hip. Mirrors flipsave.run."""
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

    # 2. Find the COP node to render
    target = _find_target_cop()
    if target is None:
        hou.ui.displayMessage(
            "Select a Copernicus node (or a copnet) first — tooandflow needs "
            "to know what to render.",
            severity=hou.severityType.Warning,
            title="tooandflow",
        )
        return {"ok": False, "reason": "no_cop_selected"}

    # 3. Resolve output paths
    p = paths.build_paths(hip_path)
    folder: Path = p["folder"]
    folder.mkdir(parents=True, exist_ok=True)
    gif_path = folder / f"{p['base']}.gif"

    # 4. Save working file + dated copy
    try:
        hou.hipFile.save()
    except hou.OperationFailed as e:
        hou.ui.displayMessage(f"Could not save working hip: {e}", severity=hou.severityType.Error,
                              title="tooandflow")
        return {"ok": False, "reason": "save_failed"}
    shutil.copy2(hou.hipFile.path(), p["hip"])
    print(f"[tooandflow] dated hip -> {p['hip']}")

    # 5. Temp rop_image -> render -> destroy
    # cops_resolution: [w, h] forces the rop's Default Resolution; null means
    # "leave it alone" and the COP renders at its own native resolution — i.e.
    # what the Composite View shows. Default stays 1080x1080 (square master).
    res = settings.get("cops_resolution")
    use_res = bool(res and isinstance(res, (list, tuple)) and len(res) == 2)
    rx, ry = (int(res[0]), int(res[1])) if use_res else (0, 0)
    # playbackRange() = $RFSTART/$RFEND; frameRange() is the global $FSTART/$FEND
    f_start, f_end = hou.playbar.playbackRange()

    final_output: Path
    rop = None
    try:
        with hou.undos.group("tooandflow copsave"):
            rop = target.parent().createNode("rop_image", _TMP_ROP_NAME)
            rop.parm("coppath").set(rop.relativePathTo(target))
            rop.parm("trange").set("normal")
            # f1/f2 default to $FSTART/$FEND expressions — kill them or set() is ignored
            for parm in rop.parmTuple("f"):
                parm.deleteAllKeyframes()
            rop.parmTuple("f").set((f_start, f_end, 1))
            rop.parm("setres").set(1 if use_res else 0)
            if use_res:
                rop.parmTuple("res").set((rx, ry))
            rop.parm("mkpath").set(1)

            if fmt == "exr":
                rop.parm("colorconversion").set("ocio")   # linear, pipeline-grade
                rop.parm("copoutput").set(p["exr_pattern"])
            else:
                rop.parm("colorconversion").set("bakeocio")  # match the COP viewer
                rop.parm("copoutput").set(p["jpg_pattern"])

            res_note = f"{rx}x{ry}" if use_res else "COP native res"
            print(f"[tooandflow] copsave {target.path()} -> {rop.parm('copoutput').unexpandedString()} "
                  f"@ {res_note}  frames {int(f_start)}..{int(f_end)}")
            rop.render()

        # Report what actually landed on disk.
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
            final_output = p["mp4"]
        elif fmt == "gif":
            encoders.encode_gif(
                paths.jpg_glob_pattern(p["jpg_pattern"]),
                gif_path,
                fps=hou.fps(),
                gif_fps=float(settings.get("gif_fps", 15)),
                scale=float(settings.get("gif_scale", 0.5)),
                start_frame=int(f_start),
            )
            final_output = gif_path
        elif fmt == "jpg":
            final_output = folder
        else:  # exr
            final_output = folder

        if fmt in ("mp4", "gif") and not settings.get("keep_jpg_intermediate", False):
            removed = encoders.cleanup_frames(folder, p["base"])
            print(f"[tooandflow] cleaned {removed} intermediate jpg frames")

    finally:
        # Destroy the temp rop even if the render raised or was interrupted
        if rop is not None:
            try:
                rop.destroy()
            except hou.ObjectWasDeleted:
                pass

    # 6. Notify + reveal
    prefs.save({"last_format": fmt})

    if settings.get("notify_when_done", True):
        choice = hou.ui.displayMessage(
            f"tooandflow copsave done\n\n  hip:    {p['hip']}\n  render: {final_output}",
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
        "cop": target.path(),
        "hip": p["hip"],
        "render": final_output,
        "frames": (int(f_start), int(f_end)),
        "resolution": actual_res,
    }
