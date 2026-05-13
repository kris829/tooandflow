"""Maximise / restore the SceneViewer pane.

We don't strip the HUD — the whole point of tooandflow is the flipbook
captures *exactly* what's in the viewport, including overlays. We just want
the pane to be as large as the screen allows so the capture is high-res.

Houdini's pane-maximise API has shuffled between versions, so this module is
deliberately defensive: every attempt is wrapped, and on any failure we log
a console warning and continue. The flipbook itself still uses
``useResolution(True)`` so output quality is never gated on this working.
"""

from __future__ import annotations

from typing import Any


def _get_scene_viewer():
    import hou  # local import — module must be safely importable outside Houdini
    return next((t for t in hou.ui.paneTabs() if isinstance(t, hou.SceneViewer)), None)


def maximise() -> dict[str, Any]:
    """Try to maximise the current SceneViewer pane.

    Returns an opaque token that :func:`restore` knows how to undo.
    On any failure returns an empty dict — restore() is a no-op.
    """
    state: dict[str, Any] = {}
    try:
        sv = _get_scene_viewer()
        if sv is None:
            return state
        pane = sv.pane()
        # Modern API on Houdini 20+ — best path
        if hasattr(pane, "setIsMaximumSize") and hasattr(pane, "isMaximumSize"):
            state["pane"] = pane
            state["was_max"] = pane.isMaximumSize()
            pane.setIsMaximumSize(True)
            return state
        # Older fallback: switch the pane to current tab focus at least
        if hasattr(sv, "setIsCurrentTab"):
            sv.setIsCurrentTab()
        state["pane"] = pane
        state["was_max"] = None  # marker: we didn't actually change anything
        print("[tooandflow] viewport.maximise: pane.setIsMaximumSize not available; "
              "flipbook will use whatever pane size is current")
    except Exception as e:
        print(f"[tooandflow] viewport.maximise failed silently: {e!r}")
    return state


def restore(state: dict[str, Any]) -> None:
    """Undo whatever :func:`maximise` did."""
    if not state:
        return
    try:
        pane = state.get("pane")
        was = state.get("was_max")
        if pane is not None and was is not None and hasattr(pane, "setIsMaximumSize"):
            pane.setIsMaximumSize(bool(was))
    except Exception as e:
        print(f"[tooandflow] viewport.restore failed silently: {e!r}")


def detect_resolution(default=(1920, 1080)) -> tuple[int, int]:
    """Pick a flipbook resolution.

    Priority:
      1. Current camera's resx / resy (if a camera is looked-through)
      2. The current viewport's pixel size
      3. ``default``
    """
    try:
        import hou
        sv = _get_scene_viewer()
        if sv is not None:
            cam = sv.curViewport().camera()
            if cam is not None:
                rx = cam.parm("resx")
                ry = cam.parm("resy")
                if rx is not None and ry is not None:
                    return int(rx.eval()), int(ry.eval())
            # Viewport size fallback
            size = sv.curViewport().size()
            if size and size[0] > 0 and size[1] > 0:
                return int(size[0]), int(size[1])
    except Exception as e:
        print(f"[tooandflow] viewport.detect_resolution falling back: {e!r}")
    return default
