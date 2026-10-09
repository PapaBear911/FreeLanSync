#!/usr/bin/env python3
"""Generate FreeLanSync launcher icons (legacy mipmap PNGs + preview).

The adaptive-icon vector layers (drawable/ic_launcher_{background,foreground}.xml)
are the canonical source for API 26+; this script renders the matching legacy
PNG fallbacks for mipmap-{mdpi..xxxhdpi} (used by pre-26 renderers, the package
installer dialog, and OEM launchers that prefer bitmaps).

Geometry lives in a 108x108 viewport (adaptive icon canvas) and is scaled to
each density. Keep it in sync with drawable/ic_launcher_foreground.xml:
  - sync ring: center (54,54), band radius 20.5..27.5, arcs 20..150 and 200..330
  - arrowheads at 150 / 330 degrees, white diamond + cyan core in the middle.

Usage: python android/tools/generate_launcher_icons.py
"""
import math
import os

from PIL import Image, ImageDraw

# Design constants (108x108 viewport space)
CENTER = 54.0
BAND_INNER = 20.5
BAND_OUTER = 27.5
ARCS = [(20.0, 150.0), (200.0, 330.0)]
C1 = (0x31, 0x2E, 0x81)  # indigo-900 (gradient start)
C2 = (0x0F, 0x17, 0x2A)  # slate-900 (gradient end)
CYAN = (0x38, 0xBD, 0xF8)
WHITE = (0xFF, 0xFF, 0xFF)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RES_DIR = os.path.join(REPO_ROOT, "android", "app", "src", "main", "res")

DENSITIES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}


def point(angle_deg: float, radius: float) -> tuple:
    """Screen-space point (y down); angle increases clockwise from 3 o'clock."""
    a = math.radians(angle_deg)
    return (CENTER + radius * math.cos(a), CENTER + radius * math.sin(a))


def arrowhead_polygon(end_angle: float) -> list:
    """Triangle just past the arc end, wider than the ring band."""
    tip = point(end_angle + 12.0, 24.0)
    base_a = point(end_angle - 2.0, BAND_INNER - 3.5)
    base_b = point(end_angle - 2.0, BAND_OUTER + 3.5)
    return [tip, base_a, base_b]


def build_gradient(size: int) -> Image.Image:
    """Diagonal indigo->slate gradient, built small then upscaled."""
    steps = 256
    grad = Image.new("RGB", (steps, steps))
    px = grad.load()
    for y in range(steps):
        for x in range(steps):
            t = (x + y) / (2.0 * (steps - 1))
            px[x, y] = tuple(int(C1[i] + (C2[i] - C1[i]) * t) for i in range(3))
    return grad.resize((size, size), Image.BILINEAR)


def render_icon(size: int, round_mask: bool, supersample: int = 4) -> Image.Image:
    big = size * supersample
    scale = big / 108.0

    img = build_gradient(big).convert("RGBA")

    # Glyph layer: ring band (outer wedge minus inner wedge), then arrows, then diamond.
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    def bbox(radius: float):
        r = radius * scale
        c = CENTER * scale
        return [c - r, c - r, c + r, c + r]

    for start, end in ARCS:
        draw.pieslice(bbox(BAND_OUTER), start=start, end=end, fill=CYAN + (255,))
        # Erase the inner wedge (ImageDraw on RGBA writes pixels raw by default).
        draw.pieslice(bbox(BAND_INNER), start=start, end=end, fill=(0, 0, 0, 0))

    for _, end in ARCS:
        poly = [(x * scale, y * scale) for x, y in arrowhead_polygon(end)]
        draw.polygon(poly, fill=CYAN + (255,))

    # Diamond: white outer + cyan core (echoes the desktop tray "diamond core").
    for radius, color in ((14.0, WHITE), (6.5, CYAN)):
        diamond = [
            (CENTER * scale, (CENTER - radius) * scale),
            ((CENTER + radius) * scale, CENTER * scale),
            (CENTER * scale, (CENTER + radius) * scale),
            ((CENTER - radius) * scale, CENTER * scale),
        ]
        draw.polygon(diamond, fill=color + (255,))

    img = Image.alpha_composite(img, layer)

    if round_mask:
        mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, big - 1, big - 1], fill=255)
        img.putalpha(mask)

    return img.resize((size, size), Image.LANCZOS)


def main():
    for dpi, size in DENSITIES.items():
        out_dir = os.path.join(RES_DIR, f"mipmap-{dpi}")
        os.makedirs(out_dir, exist_ok=True)
        for round_mask, name in ((False, "ic_launcher.png"), (True, "ic_launcher_round.png")):
            icon = render_icon(size, round_mask)
            path = os.path.join(out_dir, name)
            icon.save(path, "PNG", optimize=True)
            print(f"wrote {path} ({size}x{size})")

    # Side-by-side preview (not part of res/) for visual verification.
    preview = Image.new("RGBA", (1100, 560), (17, 17, 24, 255))
    square = render_icon(512, round_mask=False)
    round_ = render_icon(512, round_mask=True)
    preview.paste(square, (20, 24), square)
    preview.paste(round_, (568, 24), round_)
    preview_path = os.path.join(os.path.dirname(__file__), "icon_preview.png")
    preview.save(preview_path, "PNG")
    print(f"wrote {preview_path}")


if __name__ == "__main__":
    main()
