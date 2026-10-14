"""Turns `coverage.json` into a shields.io endpoint badge (`{"schemaVersion": 1, ...}`) on stdout.

The README's coverage badge reads this JSON from the `badges` branch, which `ci.yml` updates on every push to
`main`: no third-party coverage service, no token, nothing to sign up for.

Usage: `python3 scripts/badge.py coverage.json`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Lowest percentage for each color, highest first.
COLORS = ((95.0, "brightgreen"), (90.0, "green"), (80.0, "yellowgreen"), (70.0, "yellow"), (60.0, "orange"))


def badge(percent: float) -> dict[str, object]:
    """The shields.io endpoint payload for `percent`, shown with one decimal."""
    color = next((name for floor, name in COLORS if percent >= floor), "red")
    return {"schemaVersion": 1, "label": "coverage", "message": f"{percent:.1f}%", "color": color}


def main(argv: list[str]) -> int:
    """Prints the badge JSON for the `totals.percent_covered` of the `coverage.json` named in `argv`.

    Args:
        argv: The command-line arguments after the program name: exactly one path.

    Returns:
        The process exit code: 0 on success, 2 on a usage error.
    """
    if len(argv) != 1:
        print("usage: python3 scripts/badge.py coverage.json", file=sys.stderr)
        return 2
    totals = json.loads(Path(argv[0]).read_text(encoding="utf-8"))["totals"]
    print(json.dumps(badge(float(totals["percent_covered"]))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
