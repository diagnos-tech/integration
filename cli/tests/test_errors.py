"""🇺🇸 `main.app()`'s exception wrapper: an SDK `NotFoundError` becomes exit code 4, no traceback.

These go through `diagnos_cli.main.app` (the console-script entry point),
not `typer_app` directly — `exit_codes.classify` only ever runs inside
`app`'s `except DiagnosError` (`main.py`'s own docstring explains why
`CliRunner.invoke(typer_app, ...)` would not exercise it: click's test
runner sets `standalone_mode=False` and swallows the exception itself,
before it would ever reach our wrapper).

🇧🇷 O wrapper de exceção de `main.app()`: um `NotFoundError` do SDK vira
código de saída 4, sem traceback.

Estes passam por `diagnos_cli.main.app` (o ponto de entrada do
console-script), não por `typer_app` direto — `exit_codes.classify` só roda
dentro do `except DiagnosError` do `app` (a própria docstring de `main.py`
explica o porquê: o runner de teste do click seta `standalone_mode=False` e
engole a exceção ele mesmo, antes que ela chegasse ao nosso wrapper).
"""

from __future__ import annotations

import sys

import pytest
from diagnos import DiagnosError
from diagnos_cli import main as main_module
from diagnos_cli.exit_codes import EXIT_GENERAL, classify

from .conftest import FakeDiagnos


def test_not_found_exits_4_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    patched_build_client: FakeDiagnos,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """🇺🇸 `patients get <unknown id>` raises `NotFoundError`; `app()` must translate it, never crash raw.

    🇧🇷 `patients get <id desconhecido>` lança `NotFoundError`; `app()` precisa traduzir, nunca estourar cru.
    """
    monkeypatch.setattr(sys, "argv", ["diagnos", "patients", "get", "does-not-exist"])
    with pytest.raises(SystemExit) as exc_info:
        main_module.app()
    assert exc_info.value.code == 4
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
    assert "Not found" in captured.err


def test_classify_falls_back_to_exit_general_for_an_unmapped_diagnos_error() -> None:
    """🇺🇸 A bare `DiagnosError` matches none of `_RULES` — `classify` still has to return something, not raise.

    🇧🇷 Um `DiagnosError` puro não bate com nenhuma regra de `_RULES` —
    `classify` ainda assim precisa devolver algo, nunca lançar.
    """
    code, label = classify(DiagnosError("an unmapped, unforeseen failure"))
    assert code == EXIT_GENERAL
    assert label == "Error · Erro"
