"""🇺🇸 Renders the Pact contract as a Markdown table for the GitHub job summary.

One row per interaction — what the SDK asks, the provider state the vault
must set up, and the status it must answer — so a reviewer sees the
contract without opening the JSON.
Run: `python3 scripts/contract_summary.py contracts/diagnos-sdk-diagnos-vault.json`.

🇧🇷 Renderiza o contrato Pact como tabela Markdown para o resumo do job no GitHub.

Uma linha por interação — o que o SDK pede, o provider state que o cofre
precisa montar e o status que precisa responder — para quem revisa ver o
contrato sem abrir o JSON.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def summary(contract: dict[str, object]) -> str:
    """🇺🇸 The Markdown for one contract file. 🇧🇷 O Markdown de um arquivo de contrato."""
    interactions = contract["interactions"]
    assert isinstance(interactions, list)
    lines = [
        f"### Contract · Contrato — {contract['consumer']['name']} → {contract['provider']['name']}",  # type: ignore[index]
        "",
        f"{len(interactions)} interactions · interações",
        "",
        "| Request · Requisição | Provider state | Status | Description · Descrição |",
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
    """🇺🇸 Prints the summary of each contract file given. 🇧🇷 Imprime o resumo de cada arquivo de contrato dado."""
    for name in argv:
        print(summary(json.loads(Path(name).read_text(encoding="utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
