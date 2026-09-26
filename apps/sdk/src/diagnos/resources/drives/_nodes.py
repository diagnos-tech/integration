"""🇺🇸 `_Nodes`: the one engine behind `vault.drives` — every byte of the `/nodes` protocol (`docs/PROTOCOL.md §9`).

It follows the web app's upload pipeline (`@repo/magic-files`) step for
step, so a file the SDK uploads is one the web app and the vault's
processor can open:

- **Keys.** Every node (file or folder) gets its own DEK, wrapped for its
  security group with `imgexam-node-dek-v1`; its name is sealed under that
  DEK with `imgexam-node-name-v1`. The body is sealed under a content key
  derived from the DEK, the node id and the `security_context` the vault
  returns at staging — the same derivation as documents (§7).
- **Body.** libsodium secretstream, 1 MiB chunks, `[len][frame]` framing;
  the declared size is computed before any byte is encrypted.
- **SSE-C.** R2's second layer uses the content key's *sister*
  (`derive_sse_c_key`), sent on the single `PUT`, on every multipart part
  and on the `GET`, exactly as the web app does.
- **Batches.** Up to 100 files per reservation; small files go up in one
  signed `PUT` and are confirmed together; large ones go up in parts,
  signed in waves of up to 200 as the upload advances.

🇧🇷 `_Nodes`: o único motor por trás de `vault.drives` — todo byte do protocolo `/nodes` (`docs/PROTOCOL.md §9`).

Segue o pipeline de upload do app web (`@repo/magic-files`) passo a passo,
para um arquivo que o SDK sobe ser um que o app web e o processador do
cofre conseguem abrir:

- **Chaves.** Todo nó (arquivo ou pasta) ganha a própria DEK, embrulhada
  para o security group com `imgexam-node-dek-v1`; o nome é selado sob
  essa DEK com `imgexam-node-name-v1`. O corpo é selado sob uma chave de
  conteúdo derivada da DEK, do id do nó e do `security_context` que o
  cofre devolve na reserva — a mesma derivação dos documentos (§7).
- **Corpo.** secretstream da libsodium, chunks de 1 MiB, enquadramento
  `[len][frame]`; o tamanho declarado é calculado antes de cifrar um byte.
- **SSE-C.** A segunda camada do R2 usa a *irmã* da chave de conteúdo
  (`derive_sse_c_key`), mandada no `PUT` único, em toda parte de multipart
  e no `GET`, exatamente como o app web faz.
- **Lotes.** Até 100 arquivos por reserva; arquivos pequenos sobem num
  `PUT` assinado e são confirmados juntos; os grandes sobem por partes,
  assinadas em ondas de até 200 conforme o upload avança.
"""

from __future__ import annotations

import builtins
import os
import uuid
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Final

from diagnos.crypto import (
    NODE_DEK_INFO,
    NODE_NAME_INFO,
    EntropyMixer,
    SecretBox,
    decrypt_content,
    decrypt_stream,
    derive_content_key,
    derive_sse_c_key,
    encrypt_content,
    encrypt_stream,
    encrypted_size,
    generate_dek,
    sse_c_headers,
    unwrap_key,
    wrap_key,
)
from diagnos.errors import ConflictError, CryptoError, ProtocolError
from diagnos.models import DriveNode, Page, StagedNode
from diagnos.session.keyring import Keyring

from ._source import UploadSource, _plaintext_source, _PlaintextSource

if TYPE_CHECKING:
    from diagnos.transport.http import VaultTransport

# 🇺🇸 The vault's own limits (`services/uploads/policy.ts`, §13).
# 🇧🇷 Os limites do próprio cofre (`services/uploads/policy.ts`, §13).
MAX_FILES_PER_BATCH: Final[int] = 100
MAX_IDS_PER_COMPLETE_CALL: Final[int] = 200
MAX_PARTS_PER_SIGN_REQUEST: Final[int] = 200
DEFAULT_PAGE_SIZE: Final[int] = 50

