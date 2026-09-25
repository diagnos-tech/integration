"""🇺🇸 `_UploadMixin`: staging, single-`PUT` and multipart upload — the write half of `Drive`.

Its methods take `self: _UploadHost`, a structural `Protocol` naming just
the `Drive` attributes/methods they touch (`_transport`, `_entropy`,
`_base`, `_sse_headers`) — not `self: Drive` itself, because mypy requires
an explicit self-type to be a *supertype* of the defining class, and `Drive`
(which inherits this mixin) is the other way round: a subtype of it.

🇧🇷 `_UploadMixin`: reserva, `PUT` único e upload multipart — a metade de escrita de `Drive`.

Seus métodos recebem `self: _UploadHost`, um `Protocol` estrutural que nomeia
só os atributos/métodos de `Drive` que eles tocam (`_transport`, `_entropy`,
`_base`, `_sse_headers`) — não `self: Drive` em si, porque o mypy exige que
um self-type explícito seja um *supertipo* da classe que o define, e `Drive`
(que herda este mixin) é o contrário disso: um subtipo dele.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any, Protocol

from diagnos.crypto import (
    NODE_NAME_INFO,
    EntropyMixer,
    SecretBox,
    encrypt_bytes,
    encrypt_content,
    encrypt_stream,
    encrypted_size,
)
from diagnos.errors import VaultError
from diagnos.models import UploadedNode

from ._source import UploadSource, _plaintext_source, _PlaintextSource, _PreparedUpload

if TYPE_CHECKING:
    from diagnos.transport.http import VaultTransport

# 🇺🇸 §13: at most 200 part numbers per `multipart/parts` sign call.
# 🇧🇷 §13: no máximo 200 números de parte por chamada de `multipart/parts`.
_MAX_PART_NUMBERS_PER_SIGN_REQUEST = 200


class _UploadHost(Protocol):
    """🇺🇸 What `_UploadMixin` needs from `Drive` — see the module docstring for why this is a `Protocol`.

    🇧🇷 O que `_UploadMixin` precisa de `Drive` — ver a docstring do módulo para o porquê de `Protocol`.
    """

    _transport: VaultTransport
    _entropy: EntropyMixer
    _base: str

    def _sse_headers(self, key: SecretBox) -> dict[str, str]: ...
    def _sign_all_parts(self, node_id: str, part_count: int) -> dict[int, str]: ...


def _group_into_parts(chunks: Iterable[bytes], part_size: int) -> Iterator[tuple[int, bytes]]:
    """🇺🇸 Re-chunks an already-encrypted, framed byte stream into fixed-size multipart parts, 1-indexed.

    `docs/PROTOCOL.md §9`: multipart parts cut the framed `secretstream`
    output at arbitrary byte offsets, unrelated to its internal chunk
    boundaries — this is the cut, not a second encryption step.

    🇧🇷 Re-fatia um stream de bytes já cifrado e framed em partes multipart de tamanho fixo, indexadas a partir de 1.

    `docs/PROTOCOL.md §9`: as partes de multipart cortam a saída framed do
    `secretstream` em offsets de byte arbitrários, sem relação com as
    fronteiras internas dos chunks dele — este é o corte, não uma segunda
    etapa de cifragem.
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


