"""🇺🇸 Files and folders (`docs/PROTOCOL.md §9`): what the SDK asks of `/nodes`, and reads back.

Each test drives the SDK's real `Drives` against the Pact mock: reserve a
file → `PUT` → confirm, open a ready file and download it, list a group's
files, create a folder. What the SDK opens — a node's wrapped DEK, its sealed
name, its framed body, the SSE-C headers storage demands — is produced here
by an independent implementation (`_crypto.py`: `cryptography` and
libsodium through `pynacl`), cross-checked against vectors the web app's own
code generated (`apps/sdk/tests/vectors/node_content.json`); so a green run
is also proof that the SDK reads what the web app writes, and writes what
the web app reads.

Multipart uploads are not in this contract: the vault opens and closes them
through R2's S3 endpoint, which its provider verification (a local
`wrangler dev`) does not have. The SDK's unit tests cover them against a
double that models those routes (`apps/sdk/tests/resources/vault_double.py`).

🇧🇷 Arquivos e pastas (`docs/PROTOCOL.md §9`): o que o SDK pede a `/nodes`, e o que lê de volta.

Cada teste conduz os `Drives` de verdade do SDK contra o mock do Pact:
reservar um arquivo → `PUT` → confirmar, abrir um arquivo pronto e baixá-lo,
listar os arquivos de um grupo, criar uma pasta. O que o SDK abre — a DEK
embrulhada de um nó, o nome selado, o corpo enquadrado, os headers de SSE-C
que o armazenamento exige — é produzido aqui por uma implementação
independente (`_crypto.py`: `cryptography` e libsodium via `pynacl`),
conferida contra vetores gerados pelo próprio código do app web
(`apps/sdk/tests/vectors/node_content.json`); então uma rodada verde também
prova que o SDK lê o que o app web grava, e grava o que o app web lê.

Uploads multipart não estão neste contrato: o cofre os abre e fecha pelo
endpoint S3 do R2, que a verificação do provider (um `wrangler dev` local)
não tem. Os testes unitários do SDK os cobrem contra um dublê que modela
essas rotas (`apps/sdk/tests/resources/vault_double.py`).
"""

from __future__ import annotations

import types
import uuid
from typing import Any

import httpx
import pytest
from diagnos.crypto import EntropyMixer
from diagnos.crypto.secure import SecretBox
from diagnos.resources.drives import Drives
from diagnos.resources.drives import _nodes as nodes_module
from diagnos.session.keyring import Keyring
from pact import Pact, generate, match
from pact.match.matcher import GenericMatcher

from _crypto import (
    NODE_DEK_INFO,
    NODE_NAME_INFO,
    b64url,
    content_key,
    fixed_bytes,
    open_stream,
    seal_content,
    seal_stream,
    sse_c_headers,
)
from _wire import (
    ACCOUNT_ID,
    B64URL,
    EXTERNAL_PREFIX,
    HTTPS_URL,
    SECURITY_GROUP_ID,
    WORKSPACE_ID,
    declare_clock,
    encrypted,
    instant,
    literal,
    ok,
    path,
    session_keys,
    signed_headers,
    workspace_state,
)
from conftest import make_transport

GROUP_KEY = fixed_bytes("group/dek")
NODE_DEK = fixed_bytes("node/dek")
UPLOAD_DEK = fixed_bytes("node/upload-dek")
NODE_ID = "node-contract"
FOLDER_ID = "folder-contract"
EXAM_ID = "exam-contract"
CLIENT_REF = uuid.UUID(bytes=fixed_bytes("node/client-ref", 16)).hex
CONTEXT = b64url(fixed_bytes("node/security-context"))
CREATED_AT = "2026-09-01T12:00:00.000Z"
UPLOAD_URL = "https://objects.diagnos.test/node-upload?X-Amz-Signature=contract"
DOWNLOAD_URL = "https://objects.diagnos.test/node-download?X-Amz-Signature=contract"

FILE_NAME = "IM-0001-0001.dcm"
DICOM_MIME = "application/dicom"
# 🇺🇸 A DICOM preamble is 128 zero bytes then `DICM` — enough to look like one, small enough for one frame.
# 🇧🇷 Um preâmbulo DICOM são 128 bytes zero e `DICM` — o bastante para parecer um, pequeno para caber num frame.
PLAINTEXT = bytes(128) + b"DICM" + b"\x02\x00\x00\x00contract"
# 🇺🇸 `header(24) + one final frame (len 4 + tag 17) + plaintext` — `docs/PROTOCOL.md §9`.
# 🇧🇷 `header(24) + um frame final (len 4 + tag 17) + texto claro` — `docs/PROTOCOL.md §9`.
SEALED_SIZE = 24 + 4 + 17 + len(PLAINTEXT)

