"""🇺🇸 `storage_hosts.py`: which presigned URLs the SDK sends ciphertext to, and how `DIAGNOS_STORAGE_HOSTS` changes it.

🇧🇷 `storage_hosts.py`: para quais URLs pré-assinadas o SDK manda ciphertext, e como `DIAGNOS_STORAGE_HOSTS` muda isso.
"""

from __future__ import annotations

import httpx
import pytest
from diagnos.errors import ConfigError, ProtocolError
from diagnos.transport.config import Settings
from diagnos.transport.http import VaultTransport
from diagnos.transport.storage_hosts import (
    DEFAULT_STORAGE_HOSTS,
    parse_storage_hosts,
    require_storage_host,
    storage_host_allowed,
)
from diagnos.transport.token import ServiceAccountToken

_TOKEN = ServiceAccountToken(
    raw="apikey-test",
    key_id="key_1",
    account_id="acc_1",
    workspace_id="ws_1",
    name="svc@ws_1.diagnos.health",
)


@pytest.mark.parametrize(
    "url",
    [
        "https://diagnosusercontent.com/a",
        "https://ws-1.diagnosusercontent.com/objects/v1?X-Amz-Signature=x",
        "https://bucket.acc1.r2.cloudflarestorage.com/key",
        "https://bucket.acc1.eu.r2.cloudflarestorage.com/key",
        "https://STORAGE.DiagnosUserContent.com/a",
    ],
)
def test_the_default_hosts_accept_the_user_content_domain_and_r2(url: str) -> None:
    """🇺🇸 The user-content domain and the R2 endpoint the vault signs against today, subdomains included.

    🇧🇷 O domínio de conteúdo de usuário e o endpoint do R2 contra o qual o cofre assina hoje, com subdomínios.
    """
    assert storage_host_allowed(url, DEFAULT_STORAGE_HOSTS)


@pytest.mark.parametrize(
    "url",
    [
        "http://storage.diagnosusercontent.com/a",
        "https://evil-diagnosusercontent.com/a",
        "https://diagnosusercontent.com.evil.test/a",
        "https://example.com/a",
        "https:///no-host",
        "not a url",
    ],
)
def test_anything_else_is_refused(url: str) -> None:
    """🇺🇸 Plain HTTP, a look-alike suffix, a host merely containing the domain, garbage: all refused.

    🇧🇷 HTTP puro, um sufixo parecido, um host que só contém o domínio, lixo: tudo recusado.
    """
    assert not storage_host_allowed(url, DEFAULT_STORAGE_HOSTS)


def test_the_refusal_names_the_host_and_the_setting() -> None:
    """🇺🇸 The error says which host and which variable fixes it. 🇧🇷 O erro diz qual host e qual variável resolve."""
    with pytest.raises(ProtocolError, match="DIAGNOS_STORAGE_HOSTS") as raised:
        require_storage_host("https://files.example.com/x", DEFAULT_STORAGE_HOSTS)
    assert "files.example.com" in str(raised.value)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, DEFAULT_STORAGE_HOSTS),
        ("   ", DEFAULT_STORAGE_HOSTS),
        ("files.example.com", ("files.example.com",)),
        ("*.Files.Example.com, .b.test  c.test,c.test", ("files.example.com", "b.test", "c.test")),
    ],
)
def test_the_setting_is_a_normalized_list(raw: str | None, expected: tuple[str, ...]) -> None:
    """🇺🇸 Commas or spaces, `*.`/`.` prefixes dropped, lowercased, deduplicated; blank keeps the defaults.

    🇧🇷 Vírgulas ou espaços, prefixos `*.`/`.` descartados, minúsculas, sem repetição; vazio mantém os padrões.
    """
    assert parse_storage_hosts(raw) == expected


@pytest.mark.parametrize("raw", ["https://files.example.com", "files_example.com", "a..b"])
def test_an_entry_that_is_not_a_host_name_is_a_config_error(raw: str) -> None:
    """🇺🇸 A URL or an invalid name fails at startup, not on the first upload.

    🇧🇷 Uma URL ou um nome inválido falha na partida, não no primeiro upload.
    """
    with pytest.raises(ConfigError, match="DIAGNOS_STORAGE_HOSTS"):
        parse_storage_hosts(raw)


def test_settings_read_the_variable_and_show_it_in_repr() -> None:
    """🇺🇸 `Settings.from_env` reads `DIAGNOS_STORAGE_HOSTS`; `repr` shows it (it is not a secret).

    🇧🇷 `Settings.from_env` lê `DIAGNOS_STORAGE_HOSTS`; o `repr` o mostra (não é segredo).
    """
    settings = Settings.from_env({"DIAGNOS_API_TOKEN": "apikey-x", "DIAGNOS_STORAGE_HOSTS": "files.example.com"})

    assert settings.storage_hosts == ("files.example.com",)
    assert "files.example.com" in repr(settings)
    assert Settings(api_token="apikey-x").storage_hosts == DEFAULT_STORAGE_HOSTS  # noqa: S106 — fake token


@pytest.mark.parametrize("method", ["upload_bytes", "download_bytes", "download_stream"])
def test_the_transport_refuses_before_sending_anything(method: str) -> None:
    """🇺🇸 Upload, download and streaming all check the host first — storage never sees the request.

    🇧🇷 Upload, download e streaming conferem o host antes — o armazenamento nunca vê a requisição.
    """
    sent: list[httpx.Request] = []

    def storage(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200)

    transport = VaultTransport(
        Settings(api_token="apikey-test", vault_url="https://vault.example.test"),  # noqa: S106 — fake token
        _TOKEN,
        session_keys=lambda: None,
        storage_client=httpx.Client(transport=httpx.MockTransport(storage)),
    )
    url = "https://attacker.example.com/object"

    with pytest.raises(ProtocolError):
        if method == "upload_bytes":
            transport.upload_bytes(url, b"sealed", {"x-amz-server-side-encryption-customer-key": "k"})
        elif method == "download_bytes":
            transport.download_bytes(url)
        else:
            list(transport.download_stream(url))

    assert sent == []