class _UploadMixin:
    """🇺🇸 The upload half of `Drive`: prepare, stage, `PUT` (single or multipart), complete.

    🇧🇷 A metade de upload de `Drive`: preparar, reservar, `PUT` (single ou multipart), completar.
    """

    def _prepare_upload(self: _UploadHost, item: UploadSource, group_dek: SecretBox) -> _PreparedUpload:
        """🇺🇸 Normalizes the source, computes the encrypted size, and wraps the name (if any) under the group DEK.

        `client_ref` only has to be unique within this one batch call — a
        mixer-drawn 8-byte hex string is far cheaper than guaranteeing
        uniqueness some other way, and costs nothing since `EntropyMixer` is
        already on hand.

        🇧🇷 Normaliza a fonte, calcula o tamanho cifrado, e embrulha o nome (se houver) sob a DEK do grupo.

        `client_ref` só precisa ser único dentro deste único lote — uma
        string hex de 8 bytes tirada do misturador é bem mais barata que
        garantir unicidade de outro jeito, e não custa nada já que o
        `EntropyMixer` já está à mão.
        """
        plaintext = _plaintext_source(item.source)
        encrypted_name = encrypt_content(group_dek, item.name.encode("utf-8"), NODE_NAME_INFO) if item.name else None
        return _PreparedUpload(
            client_ref=self._entropy.random(8).hex(),
            plaintext=plaintext,
            encrypted_bytes=encrypted_size(plaintext.size),
            mime_type=item.mime_type,
            encrypted_name=encrypted_name,
        )

    def _stage_batch(self: _UploadHost, prepared: list[_PreparedUpload], exam_id: str | None) -> list[UploadedNode]:
        """🇺🇸 `POST {base}/uploads` — one reservation call for the whole batch.

        🇧🇷 `POST {base}/uploads` — uma única chamada de reserva para o lote inteiro.
        """
        body: dict[str, Any] = {"files": [request.to_stage_file() for request in prepared]}
        if exam_id is not None:
            body["exam_id"] = exam_id
        result = self._transport.post(f"{self._base}/uploads", json=body)
        return [UploadedNode.model_validate(node) for node in result["nodes"]]

    def _put_single(self: _UploadHost, staged: UploadedNode, node_key: SecretBox, plaintext: _PlaintextSource) -> None:
        """🇺🇸 Encrypts the whole file in memory and `PUT`s it in one shot (`docs/PROTOCOL.md §9`, ≤64 MiB).

        🇧🇷 Cifra o arquivo inteiro em memória e faz `PUT` de uma vez (`docs/PROTOCOL.md §9`, ≤64 MiB).
        """
        if staged.upload is None:
            raise VaultError(
                code="UploadPlanMismatch",
                message=f"stage answered mode='single' for node {staged.node_id!r} without an upload URL.",
                status=500,
            )
        with plaintext.open() as handle:
            body = encrypt_bytes(node_key, handle.read())
        headers = {"content-length": str(len(body)), **self._sse_headers(node_key)}
        self._transport.upload_bytes(staged.upload["url"], body, headers)

    def _complete_single(self: _UploadHost, node_ids: list[str]) -> None:
        """🇺🇸 `POST {base}/uploads/complete` — confirms every single-mode node by its real (`head`) size.

        A `node_id` coming back in `missing` means the PUT never actually
        landed in R2 (network drop, revoked signed URL) even though this
        process believes it sent the bytes — that gap is exactly what
        `VaultError(code="UploadIncomplete")` surfaces, instead of returning
        a `DriveNode` for content that is not really there.

        🇧🇷 `POST {base}/uploads/complete` — confirma todo nó single pelo tamanho real (`head`).

        Um `node_id` voltando em `missing` significa que o PUT nunca chegou
        de fato no R2 (queda de rede, URL assinada revogada) mesmo que este
        processo acredite ter mandado os bytes — essa lacuna é exatamente o
        que `VaultError(code="UploadIncomplete")` expõe, em vez de devolver
        um `DriveNode` para um conteúdo que não está realmente lá.
        """
        result = self._transport.post(f"{self._base}/uploads/complete", json={"node_ids": node_ids})
        missing = result.get("missing") or []
        if missing:
            raise VaultError(
                code="UploadIncomplete",
                message=f"objects for node ids {missing!r} never landed in storage.",
                status=409,
            )

    def _sign_all_parts(self: _UploadHost, node_id: str, part_count: int) -> dict[int, str]:
        """🇺🇸 Signs every part URL up front, in batches of ≤200 (`docs/PROTOCOL.md §13`).

        Doing this before the first byte is encrypted, rather than one part
        at a time as `_put_multipart` produces them, means encryption never
        stalls waiting on a signing round trip mid-stream.

        🇧🇷 Assina toda URL de parte de antemão, em lotes de ≤200 (`docs/PROTOCOL.md §13`).

        Fazer isso antes do primeiro byte ser cifrado, em vez de uma parte
        por vez conforme `_put_multipart` as produz, faz a cifragem nunca
        travar esperando uma ida e volta de assinatura no meio do stream.
        """
        urls: dict[int, str] = {}
        part_numbers = list(range(1, part_count + 1))
        parts_path = f"{self._base}/uploads/{node_id}/multipart/parts"
        for start in range(0, len(part_numbers), _MAX_PART_NUMBERS_PER_SIGN_REQUEST):
            batch = part_numbers[start : start + _MAX_PART_NUMBERS_PER_SIGN_REQUEST]
            result = self._transport.post(parts_path, json={"part_numbers": batch})
            for part in result["parts"]:
                urls[part["part_number"]] = part["url"]
        return urls

    def _put_multipart(
        self: _UploadHost, staged: UploadedNode, node_key: SecretBox, plaintext: _PlaintextSource
    ) -> None:
        """🇺🇸 Opens the multipart upload, signs every part, then streams-encrypts and `PUT`s each part on demand.

        Parts are produced lazily from `encrypt_stream` and cut to
        `part_size` by `_group_into_parts` — the whole file is never held in
        memory at once, unlike `_put_single`. SSE-C is never applied here:
        the vault itself creates a multipart upload and must not hold the
        key (`docs/PROTOCOL.md §10`).

        🇧🇷 Abre o upload multipart, assina toda parte, depois cifra em
        stream e faz `PUT` de cada parte sob demanda.

        Partes são produzidas de forma preguiçosa a partir de `encrypt_stream`
        e cortadas em `part_size` por `_group_into_parts` — o arquivo inteiro
        nunca fica todo em memória de uma vez, diferente de `_put_single`.
        SSE-C nunca é aplicado aqui: o próprio cofre cria o upload multipart
        e não pode ficar com a chave (`docs/PROTOCOL.md §10`).
        """
        start = self._transport.post(f"{self._base}/uploads/{staged.node_id}/multipart")
        part_size = int(start["part_size"])
        part_count = int(start["part_count"])
        part_urls = self._sign_all_parts(staged.node_id, part_count)

        completed_parts: list[dict[str, Any]] = []
        with plaintext.open() as handle:
            cipher_stream = encrypt_stream(node_key, handle)
            for part_number, chunk in _group_into_parts(cipher_stream, part_size):
                headers = {"content-length": str(len(chunk))}
                etag = self._transport.upload_bytes(part_urls[part_number], chunk, headers)
                completed_parts.append({"part_number": part_number, "etag": etag})
        complete_path = f"{self._base}/uploads/{staged.node_id}/multipart/complete"
        self._transport.post(complete_path, json={"parts": completed_parts})
