"""🇺🇸 The sandbox every runnable doc snippet runs in: the real SDK, an in-memory vault, nothing else faked.

`from diagnos import Diagnos; Diagnos()` inside a snippet is the real class
doing the real work — token parsing, the session opened with the token's
hybrid signature, sealing and opening every record and file in the Rust
enclave. Only the network is replaced: the two `httpx` clients
`VaultTransport` would open are swapped for `httpx.MockTransport`s that
answer from `FakeVault`, the SDK's own test double of the vault and R2
(`apps/sdk/tests/resources/vault_double/`), plus the token's session and
lock routes, where the session and the keys of the groups `sg_oncology`
and `sg_radiology` are sealed to the token for real.

The working directory is a fresh temporary folder holding the files the
guides upload (`FIXTURES`), the environment carries a sandbox
`DIAGNOS_TOKEN` (all-zero key id and seed: obviously not a secret), and the
system keyring is out of reach — so a snippet reads exactly like production
code and never touches the machine's own token.

🇧🇷 O sandbox em que todo snippet executável da doc roda: o SDK de verdade, um cofre em memória, nada mais falso.

`from diagnos import Diagnos; Diagnos()` dentro de um snippet é a classe de
verdade fazendo o trabalho de verdade — leitura do token, a sessão aberta com
a assinatura híbrida do token, selar e abrir todo registro e arquivo no
enclave Rust. Só a rede é trocada: os dois clients `httpx` que o
`VaultTransport` abriria viram `httpx.MockTransport`s que respondem a partir
do `FakeVault`, o duplo de teste do próprio SDK para o cofre e o R2
(`apps/sdk/tests/resources/vault_double/`), mais as rotas de sessão e de
lock do token, onde a sessão e as chaves dos grupos `sg_oncology` e
`sg_radiology` são seladas para o token de verdade.

O diretório de trabalho é uma pasta temporária nova com os arquivos que os
guias sobem (`FIXTURES`), o ambiente carrega um `DIAGNOS_TOKEN` de sandbox
(id de chave e semente todos zero: obviamente não é segredo), e o chaveiro do
sistema fica fora de alcance — então um snippet se lê exatamente como código
de produção e nunca toca o token da própria máquina.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import secrets
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import httpx

import diagnos.client
from diagnos.crypto.hybrid import seal_hybrid
from diagnos.crypto.secure import SecretBox
from diagnos.crypto.token_keys import encode_token
from diagnos.session.token_session import group_key_aad, lock_path, session_aad, session_path
from diagnos.transport.http import VaultTransport
from diagnos.transport.service_token import DiagnosToken

from .output import REPO_ROOT

# 🇺🇸 The SDK's vault double lives with its tests, outside any package; this is the one place that reaches it.
# 🇧🇷 O duplo do cofre do SDK mora com os testes, fora de pacote; este é o único lugar que o alcança.
sys.path.insert(0, str(REPO_ROOT / "apps" / "sdk" / "tests" / "resources"))
from vault_double import VAULT_URL, WORKSPACE_ID, FakeVault  # noqa: E402

GRANTED_GROUPS = ("sg_oncology", "sg_radiology")
FIXTURES: dict[str, bytes] = {
    "scans/IM-0001.dcm": b"DICM" + bytes(128),
    "scans/IM-0002.dcm": b"DICM" + bytes(256),
    "photo.jpg": b"\xff\xd8\xff\xe0" + bytes(64),
    "report.pdf": b"%PDF-1.7\n" + bytes(64),
}
_SESSION_SECONDS = 3600


def _b64url(data: bytes) -> str:
    """🇺🇸 Unpadded base64url (`docs/PROTOCOL.md §0`). 🇧🇷 base64url sem padding (`docs/PROTOCOL.md §0`)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    """🇺🇸 The inverse of `_b64url`. 🇧🇷 O inverso de `_b64url`."""
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sandbox_token() -> str:
    """🇺🇸 A `DIAGNOS_TOKEN` for the double's workspace: all-zero key id and seed, obviously fake, signed for real.

    🇧🇷 Um `DIAGNOS_TOKEN` para o workspace do duplo: id e semente todos zero, obviamente falso, assinado de verdade.
    """
    return encode_token(f"svc_{'0' * 32}", SecretBox.from_bytes(bytearray(32)), WORKSPACE_ID)


def _envelope(result: object, status: int = 200) -> httpx.Response:
    """🇺🇸 A `success: true` envelope (`docs/PROTOCOL.md §0`). 🇧🇷 Um envelope `success: true`."""
    body = {"success": True, "status": "success", "status_code": status, "result": result, "docs": "sandbox"}
    return httpx.Response(status, json=body)


