"""🇺🇸 `collect_runtime`: the shape `session/registry` expects, and that it never raises.

🇧🇷 `collect_runtime`: a forma que `session/registry` espera, e que nunca lança.
"""

from __future__ import annotations

import getpass
import socket

import pytest
from diagnos.session.runtime import collect_runtime

_REQUIRED_STRING_FIELDS = ("sdk_name", "sdk_version", "language", "os", "arch")


def test_shape_has_every_required_field_with_no_none_values() -> None:
    """🇺🇸 The required fields are present, non-`None`, and `sdk_name`/`sdk_version` are exact.

    🇧🇷 Os campos obrigatórios estão presentes, não `None`, e `sdk_name`/`sdk_version` são exatos.
    """
    runtime = collect_runtime("9.9.9")

    for field in _REQUIRED_STRING_FIELDS:
        assert field in runtime
        assert runtime[field] is not None

    assert runtime["sdk_name"] == "diagnos-python"
    assert runtime["sdk_version"] == "9.9.9"
    assert str(runtime["language"]).startswith("python ")
    assert "container" in runtime
    assert isinstance(runtime["container"], bool)


def test_no_value_in_the_dict_is_none() -> None:
    """🇺🇸 Optional fields (`hostname`/`user`/`cloud`) are omitted, never sent as `None`.

    🇧🇷 Campos opcionais (`hostname`/`user`/`cloud`) são omitidos, nunca enviados como `None`.
    """
    runtime = collect_runtime("0.1.0")
    assert None not in runtime.values()


def test_hostname_is_truncated_to_64_characters_when_present() -> None:
    """🇺🇸 A present `hostname` never exceeds the 64-character cap.

    🇧🇷 Um `hostname` presente nunca passa do teto de 64 caracteres.
    """
    runtime = collect_runtime("0.1.0")
    hostname = runtime.get("hostname")
    if hostname is not None:
        assert isinstance(hostname, str)
        assert len(hostname) <= 64


def test_container_is_always_a_bool() -> None:
    """🇺🇸 `container` is a required field and always a `bool`, never `None`.

    🇧🇷 `container` é um campo obrigatório e sempre um `bool`, nunca `None`.
    """
    runtime = collect_runtime("0.1.0")
    assert isinstance(runtime["container"], bool)


def test_never_raises_even_with_a_hostile_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 A `socket.gethostname`/`getpass.getuser` that explodes still yields a valid dict.

    🇧🇷 Um `socket.gethostname`/`getpass.getuser` que explode ainda produz um dict válido.
    """

    def _boom_hostname() -> str:
        raise OSError("no hostname for you")

    def _boom_user() -> str:
        raise LookupError("no user for you")

    monkeypatch.setattr(socket, "gethostname", _boom_hostname)
    monkeypatch.setattr(getpass, "getuser", _boom_user)

    runtime = collect_runtime("0.1.0")
    assert "hostname" not in runtime
    assert "user" not in runtime
    assert runtime["sdk_name"] == "diagnos-python"