_WS = rf"^{EXTERNAL_PREFIX}/workspaces/[^/]+"
_WS_EXPR = f"{EXTERNAL_PREFIX}/workspaces/${{workspace_id}}"
_BASE = f"{EXTERNAL_PREFIX}/workspaces/{WORKSPACE_ID}/nodes"
_CLIENT_REF = r"^[A-Za-z0-9_-]{1,64}$"


def _nodes_path(suffix: str = "") -> Any:
    """🇺🇸 `…/nodes{suffix}` under the provider's workspace. 🇧🇷 `…/nodes{suffix}` sob o workspace do provider."""
    return path(f"{_BASE}{suffix}", pattern=rf"{_WS}/nodes{suffix}$", expression=f"{_WS_EXPR}/nodes{suffix}")


def _from_state(example: str, name: str) -> GenericMatcher[str]:
    """🇺🇸 A body value the vault's state handler supplies at verification (`${name}`); any string here.

    🇧🇷 Um valor de corpo que o state handler do cofre fornece na verificação (`${name}`); qualquer string aqui.
    """
    return GenericMatcher("type", value=example, generator=generate.provider_state(f"${{{name}}}"))


def _wrapped_dek() -> dict[str, str]:
    """🇺🇸 `NODE_DEK` wrapped for the group, as the web app does. 🇧🇷 `NODE_DEK` embrulhada para o grupo."""
    return seal_content(GROUP_KEY, NODE_DEK, NODE_DEK_INFO, label="node/wrapped-dek")


def _sealed_name() -> dict[str, str]:
    """🇺🇸 `FILE_NAME` sealed under `NODE_DEK`. 🇧🇷 `FILE_NAME` selado sob `NODE_DEK`."""
    return seal_content(NODE_DEK, FILE_NAME.encode("utf-8"), NODE_NAME_INFO, label="node/name")


def _ready_file() -> dict[str, object]:
    """🇺🇸 A ready file as the SDK reads it: identity, state, size, type, sealed name and key.

    🇧🇷 Um arquivo pronto como o SDK o lê: identidade, estado, tamanho, tipo, nome e chave selados.
    """
    return {
        "node_id": match.str(NODE_ID),
        "workspace_id": match.str(WORKSPACE_ID),
        "security_group_id": match.str(SECURITY_GROUP_ID),
        "kind": literal("file"),
        "status": literal("ready"),
        "mode": literal("single"),
        "size": match.int(SEALED_SIZE),
        "mime_type": match.str(DICOM_MIME),
        "encrypted_name": encrypted(_sealed_name()),
        "encrypted_keys": match.each_value_matches(
            {SECURITY_GROUP_ID: _wrapped_dek()}, rules=match.like({"salt": "s", "nonce": "n", "ciphertext": "c"})
        ),
        "created_by": match.str(ACCOUNT_ID),
        "created_at": instant(CREATED_AT),
        "is_deleted": match.bool(False),
    }


def _stage_entry(**fields: object) -> dict[str, object]:
    """🇺🇸 What every stage entry carries: an idempotency ref, the sealed name, the wrapped DEK.

    🇧🇷 O que toda entrada de reserva leva: uma ref de idempotência, o nome selado, a DEK embrulhada.
    """
    return {
        "client_ref": match.regex(CLIENT_REF, regex=_CLIENT_REF),
        "encrypted_name": encrypted(_sealed_name()),
        "encrypted_keys": {SECURITY_GROUP_ID: encrypted(_wrapped_dek())},
        **fields,
    }


def _keyring() -> Keyring:
    """🇺🇸 The session plus the contract's group key. 🇧🇷 A sessão mais a chave de grupo do contrato."""
    return Keyring(
        enrollment_id="enr-contract",
        session=session_keys(),
        group_keys={SECURITY_GROUP_ID: SecretBox.from_bytes(bytearray(GROUP_KEY))},
    )


def _drives(url: str, storage: Any) -> Drives:
    """🇺🇸 `vault.drives` over the mock server. 🇧🇷 `vault.drives` sobre o mock."""
    return Drives(make_transport(url, storage=storage), _keyring, EntropyMixer(), workspace_id=WORKSPACE_ID)


