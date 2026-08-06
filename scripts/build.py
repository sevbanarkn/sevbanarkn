"""Regenerate every SVG in svg/.

Each generator is isolated: a broken avatar or an unreachable github.com must
not stop the other panels from refreshing.
"""

import sys
import traceback

import ascii_avatar
import contrib_graph
import info_card

STEPS = [
    ("info card", info_card.build),
    ("ascii avatar", ascii_avatar.build),
    ("contribution graph", contrib_graph.build),
]


def main():
    failures = []
    for name, fn in STEPS:
        print(f"[{name}]")
        try:
            fn()
        except Exception:                             # noqa: BLE001 - keep going
            traceback.print_exc()
            failures.append(name)
        print()

    if len(failures) == len(STEPS):
        print("all generators failed", file=sys.stderr)
        return 1
    if failures:
        print(f"completed with failures: {', '.join(failures)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
