This is entirely based on ODTools Flipbook & Save, which I own, but it includes a COPs 2.0  version and some extra features, like higher quality MP4's and sequence options

# tooandflow

One-click flipbook + dated-hip-save for SideFX Houdini.

A tiny personal replacement for ODTOOLS' flipbook function. Two shelf
buttons — modifier keys pick the output format.

**Flipsave** — captures the viewport as-seen (HUD, overlays and all):

| Click            | Output                             |
|------------------|------------------------------------|
| Click            | MP4 (h264 CRF 16, slow preset)     |
| Shift + click    | JPG image sequence                 |
| Ctrl + click     | EXR image sequence                 |

**COP Flipsave** — select any Copernicus node (or a copnet), click. A temp
`rop_image` is created next to it, rendered over the playbar range at
1080x1080 (`cops_resolution` pref), then removed — no manual ROP setup.
JPG/MP4/GIF bake the OCIO display/view so output matches the COP viewer;
EXR stays linear.

| Click            | Output                                 |
|------------------|----------------------------------------|
| Click            | MP4 (h264 CRF 16, slow preset)         |
| Shift + click    | JPG image sequence                     |
| Ctrl + click     | EXR image sequence (linear)            |
| Alt + click      | GIF (palette-optimised, 540px @ 15fps) |

Every click also drops a dated copy of the current hip next to the render so
the two stay paired.

## File layout produced

```
$HIP/flipbook/YYYY_MMDD/<scene_stem>/<scene_stem>_YYYY_MMDD_<roman>.hiplc
$HIP/flipbook/YYYY_MMDD/<scene_stem>/<scene_stem>_YYYY_MMDD_<roman>.mp4
$HIP/flipbook/YYYY_MMDD/<scene_stem>/<scene_stem>_YYYY_MMDD_<roman>.$F4.jpg
$HIP/flipbook/YYYY_MMDD/<scene_stem>/<scene_stem>_YYYY_MMDD_<roman>.$F4.exr
```

Roman numerals (`i`, `ii`, `iii` ...) auto-increment within the same day.

## Install

1. Clone or place this repo wherever you like. The reference install lives at
   `/Volumes/Suite/LOS_LABS/KRIS/git/tooandflow`.
2. Copy `package.json` to your Houdini packages folder (one-time):
   ```
   mkdir -p ~/Library/Preferences/houdini/21.0/packages
   cp package.json ~/Library/Preferences/houdini/21.0/packages/tooandflow.json
   ```
   If your repo lives somewhere other than the default path, edit
   `TOOANDFLOW_ROOT` inside the copy.
3. Launch Houdini — a `tooandflow` shelf tab will appear with one button.

## Usage

- Save your scene at least once (an untitled scene will be politely refused).
- Click the shelf button. That's it.
- A "Reveal in Finder" dialog pops at the end so you can grab the output.

## Prefs

Stored at `$HOUDINI_USER_PREF_DIR/tooandflow_prefs.json`. Edit manually for
now (settings UI is a v2 thing).

| key                       | default      | notes                              |
|---------------------------|--------------|------------------------------------|
| `last_format`             | `"mp4"`      | tracked automatically              |
| `mp4_crf`                 | `16`         | lower = higher quality / bigger    |
| `mp4_preset`              | `"slow"`     | h264 encoder preset                |
| `keep_jpg_intermediate`   | `false`      | keep temp JPGs after MP4 encode    |
| `resolution_override`     | `null`       | null = match viewport; `[w, h]` forces (width wins) |
| `maximise_viewport`       | `false`      | maximise the pane first (reframes) |
| `notify_when_done`        | `true`       | show the Reveal dialog at the end  |
| `cops_resolution`         | `[1080, 1080]` | COP Flipsave render size; null = COP's own res |
| `gif_fps`                 | `15`         | GIF frame rate                     |
| `gif_scale`               | `0.5`        | GIF scale vs master (0.5 => 540px) |

## Resolution

Flipsave writes at the **viewport's own resolution** — MP4, JPG and EXR all
come out the same size as the pane you clicked on (3980x2026 on a maximised
pane on a Retina Mac). Nothing is scaled and nothing follows the camera's
`resx`/`resy`.

Two Houdini quirks worth knowing if you touch this code:

- `FlipbookSettings.useResolution(True)` honours only the **width** you give
  it — the height is always conformed to the viewport's aspect ratio. Ask for
  1024x1024 on a 1.96:1 viewport and you get 1024x522. `resolution_override`
  therefore means "this width, viewport aspect".
- `GeometryViewport.size()` returns `(x, y, width, height)` in UI *points*,
  while the flipbook renders in device pixels. Don't compute the resolution
  from it — `useResolution(False)` lets Houdini do it correctly.

COP Flipsave is separate: it renders at `cops_resolution` (1080x1080 square
master by default), not at a viewport size.

## Why not just OpenGL ROP?

The whole point is to keep the *viewport* — HUD, overlays, gnomon, frame
counter, headlight shading — exactly as it appears on screen. OpenGL ROP
strips all that. This package wraps `hou.SceneViewer.flipbook()` instead.

## v1 / not yet

Parking lot for later: Reveal-in-Finder shelf button, Slack post-render
notification, per-job output root override, dated-hip cleanup,
proper settings UI.
