"""`diagnos-api dev-certs`: what it writes, what it refuses, and a real mTLS handshake with its output.

The last test is the only one in the suite that runs uvicorn with real TLS. It serves the app with the generated
server pair and CA, then calls `/healthz` with the generated client pair, with no client certificate, and with a client
certificate from a CA nobody trusted.
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

from diagnos.api import dev_certs, main
from diagnos.api.app import create_app
from diagnos.api.mtls import ClientCertH11Protocol, ssl_config_for_uvicorn
from diagnos.api.settings import ApiSettings

from conftest import FakeDiagnos


def _load(path: Path) -> x509.Certificate:
    """Loads a PEM certificate from disk."""
    return x509.load_pem_x509_certificate(path.read_bytes())


def test_generate_writes_a_ca_a_server_and_a_client_the_ca_signed(tmp_path: Path) -> None:
    """Six files; keys `0600` in a `0700` directory; both leaves signed by the CA with the right usages."""
    written = dev_certs.generate(tmp_path / "certs", client_cn="billing-system")

    assert stat.S_IMODE((tmp_path / "certs").stat().st_mode) == 0o700
    for key in (written.ca_key, written.server_key, written.client_key):
        assert stat.S_IMODE(key.stat().st_mode) == 0o600
    ca, server, client = _load(written.ca), _load(written.server), _load(written.client)
    server.verify_directly_issued_by(ca)
    client.verify_directly_issued_by(ca)
    assert ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is True
    # A strict client (Python 3.13's default context) refuses a chain without the key identifiers.
    ca_key_id = ca.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest
    for leaf in (server, client):
        assert leaf.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier).value.key_identifier == ca_key_id
    names = server.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert "localhost" in names.get_values_for_type(x509.DNSName)
    assert {str(ip) for ip in names.get_values_for_type(x509.IPAddress)} == {"127.0.0.1", "::1"}
    usages = client.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert list(usages) == [ExtendedKeyUsageOID.CLIENT_AUTH]
    assert client.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "billing-system"
    assert written.environment()["DIAGNOS_API_HOST"] == "127.0.0.1"


def test_generate_never_replaces_files_unless_forced(tmp_path: Path) -> None:
    """A second run stops (the client certificate may already be in use); `force` replaces everything."""
    first = dev_certs.generate(tmp_path)
    before = first.client.read_bytes()
    with pytest.raises(dev_certs.DevCertsError, match="--force"):
        dev_certs.generate(tmp_path)
    assert first.client.read_bytes() == before
    dev_certs.generate(tmp_path, force=True)
    assert first.client.read_bytes() != before


def test_generate_says_how_to_get_cryptography(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Without the optional dependency, the error names the extra to install."""
    import diagnos.api

    monkeypatch.setitem(sys.modules, "diagnos.api._pki", None)
    monkeypatch.delattr(diagnos.api, "_pki", raising=False)
    with pytest.raises(dev_certs.DevCertsError, match=r"diagnos\[dev-certs\]"):
        dev_certs.generate(tmp_path)
    assert not list(tmp_path.iterdir())


def test_the_command_prints_what_to_run_next(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """`diagnos-api dev-certs DIR` prints the exports and a `curl`; a second run exits 2."""
    main.run(["dev-certs", str(tmp_path)])
    out = capsys.readouterr().out
    assert f"export DIAGNOS_API_MTLS_CA_FILE={tmp_path / 'ca.pem'}" in out
    assert "curl --cacert" in out
    with pytest.raises(SystemExit) as exited:
        main.run(["dev-certs", str(tmp_path)])
    assert exited.value.code == 2
    assert "--force" in capsys.readouterr().err


def _free_port() -> int:
    """Returns a loopback port that nobody is listening on."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def _serving(settings: ApiSettings, vault: FakeDiagnos) -> Iterator[str]:
    """Serves the app under real uvicorn with mandatory client certificates and yields its base URL."""
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
    assert server.started, "uvicorn did not start"
    try:
        yield f"https://localhost:{settings.port}"
    finally:
        server.should_exit = True
        thread.join(10)


def _client_context(ca: Path, pair: tuple[Path, Path] | None) -> ssl.SSLContext:
    """Builds a client context that trusts `ca` and presents `pair` when given."""
    context = ssl.create_default_context(cafile=str(ca))
    if pair is not None:
        context.load_cert_chain(certfile=str(pair[0]), keyfile=str(pair[1]))
    return context


def test_the_generated_certificates_complete_a_real_mtls_handshake(tmp_path: Path, fake_vault: FakeDiagnos) -> None:
    """The client pair gets a 200; no certificate, or one from a stranger CA, never reaches a route."""
    written = dev_certs.generate(tmp_path / "certs")
    stranger = dev_certs.generate(tmp_path / "stranger")
    settings = ApiSettings.from_env({**written.environment(), "DIAGNOS_API_PORT": str(_free_port())})

    with _serving(settings, fake_vault) as url:
        ok = httpx.get(f"{url}/healthz", verify=_client_context(written.ca, (written.client, written.client_key)))
        assert (ok.status_code, ok.json()) == (200, {"status": "ok"})
        for pair in (None, (stranger.client, stranger.client_key)):
            with pytest.raises((httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError)):
                httpx.get(f"{url}/healthz", verify=_client_context(written.ca, pair))
