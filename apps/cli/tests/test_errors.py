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
from diagnos import (
    AuthenticationError,
    ConfigError,
    ConflictError,
    DiagnosError,
    DiagnosPermissionError,
    EnrollmentDeniedError,
    EnrollmentExpiredError,
    GroupKeyUnavailable,
    NotFoundError,
    QuotaError,
    RateLimitError,
    SessionExpiredError,
    ValidationError,
)
from diagnos_cli import main as main_module
from diagnos_cli.exit_codes import (
    EXIT_AUTH,
    EXIT_CONFIG,
    EXIT_CONFLICT,
    EXIT_GENERAL,
    EXIT_NOT_FOUND,
    EXIT_QUOTA,
    EXIT_RATE_LIMIT,
    classify,
)

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


def test_a_missing_group_key_is_a_permission_exit() -> None:
    """🇺🇸 `GroupKeyUnavailable` is a permission gap: exit 3, with a label that names the group key.

    🇧🇷 `GroupKeyUnavailable` é uma lacuna de permissão: saída 3, com um rótulo que nomeia a chave do grupo.
    """
    code, label = classify(GroupKeyUnavailable("no key for 'sg_x'"))

    assert code == EXIT_AUTH
    assert "security group" in label


# 🇺🇸 One row per leaf `DiagnosError` `exit_codes._RULES` maps — the exact
# same list `apps/cli/README.md`'s "Exit codes" table promises a script.
# `VaultError` subclasses need `code`/`status`; the plain `DiagnosError`
# subclasses take only a message.
# 🇧🇷 Uma linha por `DiagnosError` folha que `exit_codes._RULES` mapeia — a
# mesma lista que a tabela "Exit codes" do `apps/cli/README.md` promete a um
# script. Subclasses de `VaultError` precisam de `code`/`status`; as
# subclasses simples de `DiagnosError` levam só uma mensagem.
_ERROR_MATRIX: list[tuple[Exception, int, str]] = [
    (ConfigError("DIAGNOS_API_TOKEN is required"), EXIT_CONFIG, "Configuration error"),
    (AuthenticationError(code="TokenInvalid", message="bad token", status=401), EXIT_AUTH, "Authentication failed"),
    (DiagnosPermissionError(code="Forbidden", message="not allowed", status=403), EXIT_AUTH, "Permission denied"),
    (GroupKeyUnavailable("no key for 'sg_x'"), EXIT_AUTH, "No key for this security group"),
    (SessionExpiredError("session past expires_at"), EXIT_AUTH, "Session expired"),
    (EnrollmentDeniedError("a person denied this session"), EXIT_AUTH, "Enrollment denied"),
    (EnrollmentExpiredError("nobody approved in time"), EXIT_AUTH, "Enrollment expired"),
    (NotFoundError(code="DocumentNotFound", message="no such patient", status=404), EXIT_NOT_FOUND, "Not found"),
    (QuotaError(code="NoCredit", message="workspace has no credit", status=402), EXIT_QUOTA, "Quota exceeded"),
    (RateLimitError(code="SlowDown", message="too many requests", status=429), EXIT_RATE_LIMIT, "Rate limited"),
    (ConflictError(code="StaleVersion", message="a newer version exists", status=409), EXIT_CONFLICT, "Conflict"),
    (ValidationError(code="BadField", message="unknown field 'typo_field'", status=400), EXIT_GENERAL, "Invalid"),
]


@pytest.mark.parametrize(
    ("exc", "expected_code", "label_snippet"),
    _ERROR_MATRIX,
    ids=[type(exc).__name__ for exc, _, _ in _ERROR_MATRIX],
)
def test_every_documented_error_class_maps_to_its_readme_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    patched_build_client: FakeDiagnos,
    capsys: pytest.CaptureFixture[str],
    exc: Exception,
    expected_code: int,
    label_snippet: str,
) -> None:
    """🇺🇸 Every leaf `DiagnosError` in `apps/cli/README.md`'s table exits with its documented code, cleanly.

    Raised from `FakePatients.get` (any command would do — the mapping
    lives entirely in `main.app`'s wrapper, not in `patients.py`) and run
    through `main_module.app()`, the same entry point a real terminal
    invokes, not `typer_app` directly (`classify` only ever runs inside
    `app`'s `except DiagnosError` — see this file's own module docstring).

    🇧🇷 Toda `DiagnosError` folha na tabela do `apps/cli/README.md` sai com o
    código documentado, de forma limpa.

    Lançada de `FakePatients.get` (qualquer comando serviria — o mapeamento
    mora inteiro no wrapper do `main.app`, não em `patients.py`) e rodada
    por `main_module.app()`, o mesmo ponto de entrada que um terminal de
    verdade invoca, não `typer_app` direto (`classify` só roda dentro do
    `except DiagnosError` do `app` — ver a docstring deste próprio módulo).
    """

    def _raise(patient_id: str, **kwargs: object) -> None:
        """🇺🇸 Always raises `exc`, ignoring every argument. 🇧🇷 Sempre lança `exc`, ignorando todo argumento."""
        raise exc

    monkeypatch.setattr(patched_build_client.patients, "get", _raise)
    monkeypatch.setattr(sys, "argv", ["diagnos", "patients", "get", "pat_1"])

    with pytest.raises(SystemExit) as exc_info:
        main_module.app()

    assert exc_info.value.code == expected_code
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
    assert captured.out == ""
    assert label_snippet in captured.err


def test_a_missing_api_token_is_a_configuration_error_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """🇺🇸 With no `DIAGNOS_API_TOKEN` and no `--token`, `build_client` itself raises — end to end, no fake.

    Deliberately the one test in this file that does *not* use
    `patched_build_client`: `Settings.from_env` (`context.build_client`'s
    own dependency) is what raises `ConfigError` here, so this exercises the
    real, unfaked path from "nothing configured" to a clean exit `2` —
    the scenario `main.py`'s own docstring calls out ("a malformed
    `--vault-url`" is the same category of failure, before any command body
    or fake ever runs).

    🇧🇷 Sem `DIAGNOS_API_TOKEN` nem `--token`, o próprio `build_client`
    lança — ponta a ponta, sem fake.

    De propósito o único teste deste arquivo que *não* usa
    `patched_build_client`: `Settings.from_env` (a própria dependência de
    `context.build_client`) é quem lança `ConfigError` aqui, então isto
    exercita o caminho de verdade, sem fake, de "nada configurado" até uma
    saída limpa `2` — o cenário que a própria docstring de `main.py` cita
    ("um `--vault-url` malformado" é a mesma categoria de falha, antes de
    qualquer corpo de comando ou fake rodar).
    """
    monkeypatch.delenv("DIAGNOS_API_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["diagnos", "status"])

    with pytest.raises(SystemExit) as exc_info:
        main_module.app()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert captured.out == ""
    assert "Configuration error" in captured.err
    assert "DIAGNOS_API_TOKEN" in captured.err
