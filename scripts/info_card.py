"""Render the neofetch-style info card from config.json -> svg/card.svg.

Each line fades in on its own delay, then a blinking block cursor parks at
the bottom. Content lives in config.json so editing the card never means
touching this file.
"""

from common import (ACCENT, DIM, FG, GREEN, MAGENTA, YELLOW,
                    esc, load_config, write_svg, window_chrome)

FONT_SIZE = 13
CHAR_W = FONT_SIZE * 0.6
LINE_H = 22
PAD_X, BAR_H, PAD_TOP, PAD_BOT = 20, 32, 18, 20

SWATCHES = ["#ff5f56", "#d29922", "#3fb950", "#58a6ff",
            "#bc8cff", "#39c5cf", "#c9d1d9", "#8b949e"]

STEP = 0.12          # seconds between consecutive lines


def _text(x, y, content, fill, delay, size=FONT_SIZE, weight="normal"):
    return (f'  <text class="l" x="{x:.1f}" y="{y:.1f}" fill="{fill}" '
            f'font-size="{size}" font-weight="{weight}" xml:space="preserve" '
            f'style="animation-delay:{delay:.2f}s">{esc(content)}</text>')


def build():
    cfg = load_config()
    card = cfg.get("card", {})
    title = card.get("title", f"{cfg['username']}@github")
    rows = [(str(k), str(v)) for k, v in card.get("rows", [])]

    key_w = max((len(k) for k, _ in rows), default=4)
    prompt = f"$ neofetch --profile {cfg['username']}"

    # Longest rendered line decides the card width.
    longest = max([len(prompt), len(title) + 4]
                  + [key_w + 2 + len(v) for _, v in rows])
    width = round(PAD_X * 2 + longest * CHAR_W) + 24

    # prompt, blank, title, rule, rows, blank, swatch strip
    n_lines = 4 + len(rows) + 2
    height = round(BAR_H + PAD_TOP + n_lines * LINE_H + PAD_BOT)

    body = [window_chrome(width, height, "neofetch", BAR_H)]
    y = BAR_H + PAD_TOP + LINE_H
    step = 0

    body.append(_text(PAD_X, y, prompt, GREEN, step * STEP))
    y += LINE_H * 2
    step += 1

    body.append(_text(PAD_X, y, title, ACCENT, step * STEP, weight="bold"))
    y += LINE_H
    step += 1

    body.append(_text(PAD_X, y, "-" * len(title), DIM, step * STEP))
    y += LINE_H
    step += 1

    for key, value in rows:
        label = f"{key}:".ljust(key_w + 2)
        body.append(
            f'  <text class="l" x="{PAD_X:.1f}" y="{y:.1f}" '
            f'font-size="{FONT_SIZE}" xml:space="preserve" '
            f'style="animation-delay:{step * STEP:.2f}s">'
            f'<tspan fill="{YELLOW}" font-weight="bold">{esc(label)}</tspan>'
            f'<tspan fill="{FG}">{esc(value)}</tspan></text>'
        )
        y += LINE_H
        step += 1

    y += LINE_H // 2
    sw_delay = step * STEP
    for i, colour in enumerate(SWATCHES):
        body.append(
            f'  <rect class="l" x="{PAD_X + i * 22:.1f}" y="{y - 12:.1f}" '
            f'width="18" height="14" rx="2" fill="{colour}" '
            f'style="animation-delay:{sw_delay + i * 0.05:.2f}s"/>'
        )

    # Blinking cursor, held back until every line has landed.
    cur_x = PAD_X + len(SWATCHES) * 22 + 8
    body.append(
        f'  <rect class="cur" x="{cur_x:.1f}" y="{y - 12:.1f}" '
        f'width="9" height="14" fill="{MAGENTA}" '
        f'style="animation-delay:{sw_delay + 0.6:.2f}s"/>'
    )

    style = (
        "@keyframes fi{from{opacity:0;transform:translateY(4px)}"
        "to{opacity:1;transform:translateY(0)}}"
        "@keyframes bl{0%,49%{opacity:1}50%,100%{opacity:0}}"
        ".l{opacity:0;animation:fi .45s ease-out both}"
        ".cur{opacity:0;animation:bl 1.1s steps(1) infinite both}"
        "@media (prefers-reduced-motion:reduce){"
        ".l{animation:none;opacity:1}.cur{animation:none;opacity:1}}"
    )
    write_svg("card.svg", "\n".join(body), width, height, style)


if __name__ == "__main__":
    build()