UploadInput = UploadSource | str | os.PathLike[str] | bytes | BinaryIO


@dataclass
class _PreparedUpload:
    """🇺🇸 One file, ready to stage: its plaintext, its fresh DEK and everything the reservation carries.

    🇧🇷 Um arquivo, pronto para a reserva: o texto claro, a DEK nova e tudo o que a reserva leva.
    """

    client_ref: str
    plaintext: _PlaintextSource
    dek: SecretBox
    stage_entry: dict[str, Any]

    @property
    def encrypted_bytes(self) -> int:
        """🇺🇸 The size declared at staging (the sealed, framed body). 🇧🇷 O tamanho declarado na reserva."""
        return int(self.stage_entry["size"])


def _group_into_parts(chunks: Iterable[bytes], part_size: int) -> Iterator[tuple[int, bytes]]:
    """🇺🇸 Cuts the framed ciphertext into fixed-size multipart parts, 1-indexed — a cut, not a second encryption.

    🇧🇷 Corta o ciphertext enquadrado em partes de multipart de tamanho fixo, a partir de 1 — um corte, não
    outra cifragem.
    """
    buffer = bytearray()
    part_number = 1
    for chunk in chunks:
        buffer.extend(chunk)
        while len(buffer) >= part_size:
            yield part_number, bytes(buffer[:part_size])
            del buffer[:part_size]
            part_number += 1
    if buffer:
        yield part_number, bytes(buffer)