class SandboxVault:
    """🇺🇸 `FakeVault` plus the token's session: sealed to the sandbox token's own keys, every time it is asked.

    🇧🇷 `FakeVault` mais a sessão do token: selada para as chaves do próprio token do sandbox, a cada pedido.
    """

    def __init__(self) -> None:
        """🇺🇸 An empty workspace with two granted groups. 🇧🇷 Um workspace vazio com dois grupos concedidos."""
        self.documents = FakeVault()
        self.group_keys = {group: secrets.token_bytes(32) for group in GRANTED_GROUPS}
        token = DiagnosToken.parse(sandbox_token(), source="sandbox")
        keys = token.public_keys
        self._key_id = token.key_id
        self._recipient = (_b64url_decode(keys["x25519"]), _b64url_decode(keys["ml_kem_768"]))
        token.wipe()

    def handle_api(self, request: httpx.Request) -> httpx.Response:
        """🇺🇸 Session and lock here; the rest goes to `FakeVault`. 🇧🇷 Sessão e lock aqui; o resto, ao duplo."""
        path = request.url.path
        if request.method == "POST" and path == session_path(WORKSPACE_ID):
            return self._session()
        if request.method == "POST" and path == lock_path(WORKSPACE_ID):
            return _envelope({"revoked": True})
        return self.documents.handle_api(request)

    def _session(self) -> httpx.Response:
        """🇺🇸 `POST …/session`: a fresh session and the group keys, sealed with the reference's AADs.

        🇧🇷 `POST …/session`: uma sessão nova e as chaves de grupo, seladas com os AADs da referência.
        """
        expires_at = int(time.time()) + _SESSION_SECONDS
        session = {
            "session_id": f"ses_{secrets.token_hex(4)}",
            "sign_key": _b64url(secrets.token_bytes(32)),
            "enc_key": _b64url(secrets.token_bytes(32)),
            "expires_at": expires_at,
        }
        x25519, mlkem768 = self._recipient
        aad = session_aad(WORKSPACE_ID, self._key_id)
        sealed_groups = {
            group: seal_hybrid(x25519, mlkem768, key, group_key_aad(WORKSPACE_ID, self._key_id, group)).to_dict()
            for group, key in self.group_keys.items()
        }
        result = {
            "session_id": session["session_id"],
            "expires_at": expires_at,
            "sealed_session": seal_hybrid(x25519, mlkem768, json.dumps(session).encode(), aad).to_dict(),
            "sealed_group_keys": sealed_groups,
        }
        return _envelope(result, status=201)


def _transport_factory(vault: SandboxVault) -> Any:
    """🇺🇸 Stands in for `VaultTransport` inside `diagnos.client`: the real class, mock clients injected.

    🇧🇷 Substitui `VaultTransport` dentro de `diagnos.client`: a classe de verdade, com clients falsos injetados.
    """

    def build(*args: Any, **kwargs: Any) -> VaultTransport:
        """🇺🇸 What `Diagnos` passes, plus the two mock clients. 🇧🇷 O que o `Diagnos` passa, mais os dois clients."""
        api = httpx.Client(transport=httpx.MockTransport(vault.handle_api), base_url=VAULT_URL)
        storage = httpx.Client(transport=httpx.MockTransport(vault.documents.handle_storage))
        return VaultTransport(*args, client=api, storage_client=storage, **kwargs)

    return build


def _no_keyring() -> object:
    """🇺🇸 `keyring`'s "no keyring": a snippet never reads the machine's own token. 🇧🇷 Nunca o token da máquina."""
    from keyring.backends import fail

    return fail.Keyring()  # type: ignore[no-untyped-call]


@contextlib.contextmanager
def sandbox() -> Iterator[SandboxVault]:
    """🇺🇸 Everything a snippet needs, undone on exit: environment, working directory, the patched transport.

    `DIAGNOS_HARDEN_PROCESS=0` keeps the checking process debuggable: the
    hardening itself is the enclave's business, not the docs'.

    🇧🇷 Tudo que um snippet precisa, desfeito na saída: ambiente, diretório de trabalho, o transporte trocado.

    `DIAGNOS_HARDEN_PROCESS=0` mantém o processo que checa depurável: o
    hardening em si é assunto do enclave, não da doc.
    """
    vault = SandboxVault()
    with (
        tempfile.TemporaryDirectory(prefix="diagnos-docs-") as workdir,
        mock.patch.dict(os.environ),
        mock.patch.object(diagnos.client, "VaultTransport", _transport_factory(vault)),
        mock.patch("keyring.get_keyring", _no_keyring),
    ):
        for key in [key for key in os.environ if key.startswith(("DIAGNOS_", "OPENBAO_"))]:
            del os.environ[key]
        os.environ.update(
            {"DIAGNOS_TOKEN": sandbox_token(), "DIAGNOS_VAULT_URL": VAULT_URL, "DIAGNOS_HARDEN_PROCESS": "0"}
        )
        for name, content in FIXTURES.items():
            (Path(workdir) / name).parent.mkdir(parents=True, exist_ok=True)
            (Path(workdir) / name).write_bytes(content)
        with contextlib.chdir(workdir):
            yield vault
