"""Maximise / restore the SceneViewer pane.

We don't strip the HUD — the whole point of tooandflow is the flipbook
captures *exactly* what's in the viewport, including overlays.

Maximising is *off* by default (prefs ``maximise_viewport``): growing the pane
changes the viewport aspect, so the capture would no longer be framed like the
one you clicked on. Turn it on when you want the biggest capture the screen
allows and don't mind the reframe.

Houdini's pane-maximise API has shuffled between versions, so this module is
deliberately defensive: every attempt is wrapped, and on any failure we log
a console warning and continue. The flipbook itself renders at the
viewport's own resolution (``useResolution(False)``), so output size follows
whatever pane size we end up with.
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
        # H19-H22: hou.Pane.isMaximized() / setIsMaximized(). The old name this
        # module used to probe for ("setIsMaximumSize") does not exist on any
        # build here, so maximise() was a silent no-op — see AGENTS.md.
        if hasattr(pane, "setIsMaximized") and hasattr(pane, "isMaximized"):
            state["pane"] = pane
            state["was_max"] = pane.isMaximized()
            pane.setIsMaximized(True)
            return state
        # Older fallback: switch the pane to current tab focus at least
        if hasattr(sv, "setIsCurrentTab"):
            sv.setIsCurrentTab()
        state["pane"] = pane
        state["was_max"] = None  # marker: we didn't actually change anything
        print("[tooandflow] viewport.maximise: pane.setIsMaximized not available; "
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
        if pane is not None and was is not None and hasattr(pane, "setIsMaximized"):
            pane.setIsMaximized(bool(was))
    except Exception as e:
        print(f"[tooandflow] viewport.restore failed silently: {e!r}")


def viewport_size(default=(1920, 1080)) -> tuple[int, int]:
    """Best-effort *estimate* of the current viewport size, in UI points.

    ``hou.GeometryViewport.size()`` returns ``(x, y, width, height)`` — the
    first two are the origin, not the size — and on a Retina display the
    numbers are UI points while the flipbook renders in device pixels. So this
    is an estimate for logging / fallback only. Never trust it as the flipbook
    resolution: let Houdini use the viewport's own resolution instead
    (``FlipbookSettings.useResolution(False)``).
    """
    try:
        import hou
        sv = _get_scene_viewer()
        if sv is not None:
            size = sv.curViewport().size()
            if size and len(size) >= 4 and size[2] > 0 and size[3] > 0:
                return int(size[2]), int(size[3])
    except Exception as e:
        print(f"[tooandflow] viewport.viewport_size falling back: {e!r}")
    return default


def detect_resolution(default=(1920, 1080), *, prefer_camera: bool = False) -> tuple[int, int]:
    """Pick a fallback flipbook resolution.

    Viewport first — matching the viewport is the whole point of this tool.
    The camera's ``resx``/``resy`` is only consulted when ``prefer_camera`` is
    asked for explicitly; it used to win by default, which is how a 1024x1024
    camera turned a 3980x2026 viewport into a 1024x522 MP4.
    """
    if prefer_camera:
        try:
            sv = _get_scene_viewer()
            if sv is not None:
                cam = sv.curViewport().camera()
                if cam is not None:
                    rx, ry = cam.parm("resx"), cam.parm("resy")
                    if rx is not None and ry is not None:
                        return int(rx.eval()), int(ry.eval())
        except Exception as e:
            print(f"[tooandflow] viewport.detect_resolution camera lookup failed: {e!r}")
    return viewport_size(default)


def settle() -> None:
    """Let the UI catch up so a resized pane reports its new size.

    ``maximise()`` only flips a flag; the GL surface resizes on the next UI
    pass. Flipbooking immediately after can capture the *old* size.
    """
    try:
        import hou
        if hasattr(hou.ui, "triggerUpdate"):
            hou.ui.triggerUpdate()
        if hasattr(hou.ui, "waitUntil"):
            hou.ui.waitUntil(lambda: True)
    except Exception as e:
        print(f"[tooandflow] viewport.settle skipped: {e!r}")


def probe_resolution(path) -> tuple[int, int] | None:
    """Read back the real pixel size of a rendered frame, or ``None``.

    Used to report what the flipbook *actually* wrote rather than what we
    asked for — Houdini conforms flipbook height to the viewport aspect.
    """
    try:
        import hou
        from pathlib import Path as _P
        if path and _P(path).exists():
            w, h = hou.imageResolution(str(path))
            return int(w), int(h)
    except Exception as e:
        print(f"[tooandflow] viewport.probe_resolution failed: {e!r}")
    return None
