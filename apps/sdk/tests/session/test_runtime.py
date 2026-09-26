"""🇺🇸 `collect_runtime`: the shape `session/registry` expects, and that it never raises.

🇧🇷 `collect_runtime`: a forma que `session/registry` espera, e que nunca lança.
"""

from __future__ import annotations

import getpass
import socket

import pytest
from diagnos.session import runtime as runtime_module
from diagnos.session.runtime import collect_runtime

_REQUIRED_STRING_FIELDS = ("sdk_name", "sdk_version", "language", "os", "arch")


class _FakePath:
    """🇺🇸 A stand-in for `pathlib.Path`, scripted per test to cover `_detect_container`'s branches.

    Replaces `diagnos.session.runtime.Path` itself (not the real filesystem)
    so a test can force "no markers anywhere" or "checking a path raised" —
    scenarios this container-based sandbox does not otherwise produce, since
    `/proc/1/cgroup` here always already carries a real marker.

    🇧🇷 Um substituto de `pathlib.Path`, roteirizado por teste para cobrir os
    ramos de `_detect_container`.

    Substitui o próprio `diagnos.session.runtime.Path` (não o sistema de
    arquivos real) para um teste forçar "nenhum marcador em lugar nenhum" ou
    "checar um path lançou" — cenários que este sandbox baseado em container
    não produz sozinho, já que `/proc/1/cgroup` aqui sempre já carrega um
    marcador de verdade.
    """

    def __init__(self, exists_by_path: dict[str, bool], *, raises_on: str | None = None, cgroup_text: str = "") -> None:
        """🇺🇸 `exists_by_path` answers `.exists()`; `raises_on` makes that one path's `.exists()` raise `OSError`.

        🇧🇷 `exists_by_path` responde `.exists()`; `raises_on` faz o `.exists()` desse path lançar `OSError`.
        """
        self._exists_by_path = exists_by_path
        self._raises_on = raises_on
        self._cgroup_text = cgroup_text

    def factory(self) -> type:
        """🇺🇸 A `Path`-shaped class closing over this script. 🇧🇷 Uma classe `Path` fechando sobre este roteiro."""
        exists_by_path = self._exists_by_path
        raises_on = self._raises_on
        cgroup_text = self._cgroup_text

        class _Scripted:
            def __init__(self, raw: str) -> None:
                self._raw = raw

            def exists(self) -> bool:
                if self._raw == raises_on:
                    raise OSError("boom")
                return exists_by_path.get(self._raw, False)

            def read_text(self, errors: str = "strict") -> str:
                return cgroup_text

        return _Scripted


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


def test_container_is_true_when_dockerenv_marker_is_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 `/.dockerenv` existing is enough by itself, with no need to even look at `/proc/1/cgroup`.

    🇧🇷 `/.dockerenv` existir já basta sozinho, sem nem precisar olhar `/proc/1/cgroup`.
    """
    monkeypatch.setattr(runtime_module, "Path", _FakePath({"/.dockerenv": True}).factory())
    runtime = collect_runtime("0.1.0")
    assert runtime["container"] is True


def test_container_is_false_with_no_markers_at_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 Neither `/.dockerenv` nor a matching cgroup marker means "not a container".

    🇧🇷 Nem `/.dockerenv` nem um marcador de cgroup correspondente significa "não é um container".
    """
    monkeypatch.setattr(runtime_module, "Path", _FakePath({"/.dockerenv": False, "/proc/1/cgroup": False}).factory())
    runtime = collect_runtime("0.1.0")
    assert runtime["container"] is False


def test_container_reads_the_cgroup_file_for_its_markers(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 With no `/.dockerenv`, a `kubepods`/`docker`/`containerd` substring in `/proc/1/cgroup` still counts.

    🇧🇷 Sem `/.dockerenv`, uma substring `kubepods`/`docker`/`containerd` em `/proc/1/cgroup` ainda conta.
    """
    fake = _FakePath({"/.dockerenv": False, "/proc/1/cgroup": True}, cgroup_text="0::/kubepods/burstable/pod123")
    monkeypatch.setattr(runtime_module, "Path", fake.factory())
    runtime = collect_runtime("0.1.0")
    assert runtime["container"] is True


def test_container_detection_swallows_os_errors_and_reports_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 A path check that raises `OSError` (a permission-locked sandbox) degrades to `False`, never a crash.

    🇧🇷 Uma checagem de path que lança `OSError` (um sandbox travado por permissão) degrada para `False`, nunca quebra.
    """
    fake = _FakePath({}, raises_on="/.dockerenv")
    monkeypatch.setattr(runtime_module, "Path", fake.factory())
    runtime = collect_runtime("0.1.0")
    assert runtime["container"] is False


def test_cloud_marker_env_var_is_reported_as_the_cloud_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 A recognized cloud env var (`AWS_EXECUTION_ENV`) becomes `runtime["cloud"] == "aws"`.

    🇧🇷 Uma env var de nuvem reconhecida (`AWS_EXECUTION_ENV`) vira `runtime["cloud"] == "aws"`.
    """
    monkeypatch.setenv("AWS_EXECUTION_ENV", "AWS_ECS_FARGATE")
    runtime = collect_runtime("0.1.0")
    assert runtime["cloud"] == "aws"


def test_no_cloud_marker_env_var_leaves_cloud_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 With none of the marker env vars set, `cloud` is omitted, never a guessed value.

    🇧🇷 Sem nenhuma das env vars marcadoras definidas, `cloud` é omitido, nunca um valor advinhado.
    """
    for variable, _cloud_name in runtime_module._CLOUD_ENV_MARKERS:  # noqa: SLF001 — the exact table under test
        monkeypatch.delenv(variable, raising=False)
    runtime = collect_runtime("0.1.0")
    assert "cloud" not in runtime