@pytest.fixture
def fixed_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    """🇺🇸 Pins the SDK's `client_ref` (and, for uploads, its DEK) so the mock's canned answer matches them.

    The vault echoes each `client_ref` back and the SDK matches its files by
    it; a mock cannot echo, so the SDK must draw the ref the example
    carries. The fixed DEK lets the oracle open what the SDK uploaded.

    🇧🇷 Fixa o `client_ref` do SDK (e, em uploads, a DEK) para a resposta pronta do mock bater com eles.

    O cofre ecoa cada `client_ref` e o SDK casa os arquivos por ele; um mock
    não ecoa, então o SDK precisa sortear a ref que o exemplo leva. A DEK
    fixa deixa o oráculo abrir o que o SDK subiu.
    """
    monkeypatch.setattr(nodes_module, "uuid", types.SimpleNamespace(uuid4=lambda: uuid.UUID(hex=CLIENT_REF)))
    monkeypatch.setattr(nodes_module, "generate_dek", lambda entropy: SecretBox.from_bytes(bytearray(UPLOAD_DEK)))


class _Storage:
    """🇺🇸 In-memory R2 that enforces SSE-C: every call must carry the node's sister key.

    🇧🇷 R2 em memória que exige SSE-C: toda chamada precisa levar a chave irmã do nó.
    """

    def __init__(self, dek: bytes, *, body: bytes | None = None) -> None:
        """🇺🇸 `dek` decides the expected SSE-C key; `body` is served on `GET`.

        🇧🇷 `dek` decide a chave SSE-C esperada; `body` é servido no `GET`.
        """
        self.expected_sse = sse_c_headers(dek, NODE_ID, CONTEXT)
        self.body = body
        self.puts: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        """🇺🇸 The `httpx.MockTransport` handler. 🇧🇷 O handler do `httpx.MockTransport`."""
        sent = {name: request.headers.get(name) for name in self.expected_sse}
        assert sent == self.expected_sse, (
            "SSE-C headers differ from the web app's · headers de SSE-C diferem do app web"
        )
        if request.method == "PUT":
            self.puts.append(request)
            return httpx.Response(200, headers={"etag": '"contract"'})
        assert str(request.url) == DOWNLOAD_URL
        return httpx.Response(200, content=self.body)


# -- upload --------------------------------------------------------------------


def test_upload_reserves_puts_and_confirms_one_file(pact: Pact, fixed_refs: None) -> None:
    """🇺🇸 One reservation (sealed name, wrapped DEK, framed size, MIME) → signed `PUT` with SSE-C → confirm.

    🇧🇷 Uma reserva (nome selado, DEK embrulhada, tamanho enquadrado, MIME) → `PUT` assinado com SSE-C → confirmar.
    """
    declare_clock(pact)
    name, params = workspace_state(
        "the SDK session holds the key of a security group", security_group_id=SECURITY_GROUP_ID
    )
    (
        pact.upon_receiving("an SDK process reserves the upload of one file")
        .given(name, params)
        .with_request("POST", _nodes_path("/uploads"))
        .with_headers(signed_headers())
        .with_body(
            {
                "security_group_id": literal(SECURITY_GROUP_ID),
                "exam_id": match.str(EXAM_ID),
                "files": [_stage_entry(size=match.int(SEALED_SIZE), mime_type=literal(DICOM_MIME))],
            },
            content_type="application/json",
        )
        .will_respond_with(201)
        .with_body(
            ok(
                {
                    "items": [
                        {
                            "client_ref": match.str(CLIENT_REF),
                            "node_id": match.str(NODE_ID),
                            "version_id": match.str(NODE_ID),
                            "security_context": {"value": match.regex(CONTEXT, regex=B64URL)},
                            "kind": literal("file"),
                            "mode": literal("single"),
                            "upload": {
                                "url": match.regex(UPLOAD_URL, regex=HTTPS_URL),
                                "headers": {"content-length": match.regex(str(SEALED_SIZE), regex=r"^[1-9][0-9]*$")},
                            },
                        }
                    ]
                }
            ),
            content_type="application/json",
        )
    )
    name, params = workspace_state(
        "a file was uploaded and awaits confirmation", security_group_id=SECURITY_GROUP_ID, node_id=NODE_ID
    )
    (
        pact.upon_receiving("an SDK process confirms the files it uploaded")
        .given(name, params)
        .with_request("POST", _nodes_path("/uploads/complete"))
        .with_headers(signed_headers())
        .with_body({"node_ids": [_from_state(NODE_ID, "node_id")]}, content_type="application/json")
        .will_respond_with(200)
        .with_body(ok({"ready": match.each_like(_ready_file()), "missing": []}), content_type="application/json")
    )
    storage = _Storage(UPLOAD_DEK)

    with pact.serve() as server:
        node = (
            _drives(str(server.url), storage)
            .drive(SECURITY_GROUP_ID)
            .upload(PLAINTEXT, name=FILE_NAME, exam_id=EXAM_ID)
        )

    (put,) = storage.puts
    assert str(put.url) == UPLOAD_URL
    assert put.headers["content-length"] == str(SEALED_SIZE)
    assert open_stream(content_key(UPLOAD_DEK, NODE_ID, CONTEXT), put.content) == PLAINTEXT
    assert node.node_id == NODE_ID
    assert node.status == "ready"


