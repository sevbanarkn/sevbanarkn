"""Turn assets/avatar.jpg into an animated ASCII-art SVG.

Pipeline: background removal (optional) -> CLAHE contrast (optional) ->
downscale to a character grid -> map luminance onto a density ramp.
Rows fade in one after another via CSS keyframes baked into the SVG.

Pillow is required. rembg and OpenCV are optional; the script degrades to a
plain autocontrast pass when they are unavailable.
"""

import os

from common import ROOT, esc, load_config, write_svg, window_chrome

# Darkest to brightest. A space carries no ink, '@' carries the most.
RAMP = " .:-=+*#%@"

# Phosphor-green shades, dim to bright, indexed by luminance bucket.
SHADES = ["#2d4f3c", "#3fb950", "#56d364", "#aff5b4"]

FONT_SIZE = 11
CHAR_W = FONT_SIZE * 0.6          # monospace advance width
LINE_H = FONT_SIZE * 1.0          # tight leading keeps cells near-square
PAD_X, BAR_H, PAD_TOP, PAD_BOT = 18, 32, 14, 16

PLACEHOLDER_TEXT = [
    "",
    "no avatar image found",
    "",
    "drop a portrait at",
    "  assets/avatar.jpg",
    "and push -- the workflow",
    "regenerates this panel",
    "",
]
PLACEHOLDER_W = 40          # inner width, padded so every row aligns


def _load_pixels(path, cols, invert, remove_background):
    """Return (grid, rows, cols) of 0-255 luminance values."""
    from PIL import Image, ImageOps      # imported late so a missing Pillow
                                         # only costs the avatar, not the build
    img = Image.open(path).convert("RGBA")

    if remove_background:
        try:
            from rembg import remove
            img = remove(img)
            print("  background removed (rembg)")
        except Exception as exc:                      # noqa: BLE001 - optional dep
            print(f"  rembg unavailable, keeping background ({exc.__class__.__name__})")

    # Flatten transparency onto black so cut-out edges read as empty space.
    flat = Image.new("RGBA", img.size, (0, 0, 0, 255))
    flat.alpha_composite(img)
    gray = flat.convert("L")

    try:
        import cv2
        import numpy as np
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        gray = Image.fromarray(clahe.apply(np.array(gray)))
        print("  contrast enhanced (OpenCV CLAHE)")
    except Exception as exc:                          # noqa: BLE001 - optional dep
        gray = ImageOps.autocontrast(gray, cutoff=2)
        print(f"  CLAHE unavailable, used autocontrast ({exc.__class__.__name__})")

    rows = max(1, round(cols * (gray.height / gray.width) * (CHAR_W / LINE_H)))
    gray = gray.resize((cols, rows), Image.LANCZOS)
    if invert:
        gray = ImageOps.invert(gray)

    data = list(gray.getdata())
    grid = [data[r * cols:(r + 1) * cols] for r in range(rows)]
    return grid, rows, cols


def _rows_from_image(path, cols, invert, remove_background):
    """Render the image as a list of (char, shade_index) rows."""
    grid, rows, cols = _load_pixels(path, cols, invert, remove_background)
    out = []
    for r in range(rows):
        line = []
        for value in grid[r]:
            char = RAMP[min(len(RAMP) - 1, value * len(RAMP) // 256)]
            shade = min(len(SHADES) - 1, value * len(SHADES) // 256)
            line.append((char, shade))
        out.append(line)
    return out


def _rows_from_placeholder():
    """A framed notice, every row padded to the same width so the box closes."""
    edge = "+" + "-" * PLACEHOLDER_W + "+"
    lines = [edge]
    for text in PLACEHOLDER_TEXT:
        pad = (PLACEHOLDER_W - len(text)) // 2
        body = (" " * pad + text).ljust(PLACEHOLDER_W)
        lines.append(f"|{body}|")
    lines.append(edge)
    return [[(ch, 2 if ch not in "+-|" else 0) for ch in line] for line in lines]


def _render_row(chars, y, delay):
    """One <text> per row, with same-shade neighbours merged into tspans.

    textLength pins every run to an exact pixel span, so the grid stays
    aligned no matter which monospace font the viewer's browser picks.
    """
    spans, start = [], 0
    while start < len(chars):
        shade = chars[start][1]
        end = start
        while end < len(chars) and chars[end][1] == shade:
            end += 1
        run = "".join(c for c, _ in chars[start:end])
        if run.strip():                               # skip pure whitespace runs
            spans.append(
                f'<tspan x="{PAD_X + start * CHAR_W:.1f}" '
                f'textLength="{(end - start) * CHAR_W:.1f}" '
                f'lengthAdjust="spacingAndGlyphs" fill="{SHADES[shade]}"'
                f'>{esc(run)}</tspan>'
            )
        start = end
    if not spans:
        return ""
    return (f'  <text class="r" y="{y:.1f}" font-size="{FONT_SIZE}" '
            f'xml:space="preserve" style="animation-delay:{delay:.2f}s">'
            + "".join(spans) + "</text>")


def build():
    cfg = load_config()
    opts = cfg.get("ascii", {})
    cols = int(opts.get("cols", 46))
    path = os.path.join(ROOT, cfg.get("avatar", "assets/avatar.jpg"))

    if os.path.exists(path):
        rows = _rows_from_image(path, cols,
                                bool(opts.get("invert", False)),
                                bool(opts.get("remove_background", True)))
        title = "avatar.jpg -> ascii"
    else:
        print(f"  {os.path.relpath(path, ROOT)} not found, using placeholder")
        rows = _rows_from_placeholder()
        cols = max(len(r) for r in rows)
        title = "avatar -- not configured"

    width = round(PAD_X * 2 + cols * CHAR_W)
    height = round(BAR_H + PAD_TOP + len(rows) * LINE_H + PAD_BOT)

    body = [window_chrome(width, height, title, BAR_H)]
    for i, chars in enumerate(rows):
        y = BAR_H + PAD_TOP + (i + 1) * LINE_H
        line = _render_row(chars, y, i * 0.045)
        if line:
            body.append(line)

    style = (
        "@keyframes fi{from{opacity:0;transform:translateX(-6px)}"
        "to{opacity:1;transform:translateX(0)}}"
        ".r{opacity:0;animation:fi .5s ease-out both}"
        "@media (prefers-reduced-motion:reduce){.r{animation:none;opacity:1}}"
    )
    write_svg("avatar.svg", "\n".join(body), width, height, style)


if __name__ == "__main__":
    build()
