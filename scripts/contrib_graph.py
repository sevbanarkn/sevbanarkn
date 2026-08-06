"""Scrape the public contribution calendar and draw it as an animated heatmap.

Source: https://github.com/users/<user>/contributions - an unauthenticated
HTML fragment, so no token or API scope is needed. The trade-off is that this
parser breaks whenever GitHub reworks that markup, so every failure path falls
back to an empty grid rather than aborting the build.
"""

import datetime as dt
import random
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

SNAKE_STEP = 0.11            # default seconds the head spends crossing one
                             # cell; override with "snake_speed" in config.json
SNAKE_COLOURS = ["#bc8cff", "#a371f7", "#8957e5", "#6e40c9", "#553098"]

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


def snake_order():
    """Boustrophedon walk over every grid slot: down column 0, up column 1, ...

    Consecutive centres are always exactly PITCH apart -- including the step
    across a column boundary -- so a linear CSS timing function gives the
    snake a constant speed with no easing tricks.
    """
    order = []
    for col in range(WEEKS):
        rows = range(7) if col % 2 == 0 else range(6, -1, -1)
        order.extend((col, row) for row in rows)
    return order


def _neighbours(cell):
    col, row = cell
    for dcol, drow in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ncol, nrow = col + dcol, row + drow
        if 0 <= ncol < WEEKS and 0 <= nrow < 7:
            yield ncol, nrow


def wander_order(seed):
    """A random Hamiltonian path over the grid, or None if the search stalls.

    A plain random walk is not usable here: it revisits cells, leaves most of
    the year uneaten, and its steps would still have to be unit length. So the
    route is built as a self-avoiding walk that covers every slot exactly once
    -- it looks aimless but eats the whole grid, and every step stays one cell
    long, which is what keeps the CSS timing linear.

    Warnsdorff's rule (always head for the most enclosed neighbour) makes dead
    ends rare; the explicit stack unwinds the few that still happen.
    """
    rng = random.Random(seed)
    total = WEEKS * 7

    def ranked(cell, visited):
        options = [n for n in _neighbours(cell) if n not in visited]
        rng.shuffle(options)                          # random tie-break
        options.sort(key=lambda n: sum(1 for m in _neighbours(n)
                                       if m not in visited))
        return options

    # (0, 0) is on the majority colour of the board's checkerboard split, which
    # is a precondition for a Hamiltonian path to exist on an odd-sized grid.
    start = (0, 0)
    path, visited = [start], {start}
    stack = [ranked(start, visited)]
    budget = 500_000

    while len(path) < total:
        budget -= 1
        if budget <= 0 or not path:
            return None
        options = stack[-1]
        if not options:
            visited.discard(path.pop())               # dead end, step back
            stack.pop()
            continue
        nxt = options.pop(0)
        path.append(nxt)
        visited.add(nxt)
        stack.append(ranked(nxt, visited))

    return path


def snake_layer(grid_x, grid_y, step, order):
    """Return (body_elements, css, eat_delays) for the snake and its meal."""
    steps = len(order) - 1
    dur = round(steps * step, 2)

    def centre(col, row):
        return (grid_x + col * PITCH + CELL / 2, grid_y + row * PITCH + CELL / 2)

    # One shared keyframes rule drives every segment; the body is just the
    # same ride offset in time, which is what makes it trail the head.
    frames = []
    for i, (col, row) in enumerate(order):
        x, y = centre(col, row)
        frames.append(f"{i / steps * 100:.4f}%{{transform:translate({x:.0f}px,{y:.0f}px)}}")

    elements = []
    for k, colour in enumerate(SNAKE_COLOURS):
        size = CELL + 1 - k
        elements.append(
            f'  <rect class="sn" x="{-size / 2:.1f}" y="{-size / 2:.1f}" '
            f'width="{size}" height="{size}" rx="{3 - k * 0.4:.1f}" fill="{colour}" '
            f'style="animation-delay:{k * step:.3f}s"/>'
        )
    elements.reverse()          # tail first so the head paints on top

    # Each cell disappears as the head reaches it and regrows shortly before
    # the head comes back round, so the loop never visibly restarts.
    delays = {}
    for i, (col, row) in enumerate(order):
        delays[(col, row)] = i * step

    # The route cannot close into a cycle -- 371 cells split 186/185 across the
    # board's two colours, so no Hamiltonian cycle exists -- and the head would
    # otherwise teleport from the last cell back to the first. Fading out at the
    # end and in at the start reads as the snake leaving and re-entering.
    css = (
        "@keyframes ride{" + "".join(frames) + "}"
        "@keyframes glide{0%{opacity:0}3%{opacity:1}95%{opacity:1}100%{opacity:0}}"
        "@keyframes eaten{0%{opacity:1}1%{opacity:0}"
        "86%{opacity:0}96%{opacity:1}100%{opacity:1}}"
        f".sn{{animation:ride {dur}s linear infinite both,"
        f"glide {dur}s linear infinite both}}"
        f".e{{animation:eaten {dur}s linear infinite both}}"
        "@media (prefers-reduced-motion:reduce){"
        ".sn{display:none}.e{animation:none;opacity:1}}"
    )
    return elements, css, delays


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

    snake = bool(cfg.get("snake", True))
    if snake:
        step = max(0.02, float(cfg.get("snake_speed", SNAKE_STEP)))
        order, route = None, cfg.get("snake_path", "wander")
        if route == "wander":
            # Seeded by the date so a run is reproducible but the snake picks
            # a fresh route each day.
            seed = cfg.get("snake_seed") or dt.date.today().toordinal()
            order = wander_order(seed)
            if order is None:
                print("  wander search stalled, falling back to serpentine",
                      file=sys.stderr)
        if order is None:
            order, route = snake_order(), "serpentine"
        segments, snake_css, eat_delays = snake_layer(grid_x, grid_y, step, order)
        print(f"  snake: {route}, {step}s per cell, "
              f"{round((len(order) - 1) * step, 1)}s loop")

    # Empty slots first: eaten cells fade to reveal this layer underneath.
    for col, week in enumerate(columns):
        for row, cell in enumerate(week):
            if cell is None:
                continue
            body.append(f'  <rect x="{grid_x + col * PITCH}" '
                        f'y="{grid_y + row * PITCH}" width="{CELL}" '
                        f'height="{CELL}" rx="2" fill="{LEVELS[0]}"/>')

    for col, week in enumerate(columns):
        for row, cell in enumerate(week):
            if cell is None:
                continue
            date, level, count = cell
            if level == 0:
                continue                              # nothing to eat here
            plural = "" if count == 1 else "s"
            if snake:
                anim = (f'class="e" style="animation-delay:'
                        f'{eat_delays[(col, row)]:.2f}s"')
            else:
                # Fallback wave: fills the year in from the left.
                anim = f'class="d" style="animation-delay:{col * 0.022 + row * 0.012:.2f}s"'
            body.append(
                f'  <rect {anim} x="{grid_x + col * PITCH}" '
                f'y="{grid_y + row * PITCH}" width="{CELL}" height="{CELL}" '
                f'rx="2" fill="{LEVELS[min(level, 4)]}">'
                f'<title>{count} contribution{plural} on {date.isoformat()}</title>'
                f'</rect>'
            )

    if snake:
        body.extend(segments)

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

    if snake:
        style = snake_css
    else:
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
