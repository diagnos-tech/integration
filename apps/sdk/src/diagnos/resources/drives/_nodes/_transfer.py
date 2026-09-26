"""🇺🇸 `_Transfer`: the byte-moving primitives — single `PUT`, multipart parts, abort, and batch completion.

Split out of `_writing.py` so that module stays about *what* gets uploaded
(batching, staging, folders) while this one is purely about *how* the sealed
bytes of one already-staged node reach storage.

🇧🇷 `_Transfer`: as primitivas de mover bytes — `PUT` único, partes de multipart, abort e conclusão em lote.

Separado de `_writing.py` para aquele módulo ficar sobre *o que* é
enviado (lote, reserva, pastas) enquanto este é puramente sobre *como* os
bytes selados de um nó já reservado chegam ao armazenamento.
"""

from __future__ import annotations

import builtins
from typing import Any

from diagnos.crypto import SecretBox, derive_content_key, derive_sse_c_key, encrypt_stream, sse_c_headers
from diagnos.errors import ConflictError, ProtocolError
from diagnos.models import DriveNode, StagedNode

from ._base import _NodesBase
from ._support import MAX_IDS_PER_COMPLETE_CALL, MAX_PARTS_PER_SIGN_REQUEST, _group_into_parts, _PreparedUpload


class _Transfer(_NodesBase):
    """🇺🇸 Sends one staged node's sealed body to storage, single or multipart.

    🇧🇷 Manda o corpo selado de um nó reservado ao armazenamento, único ou multipart.
    """

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
