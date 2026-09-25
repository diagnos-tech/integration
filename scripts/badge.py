"""🇺🇸 Turns `coverage.json` into a shields.io endpoint badge (`{"schemaVersion": 1, ...}`) on stdout.

The README's coverage badge reads this JSON from the `badges` branch, which
`unit-tests.yml` updates on every push to `develop` — no third-party
coverage service, no token, nothing to sign up for.
Run: `python3 scripts/badge.py coverage.json`.

🇧🇷 Transforma o `coverage.json` num badge de endpoint do shields.io (`{"schemaVersion": 1, ...}`) no stdout.

O badge de cobertura do README lê este JSON da branch `badges`, que o
`unit-tests.yml` atualiza a cada push na `develop` — sem serviço de
cobertura de terceiros, sem token, sem cadastro.
Rode: `python3 scripts/badge.py coverage.json`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 🇺🇸 Lowest percentage for each color, highest first. 🇧🇷 Menor porcentagem de cada cor, da maior para a menor.
COLORS = ((95.0, "brightgreen"), (90.0, "green"), (80.0, "yellowgreen"), (70.0, "yellow"), (60.0, "orange"))


def badge(percent: float) -> dict[str, object]:
    """🇺🇸 The endpoint payload for `percent` (one decimal). 🇧🇷 O payload do endpoint para `percent` (uma casa)."""
    color = next((name for floor, name in COLORS if percent >= floor), "red")
    return {"schemaVersion": 1, "label": "coverage", "message": f"{percent:.1f}%", "color": color}


def main(argv: list[str]) -> int:
    """🇺🇸 Reads `totals.percent_covered` from the given `coverage.json`. 🇧🇷 Lê `totals.percent_covered` do arquivo."""
    if len(argv) != 1:
        print("usage · uso: python3 scripts/badge.py coverage.json", file=sys.stderr)
        return 2
    totals = json.loads(Path(argv[0]).read_text(encoding="utf-8"))["totals"]
    print(json.dumps(badge(float(totals["percent_covered"]))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
