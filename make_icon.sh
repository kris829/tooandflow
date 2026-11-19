#!/usr/bin/env bash
#
# make_icon.sh — rasterize config/Icons/tooandflow_flipsave.svg to PNGs.
#
# Edit the SVG (VS Code / Zed with a live preview, or any editor), then run
# this to regenerate the shelf icon. Uses Houdini's bundled hython + PySide6,
# so there's nothing to pip-install. No anti-aliasing => crisp pixel art.
#
# Usage:
#   ./make_icon.sh                 # auto-detect newest Houdini, render SVG
#   ./make_icon.sh path/to.svg     # render a different SVG
#   HYTHON=/path/to/hython ./make_icon.sh   # force a specific hython
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SVG="${1:-$REPO/config/Icons/tooandflow_flipsave.svg}"

if [[ ! -f "$SVG" ]]; then
  echo "error: SVG not found: $SVG" >&2
  exit 1
fi

# --- locate hython -----------------------------------------------------------
# Priority: $HYTHON env override, then newest Houdini under /Applications.
find_hython() {
  if [[ -n "${HYTHON:-}" ]]; then
    echo "$HYTHON"; return
  fi
  local rel="Frameworks/Houdini.framework/Versions/Current/Resources/bin/hython"
  # sort -V puts the highest version last; pick that one.
  local newest
  newest="$(ls -d /Applications/Houdini/Houdini*.* 2>/dev/null | sort -V | tail -1 || true)"
  if [[ -n "$newest" && -x "$newest/$rel" ]]; then
    echo "$newest/$rel"; return
  fi
  # Linux / fallback: hython on PATH.
  command -v hython 2>/dev/null || true
}

HY="$(find_hython)"
if [[ -z "$HY" || ! -x "$HY" ]]; then
  echo "error: could not find hython. Set HYTHON=/path/to/hython and retry." >&2
  exit 1
fi
echo "hython: $HY"
echo "svg:    $SVG"

# --- render (stderr discarded to hide Redshift/plugin chatter) --------------
"$HY" - "$SVG" 2>/dev/null <<'PY'
import sys, os
svg = sys.argv[1]
from PySide6.QtWidgets import QApplication
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import Qt

app = QApplication([])
r = QSvgRenderer(svg)
if not r.isValid():
    sys.stderr.write("INVALID SVG\n"); sys.exit(2)

base, _ = os.path.splitext(svg)        # .../tooandflow_flipsave

def render(px, suffix=""):
    out = f"{base}{suffix}.png"
    img = QImage(px, px, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, False)          # keep pixels hard
    p.setRenderHint(QPainter.SmoothPixmapTransform, False)
    r.render(p)
    p.end()
    if not img.save(out, "PNG"):
        sys.stderr.write(f"FAILED to write {out}\n"); sys.exit(3)
    print(f"  wrote {out}  ({px}x{px}, {os.path.getsize(out)} bytes)")

render(256)              # primary — Houdini picks this up by basename
render(128, "_128")
render(32,  "_32")
print("done")
PY

echo "Reload the shelf in Houdini (or restart) to see the updated icon."
