"""🇺🇸 `diagnos-api dev-certs`: what it writes, what it refuses, and a real mTLS handshake with its output.

The last test is the only one in the suite that runs uvicorn with real TLS:
it serves the app with the generated server pair and CA, then calls
`/healthz` with the generated client pair, without any, and with a client
certificate from a CA nobody trusted.

🇧🇷 `diagnos-api dev-certs`: o que ele grava, o que ele recusa, e um handshake mTLS de verdade com o resultado.

O último teste é o único da suíte que roda o uvicorn com TLS de verdade:
serve o app com o par do servidor e a CA gerados, depois chama `/healthz`
com o par de cliente gerado, sem nenhum, e com um certificado de cliente de
uma CA em que ninguém confiou.
"""

from __future__ import annotations

import socket
import ssl
import stat
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
import uvicorn
from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from diagnos_api import dev_certs, main
from diagnos_api.app import create_app
from diagnos_api.mtls import ClientCertH11Protocol, ssl_config_for_uvicorn
from diagnos_api.settings import ApiSettings

from conftest import FakeDiagnos


def _load(path: Path) -> x509.Certificate:
    """🇺🇸 A PEM certificate from disk. 🇧🇷 Um certificado PEM do disco."""
    return x509.load_pem_x509_certificate(path.read_bytes())


def test_generate_writes_a_ca_a_server_and_a_client_the_ca_signed(tmp_path: Path) -> None:
    """🇺🇸 Six files; keys `0600` in a `0700` directory; both leaves signed by the CA with the right usages.

    🇧🇷 Seis arquivos; chaves `0600` num diretório `0700`; as duas folhas assinadas pela CA com os usos certos.
    """
    written = dev_certs.generate(tmp_path / "certs", client_cn="billing-system")

    assert stat.S_IMODE((tmp_path / "certs").stat().st_mode) == 0o700
    for key in (written.ca_key, written.server_key, written.client_key):
        assert stat.S_IMODE(key.stat().st_mode) == 0o600
    ca, server, client = _load(written.ca), _load(written.server), _load(written.client)
    server.verify_directly_issued_by(ca)
    client.verify_directly_issued_by(ca)
    assert ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is True
    names = server.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert "localhost" in names.get_values_for_type(x509.DNSName)
    assert {str(ip) for ip in names.get_values_for_type(x509.IPAddress)} == {"127.0.0.1", "::1"}
    usages = client.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert list(usages) == [ExtendedKeyUsageOID.CLIENT_AUTH]
    assert client.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "billing-system"
    assert written.environment()["DIAGNOS_API_HOST"] == "127.0.0.1"


def test_generate_never_replaces_files_unless_forced(tmp_path: Path) -> None:
    """🇺🇸 A second run stops (the client certificate may already be in use); `force` replaces everything.

    🇧🇷 Uma segunda execução para (o certificado de cliente pode já estar em uso); `force` substitui tudo.
    """
    first = dev_certs.generate(tmp_path)
    before = first.client.read_bytes()
    with pytest.raises(dev_certs.DevCertsError, match="--force"):
        dev_certs.generate(tmp_path)
    assert first.client.read_bytes() == before
    dev_certs.generate(tmp_path, force=True)
    assert first.client.read_bytes() != before


def test_generate_says_how_to_get_cryptography(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """🇺🇸 Without the optional dependency, the error names the extra to install.

    🇧🇷 Sem a dependência opcional, o erro nomeia o extra a instalar.
    """
    import diagnos_api

    monkeypatch.setitem(sys.modules, "diagnos_api._pki", None)
    monkeypatch.delattr(diagnos_api, "_pki", raising=False)
    with pytest.raises(dev_certs.DevCertsError, match=r"diagnos-api\[dev\]"):
        dev_certs.generate(tmp_path)
    assert not list(tmp_path.iterdir())


def test_the_command_prints_what_to_run_next(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """🇺🇸 `diagnos-api dev-certs DIR` prints the exports and a `curl`; a second run exits 2.

    🇧🇷 `diagnos-api dev-certs DIR` mostra os exports e um `curl`; uma segunda execução sai com 2.
    """
    main.run(["dev-certs", str(tmp_path)])
    out = capsys.readouterr().out
    assert f"export DIAGNOS_API_MTLS_CA_FILE={tmp_path / 'ca.pem'}" in out
    assert "curl --cacert" in out
    with pytest.raises(SystemExit) as exited:
        main.run(["dev-certs", str(tmp_path)])
    assert exited.value.code == 2
    assert "--force" in capsys.readouterr().err


def _free_port() -> int:
    """🇺🇸 A loopback port nobody is listening on. 🇧🇷 Uma porta de loopback em que ninguém escuta."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def _serving(settings: ApiSettings, vault: FakeDiagnos) -> Iterator[str]:
    """🇺🇸 The app under real uvicorn with mandatory client certificates; yields its base URL.

    🇧🇷 O app sob um uvicorn de verdade com certificado de cliente obrigatório; devolve a URL base.
    """
    config = uvicorn.Config(
        create_app(settings, vault),  # type: ignore[arg-type]
        host=settings.host,
        port=settings.port,
        http=ClientCertH11Protocol,
        log_config=None,
        **ssl_config_for_uvicorn(settings),
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started, "uvicorn did not start · o uvicorn não subiu"
    try:
        yield f"https://localhost:{settings.port}"
    finally:
        server.should_exit = True
        thread.join(10)


def _client_context(ca: Path, pair: tuple[Path, Path] | None) -> ssl.SSLContext:
    """🇺🇸 Trusts `ca`; presents `pair` when given. 🇧🇷 Confia em `ca`; apresenta `pair` quando dado."""
    context = ssl.create_default_context(cafile=str(ca))
    if pair is not None:
        context.load_cert_chain(certfile=str(pair[0]), keyfile=str(pair[1]))
    return context


def test_the_generated_certificates_complete_a_real_mtls_handshake(tmp_path: Path, fake_vault: FakeDiagnos) -> None:
    """🇺🇸 The client pair gets a 200; no certificate, or one from a stranger CA, never reaches a route.

    🇧🇷 O par de cliente recebe 200; sem certificado, ou com um de uma CA estranha, nunca chega a uma rota.
    """
    written = dev_certs.generate(tmp_path / "certs")
    stranger = dev_certs.generate(tmp_path / "stranger")
    settings = ApiSettings.from_env({**written.environment(), "DIAGNOS_API_PORT": str(_free_port())})

    with _serving(settings, fake_vault) as url:
        ok = httpx.get(f"{url}/healthz", verify=_client_context(written.ca, (written.client, written.client_key)))
        assert (ok.status_code, ok.json()) == (200, {"status": "ok"})
        for pair in (None, (stranger.client, stranger.client_key)):
            with pytest.raises((httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError)):
                httpx.get(f"{url}/healthz", verify=_client_context(written.ca, pair))
