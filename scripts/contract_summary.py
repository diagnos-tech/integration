"""Renders the Pact contract as a Markdown table for the GitHub job summary.

One row per interaction (what the SDK asks, the provider state the vault must set up, and the status it must
answer), so a reviewer sees the contract without opening the JSON.

Usage: `python3 scripts/contract_summary.py contracts/diagnos-sdk-diagnos-vault.json`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def summary(contract: dict[str, object]) -> str:
    """Renders a parsed Pact contract as Markdown: a heading, an interaction count and a table."""
    interactions = contract["interactions"]
    assert isinstance(interactions, list)
    lines = [
        f"### Contract: {contract['consumer']['name']} → {contract['provider']['name']}",  # type: ignore[index]
        "",
        f"{len(interactions)} interactions",
        "",
        "| Request | Provider state | Status | Description |",
        "|---|---|---|---|",
    ]
    for interaction in interactions:
        request, response = interaction["request"], interaction["response"]
        states = ", ".join(state["name"] for state in interaction.get("providerStates", [])) or "—"
        lines.append(
            f"| `{request['method']} {request['path']}` | {states} | {response['status']} "
            f"| {interaction['description']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    """Prints the Markdown summary of each contract file named in `argv`; always returns 0."""
    for name in argv:
        print(summary(json.loads(Path(name).read_text(encoding="utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
