#!/usr/bin/env python3
"""Emit adaptive-icon vector layers + a verification SVG from shared geometry.

FreeLanSync Mobius HyperLink: Horizontal Continuous-Curvature 3D Sync Knot.
Writes:
  android/app/src/main/res/drawable/ic_launcher_background.xml  (vector, gradient)
  android/app/src/main/res/drawable/ic_launcher_foreground.xml  (vector, glyph)
  android/tools/ic_launcher_foreground_preview.svg              (render check)
"""
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RES_DIR = os.path.join(REPO_ROOT, "android", "app", "src", "main", "res")

# Geometric paths for 108x108 viewport
INDIGO_UNDERPASS_1 = "M 64,64 A 14.142,14.142 0 1,0 64,44 L 58.5,49.5"
INDIGO_UNDERPASS_2 = "M 49.5,58.5 L 44,64"
CYAN_OVERPASS = "M 44,64 A 14.142,14.142 0 1,1 44,44 L 64,64"

FOREGROUND_XML = f"""<?xml version="1.0" encoding="utf-8"?>
<!-- FreeLanSync adaptive-icon foreground (API 26+).
     FreeLanSync Mobius HyperLink: Horizontal Continuous-Curvature 3D Sync Knot.
     Single source of truth with desktop dashboard brand mark. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">

    <!-- Under-pass: Indigo Strand (Desktop Vault Node) -->
    <path
        android:strokeColor="#6366F1"
        android:strokeWidth="8"
        android:strokeLineCap="round"
        android:strokeLineJoin="round"
        android:pathData="{INDIGO_UNDERPASS_1}" />
    <path
        android:strokeColor="#6366F1"
        android:strokeWidth="8"
        android:strokeLineCap="round"
        android:strokeLineJoin="round"
        android:pathData="{INDIGO_UNDERPASS_2}" />

    <!-- Over-pass: Electric Cyan Strand (Mobile Link Node) -->
    <path
        android:strokeColor="#38BDF8"
        android:strokeWidth="8"
        android:strokeLineCap="round"
        android:strokeLineJoin="round"
        android:pathData="{CYAN_OVERPASS}" />
</vector>
"""

BACKGROUND_XML = """<?xml version="1.0" encoding="utf-8"?>
<!-- FreeLanSync adaptive-icon background: 2026 dark tech slate-900 -> slate-950 diagonal gradient. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:aapt="http://schemas.android.com/aapt"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path android:pathData="M0,0 H108 V108 H0 Z">
        <aapt:attr name="android:fillColor">
            <gradient
                android:type="linear"
                android:startX="0"
                android:startY="0"
                android:endX="108"
                android:endY="108"
                android:startColor="#FF0F172A"
                android:endColor="#FF020617" />
        </aapt:attr>
    </path>
</vector>
"""

def foreground_svg() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1080" viewBox="0 0 108 108">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="108" y2="108" gradientUnits="userSpaceOnUse">
      <stop stop-color="#0F172A"/>
      <stop offset="1" stop-color="#020617"/>
    </linearGradient>
  </defs>
  <rect width="108" height="108" fill="url(#bg)"/>
  <!-- Under-pass: Indigo Strand (Desktop Vault Node) -->
  <path d="{INDIGO_UNDERPASS_1}" fill="none" stroke="#818CF8" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{INDIGO_UNDERPASS_2}" fill="none" stroke="#818CF8" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
  <!-- Over-pass: Electric Cyan Strand (Mobile Link Node) -->
  <path d="{CYAN_OVERPASS}" fill="none" stroke="#38BDF8" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

def main():
    fg_path = os.path.join(RES_DIR, "drawable", "ic_launcher_foreground.xml")
    bg_path = os.path.join(RES_DIR, "drawable", "ic_launcher_background.xml")
    os.makedirs(os.path.dirname(fg_path), exist_ok=True)
    with open(fg_path, "w", encoding="utf-8") as f:
        f.write(FOREGROUND_XML)
    with open(bg_path, "w", encoding="utf-8") as f:
        f.write(BACKGROUND_XML)
    print(f"wrote {fg_path}")
    print(f"wrote {bg_path}")

    svg_path = os.path.join(os.path.dirname(__file__), "ic_launcher_foreground_preview.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(foreground_svg())
    print(f"wrote {svg_path}")

if __name__ == "__main__":
    main()
