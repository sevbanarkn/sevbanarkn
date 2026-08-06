"""Scrape the public contribution calendar and draw it as an animated heatmap.

Source: https://github.com/users/<user>/contributions - an unauthenticated
HTML fragment, so no token or API scope is needed. The trade-off is that this
parser breaks whenever GitHub reworks that markup, so every failure path falls
back to an empty grid rather than aborting the build.
"""

import datetime as dt
import re
import sys

from common import (ACCENT, DIM, FG, LEVELS, esc, load_config,
                    write_svg, window_chrome)

URL = "https://github.com/users/{user}/contributions"
HEADERS = {"User-Agent": "Mozilla/5.0 (profile-readme-builder)",
           "Accept": "text/html"}

CELL, GAP = 11, 3
PITCH = CELL + GAP
PAD_X, BAR_H = 20, 32
LABEL_W = 30                 # left gutter for Mon/Wed/Fri
MONTH_H = 18
WEEKS = 53

DAY_LABELS = {1: "Mon", 3: "Wed", 5: "Fri"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _sunday(date):
    """The Sunday that starts this date's calendar week."""
    return date - dt.timedelta(days=(date.weekday() + 1) % 7)


def _bucket(count):
    """Fallback level 0-4 for when GitHub stops emitting data-level."""
    for i, threshold in enumerate((0, 1, 4, 8)):
        if count <= threshold:
            return i
    return 4


def fetch(user):
    """Return (columns, total) where columns is a list of 7-slot week lists.

    Each slot is None (outside the range) or a (date, level, count) tuple.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:
        print(f"  missing dependency: {exc}", file=sys.stderr)
        return [], None

    try:
        resp = requests.get(URL.format(user=user), headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as exc:                          # noqa: BLE001 - network
        print(f"  fetch failed: {exc}", file=sys.stderr)
        return [], None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Counts live in <tool-tip for="<td id>">N contributions on ...</tool-tip>.
    counts = {}
    for tip in soup.find_all("tool-tip"):
        target = tip.get("for")
        if not target:
            continue
        match = re.match(r"\s*([\d,]+)\s+contribution", tip.get_text(" ", strip=True))
        counts[target] = int(match.group(1).replace(",", "")) if match else 0

    days = []
    for td in soup.find_all("td"):
        raw = td.get("data-date")
        if not raw:
            continue
        try:
            date = dt.date.fromisoformat(raw)
        except ValueError:
            continue
        count = counts.get(td.get("id"), 0)
        level = td.get("data-level")
        # data-level has come and gone across GitHub redesigns; derive it from
        # the tooltip count when the attribute is missing.
        level = int(level) if level is not None else _bucket(count)
        days.append((date, level, count))

    # Place cells by date rather than by DOM position: the first and last weeks
    # of the range are partial, so weekday rows are ragged and index-based
    # alignment would shift whole columns.
    grid = [[None] * WEEKS for _ in range(7)]
    seen = 0
    if days:
        last_sunday = _sunday(max(d[0] for d in days))
        for date, level, count in days:
            row = (date.weekday() + 1) % 7            # Mon=0..Sun=6 -> Sun=0
            col = WEEKS - 1 - (last_sunday - _sunday(date)).days // 7
            if 0 <= col < WEEKS:
                grid[row][col] = (date, level, count)
                seen += 1

    if not seen:
        print("  no contribution cells parsed - GitHub markup may have changed",
              file=sys.stderr)
        return [], None

    columns = [[grid[r][c] for r in range(7)] for c in range(WEEKS)]
    total = sum(cell[2] for col in columns for cell in col if cell)
    print(f"  parsed {seen} days, {total} contributions")
    return columns, total


def month_ticks(columns):
    """Column index -> month label, emitted only where the month rolls over."""
    ticks, previous = [], None
    for i, col in enumerate(columns[:-2]):            # last 2 would clip the edge
        first = next((c for c in col if c), None)
        if not first:
            continue
        month = first[0].month
        if month != previous:
            ticks.append((i, MONTHS[month - 1]))
        previous = month
    return ticks


def build():
    cfg = load_config()
    user = cfg["username"]
    columns, total = fetch(user)
    if not columns:
        columns = [[None] * 7 for _ in range(WEEKS)]

    grid_x = PAD_X + LABEL_W
    grid_y = BAR_H + 34 + MONTH_H
    width = grid_x + WEEKS * PITCH - GAP + PAD_X
    height = grid_y + 7 * PITCH - GAP + 46

    body = [window_chrome(width, height, f"{user} -- contributions", BAR_H)]

    headline = (f"{total:,} contributions in the last year"
                if total is not None else "contribution activity")
    body.append(f'  <text x="{grid_x}" y="{BAR_H + 26}" fill="{FG}" '
                f'font-size="13" font-weight="bold">{esc(headline)}</text>')

    for col, label in month_ticks(columns):
        body.append(f'  <text x="{grid_x + col * PITCH}" y="{grid_y - 6}" '
                    f'fill="{DIM}" font-size="10">{label}</text>')

    for row, label in DAY_LABELS.items():
        body.append(f'  <text x="{PAD_X}" y="{grid_y + row * PITCH + CELL - 1}" '
                    f'fill="{DIM}" font-size="10">{label}</text>')

    # Wave: delay grows with the column so the year fills in left to right.
    for col, week in enumerate(columns):
        for row, cell in enumerate(week):
            if cell is None:
                continue
            date, level, count = cell
            delay = col * 0.022 + row * 0.012
            plural = "" if count == 1 else "s"
            body.append(
                f'  <rect class="d" x="{grid_x + col * PITCH}" '
                f'y="{grid_y + row * PITCH}" width="{CELL}" height="{CELL}" '
                f'rx="2" fill="{LEVELS[min(level, 4)]}" '
                f'style="animation-delay:{delay:.2f}s">'
                f'<title>{count} contribution{plural} on {date.isoformat()}</title>'
                f'</rect>'
            )

    # Legend.
    lg_y = grid_y + 7 * PITCH + 12
    lg_x = width - PAD_X - (len(LEVELS) * PITCH + 78)
    body.append(f'  <text x="{lg_x}" y="{lg_y + CELL - 1}" fill="{DIM}" '
                f'font-size="10">Less</text>')
    for i, colour in enumerate(LEVELS):
        body.append(f'  <rect x="{lg_x + 32 + i * PITCH}" y="{lg_y}" '
                    f'width="{CELL}" height="{CELL}" rx="2" fill="{colour}"/>')
    body.append(f'  <text x="{lg_x + 36 + len(LEVELS) * PITCH}" '
                f'y="{lg_y + CELL - 1}" fill="{DIM}" font-size="10">More</text>')

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body.append(f'  <text x="{PAD_X}" y="{lg_y + CELL - 1}" fill="{ACCENT}" '
                f'font-size="10" opacity="0.7">updated {stamp}</text>')

    style = (
        "@keyframes pop{from{opacity:0;transform:scale(.3)}"
        "to{opacity:1;transform:scale(1)}}"
        ".d{opacity:0;transform-box:fill-box;transform-origin:center;"
        "animation:pop .4s cubic-bezier(.2,.9,.3,1.4) both}"
        "@media (prefers-reduced-motion:reduce){.d{animation:none;opacity:1}}"
    )
    write_svg("contributions.svg", "\n".join(body), width, height, style)


if __name__ == "__main__":
    build()
