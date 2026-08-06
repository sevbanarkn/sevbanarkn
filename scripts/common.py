"""Shared helpers for the profile SVG generators.

Every SVG produced here must be fully self-contained: GitHub renders README
images through an <img> tag, which blocks scripts and external resources but
still honours CSS keyframes and SMIL declared inside the file itself.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Terminal chrome. Deliberately dark in both GitHub themes: an <img>-embedded
# SVG follows the OS colour scheme, not the one picked in GitHub's settings,
# so a theme-reactive palette would desync from the page around it.
BG = "#0d1117"
BG_BAR = "#161b22"
BORDER = "#30363d"
FG = "#c9d1d9"
DIM = "#8b949e"
ACCENT = "#58a6ff"
GREEN = "#3fb950"
YELLOW = "#d29922"
MAGENTA = "#bc8cff"

# Single quotes on purpose: this string is interpolated into a double-quoted
# XML attribute, so double quotes here would terminate the attribute early and
# make the whole SVG unparseable. CSS accepts either quote style.
MONO = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'DejaVu Sans Mono', 'Liberation Mono', monospace")

# GitHub's contribution heatmap levels 0-4.
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]


def load_config():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as fh:
        return json.load(fh)


def esc(text):
    """Escape a string for use as SVG text content."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def window_chrome(width, height, title, bar_h=32):
    """The macOS-style title bar every card sits inside."""
    return f"""  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8"
        fill="{BG}" stroke="{BORDER}"/>
  <path d="M0.5 8.5a8 8 0 0 1 8-8h{width - 17}a8 8 0 0 1 8 8v{bar_h - 8}H0.5z"
        fill="{BG_BAR}" stroke="{BORDER}"/>
  <circle cx="18" cy="{bar_h / 2}" r="5.5" fill="#ff5f56"/>
  <circle cx="38" cy="{bar_h / 2}" r="5.5" fill="#ffbd2e"/>
  <circle cx="58" cy="{bar_h / 2}" r="5.5" fill="#27c93f"/>
  <text x="{width / 2}" y="{bar_h / 2 + 4}" fill="{DIM}" font-family="{MONO}"
        font-size="12" text-anchor="middle">{esc(title)}</text>"""


def write_svg(name, body, width, height, style=""):
    """Serialise one self-contained SVG into svg/<name>."""
    out = os.path.join(ROOT, "svg", name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    doc = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="{MONO}" role="img">\n'
        f"  <style>{style}</style>\n"
        f"{body}\n"
        "</svg>\n"
    )
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(doc)
    print(f"  wrote svg/{name}  ({width}x{height}, {len(doc)} bytes)")
    return out
