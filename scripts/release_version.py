"""🇺🇸 The release guard: one version everywhere, and a tag that says exactly that version.

`diagnos`, `diagnos-cli`, `diagnos-api` and the Rust crate are released
together, under one number. A version on PyPI can never be uploaded twice,
so the release workflow runs this before it builds anything:

- the three `pyproject.toml` and the crate's `Cargo.toml` agree;
- on a tag, the tag is `v<that version>`, the tagged commit is already on
  `develop`, and `CHANGELOG.md` gives the version a date instead of
  `Unreleased`.

Run: `python3 scripts/release_version.py` (standard library only; the
workflow runs it before uv is installed).

🇧🇷 A guarda do release: uma versão em todo lugar, e uma tag que diz exatamente essa versão.

`diagnos`, `diagnos-cli`, `diagnos-api` e o crate Rust são lançados juntos,
sob um número só. Uma versão no PyPI nunca pode ser enviada duas vezes,
então o workflow de release roda isto antes de construir qualquer coisa:

- os três `pyproject.toml` e o `Cargo.toml` do crate concordam;
- numa tag, a tag é `v<essa versão>`, o commit marcado já está na
  `develop`, e o `CHANGELOG.md` dá uma data à versão em vez de
  `Unreleased`.

Rode: `python3 scripts/release_version.py` (só biblioteca padrão; o workflow
o roda antes de o uv estar instalado).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
MANIFESTS: Final = {
    "apps/sdk/pyproject.toml": "project",
    "apps/cli/pyproject.toml": "project",
    "apps/api/pyproject.toml": "project",
    "apps/sdk/native/Cargo.toml": "package",
}
TRUNK: Final = "origin/develop"


def versions(root: Path = ROOT) -> dict[str, str]:
    """🇺🇸 `{manifest: version}` for the three packages and the crate.

    🇧🇷 `{manifesto: versão}` dos três pacotes e do crate.
    """
    found: dict[str, str] = {}
    for manifest, table in MANIFESTS.items():
        with (root / manifest).open("rb") as handle:
            found[manifest] = str(tomllib.load(handle)[table]["version"])
    return found


def changelog_date(version: str, root: Path = ROOT) -> str | None:
    """🇺🇸 What `CHANGELOG.md` puts after `## [version] - `, or `None` without that heading.

    🇧🇷 O que o `CHANGELOG.md` põe depois de `## [versão] - `, ou `None` sem esse título.
    """
    heading = re.compile(rf"^## \[{re.escape(version)}\] - (?P<date>.+)$", re.MULTILINE)
    match = heading.search((root / "CHANGELOG.md").read_text(encoding="utf-8"))
    return match["date"].strip() if match else None


def on_trunk(root: Path = ROOT) -> bool:
    """🇺🇸 Whether `HEAD` is already part of `develop`. 🇧🇷 Se o `HEAD` já faz parte da `develop`."""
    result = subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["git", "merge-base", "--is-ancestor", "HEAD", TRUNK],  # noqa: S607 — git on PATH
        cwd=root,
        check=False,
    )
    return result.returncode == 0


def problems(tag: str | None, root: Path = ROOT) -> list[str]:
    """🇺🇸 One line per reason not to release; `tag` is `None` on a run that publishes nothing.

    🇧🇷 Uma linha por motivo para não lançar; `tag` é `None` numa execução que não publica nada.
    """
    found = versions(root)
    if len(set(found.values())) != 1:
        return [f"{manifest}: {version}" for manifest, version in found.items()]
    version = next(iter(found.values()))
    if tag is None:
        return []
    reasons: list[str] = []
    if tag != f"v{version}":
        reasons.append(f"tag {tag} is not · não é v{version}")
    date = changelog_date(version, root)
    if date is None or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        reasons.append(f"CHANGELOG.md: [{version}] has no date · não tem data ({date or 'missing · ausente'})")
    if not on_trunk(root):
        reasons.append(f"the tagged commit is not on · o commit marcado não está em {TRUNK}")
    return reasons


def main() -> int:
    """🇺🇸 Prints the version, or every reason not to release; exit code 1 if there is any.

    🇧🇷 Imprime a versão, ou todo motivo para não lançar; código de saída 1 se houver algum.
    """
    tag = os.environ.get("GITHUB_REF_NAME") if os.environ.get("GITHUB_REF_TYPE") == "tag" else None
    reasons = problems(tag)
    for line in reasons:
        print(line)
    if reasons:
        print(f"{len(reasons)} problem(s) · problema(s)")
        return 1
    version = next(iter(versions().values()))
    print(f"{version} — {'tag ' + tag if tag else 'no tag: nothing is published · sem tag: nada é publicado'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