class _Nodes:
    """🇺🇸 The `/nodes` routes of one workspace: list, read, name, download, upload, folders.

    🇧🇷 As rotas `/nodes` de um workspace: listar, ler, nomear, baixar, subir, pastas.
    """

    def __init__(
        self,
        transport: VaultTransport,
        keyring_provider: Callable[[], Keyring],
        entropy: EntropyMixer,
        *,
        workspace_id: str,
    ) -> None:
        """🇺🇸 `keyring_provider` is asked fresh on every call, like `VersionedDocuments`.

        🇧🇷 `keyring_provider` é consultado a cada chamada, como em `VersionedDocuments`.
        """
        self._transport = transport
        self._keyring_provider = keyring_provider
        self._entropy = entropy
        self._base = f"/api/external/v1/workspaces/{workspace_id}/nodes"

    # -- reading -------------------------------------------------------------

    def list(
        self,
        *,
        security_group: str | None = None,
        exam_id: str | None = None,
        parent_id: str | None = None,
        include_pending: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> Page[DriveNode]:
        """🇺🇸 One page of nodes (`GET /nodes`), filtered by group, exam and/or folder.

        🇧🇷 Uma página de nós (`GET /nodes`), filtrada por grupo, exame e/ou pasta.
        """
        # 🇺🇸 Asking for the keyring unlocks lazily; a signed request cannot go out before there is a session.
        # 🇧🇷 Pedir o keyring desbloqueia de forma preguiçosa; uma requisição assinada não sai antes de existir sessão.
        self._keyring_provider()
        query: dict[str, str | int | bool] = {"limit": limit}
        for name, value in (("security_group_id", security_group), ("exam_id", exam_id), ("parent_id", parent_id)):
            if value is not None:
                query[name] = value
        if include_pending:
            query["include_pending"] = "true"
        if cursor is not None:
            query["cursor"] = cursor
        result = self._transport.get(self._base, query=query)
        return Page(
            items=[DriveNode.model_validate(node) for node in result["items"]], next_cursor=result["next_cursor"]
        )

    def iter_all(self, **filters: Any) -> Iterator[DriveNode]:
        """🇺🇸 Walks every page of `list(**filters)`. 🇧🇷 Percorre toda página de `list(**filters)`."""
        cursor: str | None = None
        while True:
            page = self.list(**filters, cursor=cursor)
            yield from page.items
            if page.next_cursor is None:
                return
            cursor = page.next_cursor

    def get(self, node_id: str) -> DriveNode:
        """🇺🇸 One ready file's index (`GET /nodes/{id}`); folders and unfinished uploads answer `404`.

        🇧🇷 O índice de um arquivo pronto (`GET /nodes/{id}`); pastas e uploads inacabados respondem `404`.
        """
        self._keyring_provider()  # 🇺🇸 lazy unlock before signing (see `list`) 🇧🇷 unlock preguiçoso antes de assinar
        result = self._transport.get(f"{self._base}/{node_id}")
        return DriveNode.model_validate(result["node"])

    def node_dek(self, node: DriveNode) -> SecretBox:
        """🇺🇸 Unwraps the node's own DEK with the key of its security group.

        🇧🇷 Desembrulha a DEK do próprio nó com a chave do security group dele.
        """
        wrapped = node.encrypted_keys.get(node.security_group_id)
        if wrapped is None:
            raise CryptoError(
                f"🇺🇸 node {node.node_id!r} has no DEK sealed for its own security group {node.security_group_id!r}. "
                f"🇧🇷 o nó {node.node_id!r} não tem DEK selada para o próprio security group {node.security_group_id!r}."
            )
        group_key = self._keyring_provider().group_key(node.security_group_id)
        return unwrap_key(group_key, wrapped, NODE_DEK_INFO)

    def name_of(self, node: DriveNode) -> str:
        """🇺🇸 Opens the node's sealed name. 🇧🇷 Abre o nome selado do nó."""
        return decrypt_content(self.node_dek(node), node.encrypted_name, NODE_NAME_INFO).decode("utf-8")

    def iter_download(self, node_id: str) -> Iterator[bytes]:
        """🇺🇸 Downloads and decrypts one file lazily, a plaintext chunk at a time.

        Nothing larger than one frame is held in memory, and the first bytes
        reach the caller before the last ones leave storage.

        🇧🇷 Baixa e decifra um arquivo preguiçosamente, um pedaço de texto claro por vez.

        Nada maior que um frame fica em memória, e os primeiros bytes chegam
        a quem chama antes de os últimos saírem do armazenamento.
        """
        self._keyring_provider()  # 🇺🇸 lazy unlock before signing (see `list`) 🇧🇷 unlock preguiçoso antes de assinar
        result = self._transport.get(f"{self._base}/{node_id}")
        node = DriveNode.model_validate(result["node"])
        context = str(result["security_context"]["value"])
        dek = self.node_dek(node)
        download = result["download"]
        headers = {str(k): str(v) for k, v in (download.get("headers") or {}).items()}
        headers.update(sse_c_headers(derive_sse_c_key(dek, node.node_id, context)))
        cipher_stream = self._transport.download_stream(download["url"], headers=headers)
        yield from decrypt_stream(derive_content_key(dek, node.node_id, context), cipher_stream)

    def download(self, node_id: str, destination: str | os.PathLike[str] | BinaryIO | None = None) -> bytes | None:
        """🇺🇸 The whole plaintext when `destination` is `None`; else written to it chunk by chunk.

        🇧🇷 O texto claro inteiro quando `destination` é `None`; senão escrito nele pedaço a pedaço.
        """
        chunks = self.iter_download(node_id)
        if destination is None:
            return b"".join(chunks)
        if isinstance(destination, (str, os.PathLike)):
            with Path(destination).open("wb") as handle:
                for chunk in chunks:
                    handle.write(chunk)
            return None
        for chunk in chunks:
            destination.write(chunk)
        return None

    # -- writing -------------------------------------------------------------

    def _seal_node(self, group_key: SecretBox, security_group: str, name: str) -> tuple[SecretBox, dict[str, Any]]:
        """🇺🇸 A fresh node DEK plus the sealed name and wrapped key every stage entry carries.

        🇧🇷 Uma DEK de nó nova mais o nome selado e a chave embrulhada que toda entrada de reserva leva.
        """
        dek = generate_dek(self._entropy)
        entry = {
            "client_ref": uuid.uuid4().hex,
            "encrypted_name": encrypt_content(dek, name.encode("utf-8"), NODE_NAME_INFO).to_dict(),
            "encrypted_keys": {security_group: wrap_key(group_key, dek, NODE_DEK_INFO).to_dict()},
        }
        return dek, entry

    def _stage(self, body: dict[str, Any]) -> builtins.list[StagedNode]:
        """🇺🇸 `POST /nodes/uploads` — one reservation for the whole batch (idempotent per `client_ref`).

        🇧🇷 `POST /nodes/uploads` — uma reserva para o lote inteiro (idempotente por `client_ref`).
        """
        result = self._transport.post(f"{self._base}/uploads", json=body)
        return [StagedNode.model_validate(item) for item in result["items"]]

    def create_folder(self, name: str, *, security_group: str, parent_id: str | None = None) -> str:
        """🇺🇸 Creates a folder (ready at once — it has no content) and returns its node id.

        🇧🇷 Cria uma pasta (pronta na hora — ela não tem conteúdo) e devolve o id do nó.
        """
        group_key = self._keyring_provider().group_key(security_group)
        _dek, entry = self._seal_node(group_key, security_group, name)
        body: dict[str, Any] = {"security_group_id": security_group, "files": [{"kind": "folder", **entry}]}
        if parent_id is not None:
            body["parent_id"] = parent_id
        (staged,) = self._stage(body)
        return staged.node_id

    def upload_many(
        self,
        sources: Iterable[UploadInput],
        *,
        security_group: str,
        exam_id: str | None = None,
        parent_id: str | None = None,
    ) -> builtins.list[DriveNode]:
        """🇺🇸 Uploads every source, in reservations of up to 100, and returns the ready nodes in input order.

        🇧🇷 Sobe toda fonte, em reservas de até 100, e devolve os nós prontos na ordem de entrada.
        """
        items = [item if isinstance(item, UploadSource) else UploadSource(item) for item in sources]
        group_key = self._keyring_provider().group_key(security_group)
        nodes: builtins.list[DriveNode] = []
        for start in range(0, len(items), MAX_FILES_PER_BATCH):
            batch = items[start : start + MAX_FILES_PER_BATCH]
            nodes.extend(self._upload_batch(batch, group_key, security_group, exam_id, parent_id))
        return nodes

    def _prepare(self, item: UploadSource, group_key: SecretBox, security_group: str) -> _PreparedUpload:
        """🇺🇸 Names the file, measures it, and seals what the reservation needs.

        🇧🇷 Nomeia o arquivo, mede-o, e sela o que a reserva precisa.
        """
        name = item.resolved_name()
        plaintext = _plaintext_source(item.source)
        dek, entry = self._seal_node(group_key, security_group, name)
        entry["size"] = encrypted_size(plaintext.size)
        mime_type = item.resolved_mime_type(name)
        if mime_type:
            entry["mime_type"] = mime_type
        return _PreparedUpload(client_ref=entry["client_ref"], plaintext=plaintext, dek=dek, stage_entry=entry)

    def _upload_batch(
        self,
        batch: builtins.list[UploadSource],
        group_key: SecretBox,
        security_group: str,
        exam_id: str | None,
        parent_id: str | None,
    ) -> builtins.list[DriveNode]:
        """🇺🇸 Stage → upload each file → confirm the single `PUT`s together.

        🇧🇷 Reservar → subir cada arquivo → confirmar os `PUT`s únicos juntos.
        """
        prepared = [self._prepare(item, group_key, security_group) for item in batch]
        try:
            body: dict[str, Any] = {
                "security_group_id": security_group,
                "files": [upload.stage_entry for upload in prepared],
            }
            if exam_id is not None:
                body["exam_id"] = exam_id
            if parent_id is not None:
                body["parent_id"] = parent_id
            staged = {node.client_ref: node for node in self._stage(body)}
            finished: dict[str, DriveNode] = {}
            singles: builtins.list[str] = []
            for upload in prepared:
                node = staged.get(upload.client_ref)
                if node is None or node.kind != "file":
                    raise ProtocolError(
                        f"🇺🇸 the reservation did not return a file node for {upload.client_ref!r}. "
                        f"🇧🇷 a reserva não devolveu um nó de arquivo para {upload.client_ref!r}."
                    )
                if node.mode == "single":
                    self._put_single(node, upload)
                    singles.append(node.node_id)
                elif node.mode == "multipart":
                    finished[node.node_id] = self._put_multipart(node, upload)
                else:
                    raise ProtocolError(
                        f"🇺🇸 unknown upload mode {node.mode!r}. 🇧🇷 modo de upload desconhecido {node.mode!r}."
                    )
            finished.update(self._complete_singles(singles))
            # 🇺🇸 A confirmed node the vault did not echo back is fetched, never assumed.
            # 🇧🇷 Um nó confirmado que o cofre não ecoou é buscado, nunca presumido.
            node_ids = [staged[upload.client_ref].node_id for upload in prepared]
            return [finished[node_id] if node_id in finished else self.get(node_id) for node_id in node_ids]
        finally:
            for upload in prepared:
                upload.plaintext.cleanup()

    def _keys(self, node: StagedNode, upload: _PreparedUpload) -> tuple[SecretBox, dict[str, str]]:
        """🇺🇸 The content key and the SSE-C headers for one staged node.

        🇧🇷 A chave de conteúdo e os headers de SSE-C de um nó reservado.
        """
        context = node.security_context.value
        content_key = derive_content_key(upload.dek, node.version_id, context)
        return content_key, sse_c_headers(derive_sse_c_key(upload.dek, node.version_id, context))

    def _put_single(self, node: StagedNode, upload: _PreparedUpload) -> None:
        """🇺🇸 Seals the whole file and sends it in one signed `PUT` (≤ 64 MiB), with the SSE-C headers.

        🇧🇷 Sela o arquivo inteiro e o manda num `PUT` assinado (≤ 64 MiB), com os headers de SSE-C.
        """
        if node.upload is None:
            raise ProtocolError(
                f"🇺🇸 single-mode node {node.node_id!r} came without an upload URL. "
                f"🇧🇷 o nó single {node.node_id!r} veio sem URL de upload."
            )
        content_key, sse = self._keys(node, upload)
        with upload.plaintext.open() as handle:
            body = b"".join(encrypt_stream(content_key, handle))
        headers = {str(k): str(v) for k, v in (node.upload.get("headers") or {}).items()}
        declared = headers.get("content-length")
        if len(body) != upload.encrypted_bytes or (declared is not None and int(declared) != len(body)):
            raise ProtocolError(
                f"🇺🇸 sealed {len(body)} bytes for node {node.node_id!r}, signed for {declared}. "
                f"🇧🇷 selados {len(body)} bytes para o nó {node.node_id!r}, assinado para {declared}."
            )
        self._transport.upload_bytes(node.upload["url"], body, {**headers, **sse})

    def _sign_parts(self, node_id: str, part_numbers: builtins.list[int]) -> dict[int, str]:
        """🇺🇸 `POST /nodes/{id}/multipart/parts` for up to 200 part numbers. 🇧🇷 Assina até 200 partes."""
        result = self._transport.post(f"{self._base}/{node_id}/multipart/parts", json={"part_numbers": part_numbers})
        return {int(part["part_number"]): str(part["url"]) for part in result["parts"]}

    def _put_multipart(self, node: StagedNode, upload: _PreparedUpload) -> DriveNode:
        """🇺🇸 Streams the sealed body up in parts, signing URLs in waves, then completes; aborts on failure.

        The reservation usually opens the multipart upload already
        (`upload_id`); only when it did not does the SDK call the recovery
        route. Parts are signed in waves as the upload advances, so a long
        upload never uses a URL signed long before. On any failure the
        upload is aborted, so the vault releases the reserved bytes at once.

        🇧🇷 Sobe o corpo selado por partes, assinando URLs em ondas, depois conclui; aborta em caso de falha.

        A reserva em geral já abre o upload multipart (`upload_id`); só
        quando não abriu o SDK chama a rota de recuperação. As partes são
        assinadas em ondas conforme o upload avança, então um upload longo
        nunca usa uma URL assinada muito antes. Em qualquer falha o upload é
        abortado, para o cofre liberar os bytes reservados na hora.
        """
        part_size = node.part_size
        if node.upload_id is None or part_size is None:
            started = self._transport.post(f"{self._base}/{node.node_id}/multipart")
            part_size = int(started["part_size"])
        part_count = -(-upload.encrypted_bytes // part_size)
        content_key, sse = self._keys(node, upload)
        try:
            urls: dict[int, str] = {}
            parts: builtins.list[dict[str, Any]] = []
            with upload.plaintext.open() as handle:
                for part_number, chunk in _group_into_parts(encrypt_stream(content_key, handle), part_size):
                    if part_number not in urls:
                        wave = list(range(part_number, min(part_number + MAX_PARTS_PER_SIGN_REQUEST, part_count + 1)))
                        urls.update(self._sign_parts(node.node_id, wave or [part_number]))
                    etag = self._transport.upload_bytes(urls[part_number], chunk, sse)
                    if not etag:
                        raise ProtocolError(
                            f"🇺🇸 storage returned no ETag for part {part_number}. "
                            f"🇧🇷 o armazenamento não devolveu ETag para a parte {part_number}."
                        )
                    parts.append({"part_number": part_number, "etag": etag})
            result = self._transport.post(f"{self._base}/{node.node_id}/multipart/complete", json={"parts": parts})
            return DriveNode.model_validate(result["node"])
        except Exception:
            self._abort(node.node_id)
            raise

    def _abort(self, node_id: str) -> None:
        """🇺🇸 Best-effort `POST /nodes/{id}/multipart/abort`; the vault's sweep covers a lost abort.

        🇧🇷 `POST /nodes/{id}/multipart/abort` best-effort; a varredura do cofre cobre um abort perdido.
        """
        try:
            self._transport.post(f"{self._base}/{node_id}/multipart/abort")
        except Exception:  # noqa: BLE001, S110 — the original failure is the one worth raising
            pass

    def _complete_singles(self, node_ids: builtins.list[str]) -> dict[str, DriveNode]:
        """🇺🇸 `POST /nodes/uploads/complete` in calls of up to 200; a `missing` id means the `PUT` never landed.

        🇧🇷 `POST /nodes/uploads/complete` em chamadas de até 200; um id em `missing` significa que o `PUT` não chegou.
        """
        ready: dict[str, DriveNode] = {}
        for start in range(0, len(node_ids), MAX_IDS_PER_COMPLETE_CALL):
            chunk = node_ids[start : start + MAX_IDS_PER_COMPLETE_CALL]
            result = self._transport.post(f"{self._base}/uploads/complete", json={"node_ids": chunk})
            missing = result.get("missing") or []
            if missing:
                raise ConflictError(
                    code="UploadIncomplete",
                    message=(
                        f"🇺🇸 storage has no object for node(s) {missing!r} — upload them again. "
                        f"🇧🇷 o armazenamento não tem objeto para o(s) nó(s) {missing!r} — suba de novo."
                    ),
                    status=409,
                )
            for raw in result["ready"]:
                node = DriveNode.model_validate(raw)
                ready[node.node_id] = node
        return ready
