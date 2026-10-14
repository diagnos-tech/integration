"""The release guard: one version everywhere, and a tag that says exactly that version.

`diagnos` and its Rust crate are released together, under one number. A version on PyPI can never be uploaded
twice, so the package workflow runs this before it builds anything:

- `pyproject.toml` and the crate's `Cargo.toml` agree, on a version PyPI and GHCR can hold (no local or `.dev`
  segment);
- on a tag, the tag is `v<that version>`, the tagged commit is already on `main`, and `CHANGELOG.md` gives the
  version a date instead of `Unreleased`.

It writes the checked version to `$GITHUB_OUTPUT` for the jobs after it. With `--notes` it prints that version's
`CHANGELOG.md` section instead, which is the body of the GitHub release.

Usage: `python3 scripts/release_version.py [--notes]` (standard library only; the workflow runs it before uv is
installed).
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
    "pyproject.toml": "project",
    "apps/sdk/native/Cargo.toml": "package",
}
RELEASE: Final = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?")
# Cargo spells a pre-release the SemVer way (`0.2.0-rc.1`), PyPI the PEP 440 way (`0.2.0rc1`): the same release.
_SEMVER_PRE: Final = re.compile(r"(?P<core>[0-9]+\.[0-9]+\.[0-9]+)-(?P<kind>a|b|rc)\.?(?P<number>[0-9]+)")
# Releases are cut from `main`.
TRUNK: Final = "origin/main"


def pep440(version: str) -> str:
    """Returns `version` as PyPI writes it: a SemVer pre-release (`0.2.0-rc.1`) becomes `0.2.0rc1`, the rest is kept."""
    match = _SEMVER_PRE.fullmatch(version)
    return f"{match['core']}{match['kind']}{match['number']}" if match else version


def versions(root: Path = ROOT) -> dict[str, str]:
    """Reads `{manifest: version}` for the package and the crate, both as PyPI writes them."""
    found: dict[str, str] = {}
    for manifest, table in MANIFESTS.items():
        with (root / manifest).open("rb") as handle:
            found[manifest] = pep440(str(tomllib.load(handle)[table]["version"]))
    return found


def changelog_date(version: str, root: Path = ROOT) -> str | None:
    """Returns what `CHANGELOG.md` puts after `## [version] - `, or `None` without that heading."""
    heading = re.compile(rf"^## \[{re.escape(version)}\] - (?P<date>.+)$", re.MULTILINE)
    match = heading.search((root / "CHANGELOG.md").read_text(encoding="utf-8"))
    return match["date"].strip() if match else None


def notes(version: str, root: Path = ROOT) -> str:
    """Returns the body of `version`'s section in `CHANGELOG.md`, without its heading; empty when there is none."""
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = rf"^## \[{re.escape(version)}\][^\n]*\n"
    section = re.search(heading + r"(?P<body>.*?)(?=^## \[|\Z)", text, re.MULTILINE | re.DOTALL)
    return section["body"].strip() if section else ""


def on_trunk(root: Path = ROOT) -> bool:
    """Whether `HEAD` is already part of `main` (the trunk releases are cut from)."""
    result = subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["git", "merge-base", "--is-ancestor", "HEAD", TRUNK],  # noqa: S607 — git on PATH
        cwd=root,
        check=False,
    )
    return result.returncode == 0


def problems(tag: str | None, root: Path = ROOT) -> list[str]:
    """Collects the reasons not to release, one line each.

    Args:
        tag: The git tag being released, or `None` on a run that publishes nothing.
        root: The repository root holding the manifests and `CHANGELOG.md`.

    Returns:
        The reasons, in the order they were found; empty when the release may go ahead.
    """
    found = versions(root)
    if len(set(found.values())) != 1:
        return [f"{manifest}: {version}" for manifest, version in found.items()]
    version = next(iter(found.values()))
    if not RELEASE.fullmatch(version):
        return [f"{version} is not a release version"]
    if tag is None:
        return []
    reasons: list[str] = []
    if tag != f"v{version}":
        reasons.append(f"tag {tag} is not v{version}")
    date = changelog_date(version, root)
    if date is None or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        reasons.append(f"CHANGELOG.md: [{version}] has no date ({date or 'missing'})")
    if not on_trunk(root):
        reasons.append(f"the tagged commit is not on {TRUNK}")
    return reasons


def main(argv: list[str]) -> int:
    """Prints the checked version (or its notes), or every reason not to release.

    Args:
        argv: The command-line arguments after the program name: empty, or `["--notes"]`.

    Returns:
        The process exit code: 0 when the release may go ahead, 1 when there is any reason not to.
    """
    tag = os.environ.get("GITHUB_REF_NAME") if os.environ.get("GITHUB_REF_TYPE") == "tag" else None
    reasons = problems(tag)
    for line in reasons:
        print(line)
    if reasons:
        print(f"{len(reasons)} problem(s)")
        return 1
    version = next(iter(versions().values()))
    if argv == ["--notes"]:
        print(notes(version) or f"diagnos {version}")
        return 0
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"version={version}\n")
    print(f"{version} — {'tag ' + tag if tag else 'no tag: nothing is published'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
