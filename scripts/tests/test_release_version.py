"""The release guard refuses every version or tag PyPI would get wrong, before anything is built."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import release_version
from scripts.release_version import main, notes, pep440, problems

CHANGELOG = """# Changelog

## [Unreleased]

## [0.2.0rc1] - 2026-10-01

### Added

- Something.

## [0.1.0] - Unreleased

- First.
"""


def tree(tmp_path: Path, package: str, crate: str) -> Path:
    """Builds a repository root holding both manifests at the given versions and the changelog."""
    (tmp_path / "apps/sdk/native").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(f'[project]\nversion = "{package}"\n', encoding="utf-8")
    (tmp_path / "apps/sdk/native/Cargo.toml").write_text(f'[package]\nversion = "{crate}"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("0.2.0-rc.1", "0.2.0rc1"),
        ("0.2.0-rc1", "0.2.0rc1"),
        ("1.0.0-b.2", "1.0.0b2"),
        ("1.0.0-a.3", "1.0.0a3"),
        ("1.0.0", "1.0.0"),
        ("1.0.0-dev.1", "1.0.0-dev.1"),
    ],
)
def test_pep440_spells_a_semver_pre_release_the_pypi_way(given: str, expected: str) -> None:
    """SemVer pre-releases become PEP 440, the rest stays."""
    assert pep440(given) == expected


def test_a_release_candidate_agrees_across_cargo_and_pyproject(tmp_path: Path) -> None:
    """`0.2.0rc1` and `0.2.0-rc.1` are one version."""
    assert problems(None, tree(tmp_path, "0.2.0rc1", "0.2.0-rc.1")) == []


@pytest.mark.parametrize(
    ("package", "crate", "reason"),
    [
        ("0.1.0", "0.1.1", "pyproject.toml: 0.1.0"),
        ("0.1.0.dev1", "0.1.0.dev1", "not a release version"),
        ("0.1.0+local", "0.1.0+local", "not a release version"),
        ("0.1.0\\n", "0.1.0\\n", "not a release version"),
    ],
)
def test_disagreeing_or_unpublishable_versions_are_refused(
    tmp_path: Path, package: str, crate: str, reason: str
) -> None:
    """Two numbers, or one PyPI cannot hold, stop the build."""
    assert any(reason in line for line in problems(None, tree(tmp_path, package, crate)))


def test_a_tag_must_name_the_version_be_dated_and_be_on_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Wrong tag, undated changelog, off trunk: three reasons."""
    monkeypatch.setattr(release_version, "on_trunk", lambda root: False)
    reasons = problems("v0.1.1", tree(tmp_path, "0.1.0", "0.1.0"))
    assert [line.split(" ")[0] for line in reasons] == ["tag", "CHANGELOG.md:", "the"]


def test_a_dated_version_tagged_on_main_is_released(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Everything in order: no reason left."""
    monkeypatch.setattr(release_version, "on_trunk", lambda root: True)
    assert problems("v0.2.0rc1", tree(tmp_path, "0.2.0rc1", "0.2.0-rc.1")) == []


def test_notes_are_the_section_body_without_its_heading(tmp_path: Path) -> None:
    """One section, up to the next heading."""
    root = tree(tmp_path, "0.2.0rc1", "0.2.0rc1")
    assert notes("0.2.0rc1", root) == "### Added\n\n- Something."
    assert notes("9.9.9", root) == ""


def test_main_writes_this_repository_s_version_for_the_next_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without a tag nothing is published, and `version=` is written."""
    output = tmp_path / "output"
    monkeypatch.delenv("GITHUB_REF_TYPE", raising=False)
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    assert main([]) == 0
    version = next(iter(release_version.versions().values()))
    assert output.read_text(encoding="utf-8") == f"version={version}\n"
    assert "nothing is published" in capsys.readouterr().out
