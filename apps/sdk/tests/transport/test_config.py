"""`Settings.from_env`: `OPENBAO_TOKEN_FILE` and `DIAGNOS_HARDEN_PROCESS`.

The rest of `Settings.from_env` (the required `DIAGNOS_API_TOKEN`, every
other env var, the redacted `repr`) is already covered by
`tests/transport/test_token.py`; this file only adds the two fields that
came with the memory-enclave move: the file-backed OpenBao token
(`docs/PROTOCOL.md §11`, the form Kubernetes/Docker Compose secrets prefer
over a plain env var) and the opt-out from process hardening.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from diagnos.errors import ConfigError
from diagnos.transport.config import Settings

_BASE_ENV = {"DIAGNOS_API_TOKEN": "apikey-abc.def.ghi"}  # noqa: S106 — fixture, not a real secret


def test_openbao_token_file_is_read_and_trimmed(tmp_path: Path) -> None:
    """`OPENBAO_TOKEN_FILE` is read and its contents trimmed of surrounding whitespace."""
    token_file = tmp_path / "openbao-token"
    token_file.write_text("  s.supersecrettoken\n", encoding="utf-8")

    settings = Settings.from_env({**_BASE_ENV, "OPENBAO_TOKEN_FILE": str(token_file)})

    assert settings.openbao_token == "s.supersecrettoken"  # noqa: S105 — fixture, not a real secret


def test_openbao_token_file_empty_raises_config_error(tmp_path: Path) -> None:
    """An empty (or whitespace-only) token file is a configuration mistake, not a valid empty token."""
    token_file = tmp_path / "openbao-token"
    token_file.write_text("   \n", encoding="utf-8")

    with pytest.raises(ConfigError):
        Settings.from_env({**_BASE_ENV, "OPENBAO_TOKEN_FILE": str(token_file)})


def test_openbao_token_file_missing_raises_config_error(tmp_path: Path) -> None:
    """A path that does not exist raises `ConfigError`, not a bare `OSError`."""
    missing_path = tmp_path / "does-not-exist"

    with pytest.raises(ConfigError):
        Settings.from_env({**_BASE_ENV, "OPENBAO_TOKEN_FILE": str(missing_path)})


def test_openbao_token_env_var_wins_over_the_file(tmp_path: Path) -> None:
    """`OPENBAO_TOKEN` takes precedence when both it and `OPENBAO_TOKEN_FILE` are set."""
    token_file = tmp_path / "openbao-token"
    token_file.write_text("token-from-file", encoding="utf-8")

    settings = Settings.from_env(
        {
            **_BASE_ENV,
            "OPENBAO_TOKEN": "token-from-env",  # noqa: S106 — fixture, not a real secret
            "OPENBAO_TOKEN_FILE": str(token_file),
        }
    )

    assert settings.openbao_token == "token-from-env"  # noqa: S105 — fixture, not a real secret


def test_neither_openbao_token_nor_file_is_none() -> None:
    """With neither `OPENBAO_TOKEN` nor `OPENBAO_TOKEN_FILE` set, `openbao_token` is `None`."""
    settings = Settings.from_env(_BASE_ENV)
    assert settings.openbao_token is None


def test_harden_process_defaults_to_true() -> None:
    """With `DIAGNOS_HARDEN_PROCESS` unset, `harden_process` defaults to `True`."""
    settings = Settings.from_env(_BASE_ENV)
    assert settings.harden_process is True


def test_harden_process_can_be_turned_off() -> None:
    """`DIAGNOS_HARDEN_PROCESS=0` turns `harden_process` off — the escape hatch to attach a debugger."""
    settings = Settings.from_env({**_BASE_ENV, "DIAGNOS_HARDEN_PROCESS": "0"})
    assert settings.harden_process is False


@pytest.mark.parametrize(("raw", "expected"), [(None, None), ("", None), ("month", "month"), (" Day ", "day")])
def test_time_precision_is_read_and_normalized(raw: str | None, expected: str | None) -> None:
    """`DIAGNOS_TIME_PRECISION` is optional, case-insensitive and trimmed."""
    env = dict(_BASE_ENV) if raw is None else {**_BASE_ENV, "DIAGNOS_TIME_PRECISION": raw}
    settings = Settings.from_env(env)
    assert settings.time_precision == expected
    assert f"time_precision={expected!r}" in repr(settings)


def test_time_precision_rejects_an_unknown_value() -> None:
    """A typo in the precision is a `ConfigError`, never a silent default."""
    with pytest.raises(ConfigError, match="DIAGNOS_TIME_PRECISION"):
        Settings.from_env({**_BASE_ENV, "DIAGNOS_TIME_PRECISION": "year"})


def test_timeout_seconds_rejects_a_non_numeric_value() -> None:
    """A `DIAGNOS_TIMEOUT_SECONDS` that is not a number is a `ConfigError`, not a `ValueError`."""
    with pytest.raises(ConfigError, match="DIAGNOS_TIMEOUT_SECONDS"):
        Settings.from_env({**_BASE_ENV, "DIAGNOS_TIMEOUT_SECONDS": "soon"})