def test_create_folder_reserves_a_folder_node(pact: Pact, fixed_refs: None) -> None:
    """🇺🇸 A folder is a stage entry of `kind: folder`, no size: ready at once, nothing to upload.

    🇧🇷 Uma pasta é uma entrada de reserva `kind: folder`, sem tamanho: pronta na hora, nada a subir.
    """
    declare_clock(pact)
    name, params = workspace_state(
        "the SDK session holds the key of a security group", security_group_id=SECURITY_GROUP_ID
    )
    (
        pact.upon_receiving("an SDK process creates a folder")
        .given(name, params)
        .with_request("POST", _nodes_path("/uploads"))
        .with_headers(signed_headers())
        .with_body(
            {"security_group_id": literal(SECURITY_GROUP_ID), "files": [_stage_entry(kind=literal("folder"))]},
            content_type="application/json",
        )
        .will_respond_with(201)
        .with_body(
            ok(
                {
                    "items": [
                        {
                            "client_ref": match.str(CLIENT_REF),
                            "node_id": match.str(FOLDER_ID),
                            "version_id": match.str(FOLDER_ID),
                            "security_context": {"value": match.regex(CONTEXT, regex=B64URL)},
                            "kind": literal("folder"),
                        }
                    ]
                }
            ),
            content_type="application/json",
        )
    )

    with pact.serve() as server:
        folder_id = _drives(str(server.url), _Storage(UPLOAD_DEK)).drive(SECURITY_GROUP_ID).create_folder("Tomografias")

    assert folder_id == FOLDER_ID


# -- reading -------------------------------------------------------------------


def test_download_opens_what_the_web_app_sealed(pact: Pact) -> None:
    """🇺🇸 Index → DEK (group key) → name; content key and SSE-C sister key (node id, context) → the bytes.

    🇧🇷 Índice → DEK (chave do grupo) → nome; chave de conteúdo e chave irmã SSE-C (id do nó, contexto) → os bytes.
    """
    declare_clock(pact)
    name, params = workspace_state(
        "a security group holds one ready file", security_group_id=SECURITY_GROUP_ID, node_id=NODE_ID
    )
    (
        pact.upon_receiving("an SDK process reads a ready file and its download URL")
        .given(name, params)
        .with_request(
            "GET",
            path(
                f"{_BASE}/{NODE_ID}",
                pattern=rf"{_WS}/nodes/[^/]+$",
                expression=f"{_WS_EXPR}/nodes/${{node_id}}",
            ),
        )
        .with_headers(signed_headers())
        .will_respond_with(200)
        .with_body(
            ok(
                {
                    "node": _ready_file(),
                    "security_context": {"value": match.regex(CONTEXT, regex=B64URL)},
                    "download": {"url": match.regex(DOWNLOAD_URL, regex=HTTPS_URL)},
                }
            ),
            content_type="application/json",
        )
    )
    storage = _Storage(NODE_DEK, body=seal_stream(content_key(NODE_DEK, NODE_ID, CONTEXT), PLAINTEXT))

    with pact.serve() as server:
        drives = _drives(str(server.url), storage)
        content = drives.download(NODE_ID)

    assert content == PLAINTEXT


def test_list_decrypts_each_name(pact: Pact) -> None:
    """🇺🇸 `GET /nodes?security_group_id=…&limit=50` → one page; every name opens with the group key.

    🇧🇷 `GET /nodes?security_group_id=…&limit=50` → uma página; todo nome abre com a chave do grupo.
    """
    declare_clock(pact)
    name, params = workspace_state(
        "a security group holds one ready file", security_group_id=SECURITY_GROUP_ID, node_id=NODE_ID
    )
    (
        pact.upon_receiving("an SDK process lists the files of a security group")
        .given(name, params)
        .with_request("GET", _nodes_path())
        .with_query_parameter("security_group_id", SECURITY_GROUP_ID)
        .with_query_parameter("limit", "50")
        .with_headers(signed_headers())
        .will_respond_with(200)
        .with_body(ok({"items": match.each_like(_ready_file()), "next_cursor": None}), content_type="application/json")
    )

    with pact.serve() as server:
        drives = _drives(str(server.url), _Storage(NODE_DEK))
        page = drives.list(security_group=SECURITY_GROUP_ID)
        names = [drives.name_of(node) for node in page.items]

    assert names == [FILE_NAME]
    assert page.next_cursor is None
