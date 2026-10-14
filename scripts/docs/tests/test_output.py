"""Rendering is byte-stable, and `generatedFrom.commit` moves only when the content does."""

from __future__ import annotations

from typing import Any

from scripts.docs.output import render, stamp


def fresh(version: str = "0.1.0") -> dict[str, Any]:
    """A generated document before stamping."""
    return {"schemaVersion": 1, "generatedFrom": {"package": "p", "version": version, "commit": ""}, "items": [2, 1]}


def test_render_sorts_keys_keeps_arrays_and_ends_with_one_newline() -> None:
    """Keys sorted on request, arrays untouched, one newline."""
    text = render({"b": [2, 1], "a": "é"}, sort_keys=True)
    assert text == '{\n  "a": "é",\n  "b": [\n    2,\n    1\n  ]\n}\n'
    assert render({"b": 1, "a": 2}, sort_keys=False).index('"b"') < render({"b": 1, "a": 2}, sort_keys=False).index(
        '"a"'
    )


def test_unchanged_content_keeps_the_committed_commit() -> None:
    """A new `HEAD` alone never makes a file stale."""
    committed = stamp(fresh(), None, commit="aaa1111")
    assert committed["generatedFrom"]["commit"] == "aaa1111"
    assert stamp(fresh(), committed, commit="bbb2222") == committed


def test_changed_content_is_restamped() -> None:
    """Real changes carry the commit they were generated on."""
    committed = stamp(fresh(), None, commit="aaa1111")
    assert stamp(fresh("0.2.0"), committed, commit="bbb2222")["generatedFrom"]["commit"] == "bbb2222"


def test_documents_without_generated_from_are_left_alone() -> None:
    """OpenAPI has no envelope, so nothing is stamped."""
    assert stamp({"openapi": "3.1.0"}, None, commit="aaa1111") == {"openapi": "3.1.0"}
