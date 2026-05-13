# tooandflow

One-click flipbook + dated-hip-save for SideFX Houdini.

A tiny personal replacement for ODTOOLS' flipbook function. One shelf
button — modifier keys pick the output format.

| Click            | Output                             |
|------------------|------------------------------------|
| Click            | MP4 (h264 CRF 16, slow preset)     |
| Shift + click    | JPG image sequence                 |
| Ctrl + click     | EXR image sequence                 |

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
| `resolution_override`     | `null`       | `[w, h]` to force, null = auto     |
| `notify_when_done`        | `true`       | show the Reveal dialog at the end  |

## Why not just OpenGL ROP?

The whole point is to keep the *viewport* — HUD, overlays, gnomon, frame
counter, headlight shading — exactly as it appears on screen. OpenGL ROP
strips all that. This package wraps `hou.SceneViewer.flipbook()` instead.

## v1 / not yet

Parking lot for later: Reveal-in-Finder shelf button, Slack post-render
notification, per-job output root override, dated-hip cleanup,
proper settings UI.
