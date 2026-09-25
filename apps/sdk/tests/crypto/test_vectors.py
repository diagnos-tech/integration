"""🇺🇸 Every crypto primitive against the TypeScript-generated vectors (PROTOCOL is normative, vectors are the proof).

🇧🇷 Toda primitiva de cripto contra os vetores gerados do TypeScript (PROTOCOL é normativo, os vetores são a prova).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from diagnos.crypto import (
    DOCUMENT_DEK_INFO,
    INDEX_INFO,
    NODE_DEK_INFO,
    NODE_NAME_INFO,
    derive_sse_c_key,
    encrypt_stream,
    encrypted_size,
    sse_c_headers,
)
from diagnos.crypto.content import (
    DRAFT_CONTENT_INFO,
    SEALED_OVERHEAD_BYTES,
    VERSION_CONTENT_INFO,
    derive_content_key,
    draft_key_id,
    open_draft_content,
    open_version_content,
    seal_version_content,
)
from diagnos.crypto.encoding import b64url_decode
from diagnos.crypto.envelope import EncryptedPayload, decrypt_content, unwrap_key
from diagnos.crypto.hkdf import hkdf_sha256
from diagnos.crypto.hybrid import HybridKeyPair, open_hybrid
from diagnos.crypto.secretstream import decrypt_bytes, decrypt_stream
from diagnos.errors import CryptoError

from conftest import VECTORS


def load_vector(name: str) -> dict[str, Any]:
    """🇺🇸 Reads and parses one `tests/vectors/<name>.json` file.

    🇧🇷 Lê e faz o parse de um arquivo `tests/vectors/<name>.json`.
    """
    return json.loads((VECTORS / f"{name}.json").read_text("utf-8"))


def test_hkdf_with_salt_matches_vector() -> None:
    """🇺🇸 Same `ikm`/`info`/`salt` as the vault's HKDF reference must yield the same 32 bytes.

    🇧🇷 O mesmo `ikm`/`info`/`salt` da referência de HKDF do cofre precisa gerar os mesmos 32 bytes.
    """
    vector = load_vector("aes_gcm_envelope")["hkdf"]
    okm = hkdf_sha256(
        ikm=b64url_decode(vector["ikm_b64url"]),
        info=vector["info"],
        length=32,
        salt=b64url_decode(vector["salt_b64url"]),
    )
    assert bytes(okm.reveal()) == b64url_decode(vector["okm_32_b64url"])


def test_hkdf_without_salt_matches_vector() -> None:
    """🇺🇸 `salt=None` must reproduce RFC 5869's "no salt" output.

    🇧🇷 `salt=None` precisa reproduzir a saída "sem salt" da RFC 5869.
    """
    vector = load_vector("aes_gcm_envelope")["hkdf"]
    okm = hkdf_sha256(ikm=b64url_decode(vector["ikm_b64url"]), info=vector["info"], length=32, salt=None)
    assert bytes(okm.reveal()) == b64url_decode(vector["okm_no_salt_b64url"])


def test_unwrap_key_opens_vector_payload() -> None:
    """🇺🇸 `unwrap_key` must open a payload sealed by the TypeScript `wrapKey`.

    🇧🇷 `unwrap_key` precisa abrir um payload selado pelo `wrapKey` em TypeScript.
    """
    vector = load_vector("aes_gcm_envelope")["wrap_key"]
    unwrapped = unwrap_key(
        wrapping_key=b64url_decode(vector["wrapping_key_b64url"]),
        payload=EncryptedPayload.from_dict(vector["payload"]),
        info=vector["info"],
    )
    assert bytes(unwrapped.reveal()) == b64url_decode(vector["plaintext_b64url"])


def test_decrypt_content_opens_vector_payload() -> None:
    """🇺🇸 `decrypt_content` must open a payload sealed by the TypeScript `encryptContent`.

    🇧🇷 `decrypt_content` precisa abrir um payload selado pelo `encryptContent` em TypeScript.
    """
    vector = load_vector("aes_gcm_envelope")["encrypt_content"]
    plaintext = decrypt_content(
        dek=b64url_decode(vector["dek_b64url"]),
        payload=EncryptedPayload.from_dict(vector["payload"]),
        info=vector["info"],
    )
    assert plaintext.decode("utf-8") == vector["plaintext_utf8"]


def _hybrid_keypair_from_vector(vector: dict[str, object]) -> HybridKeyPair:
    recipient = vector["recipient"]
    assert isinstance(recipient, dict)
    return HybridKeyPair.from_secrets(
        x25519_secret=b64url_decode(recipient["x25519_secret_b64url"]),
        mlkem768_secret=b64url_decode(recipient["mlkem768_secret_b64url"]),
    )


def test_open_hybrid_opens_vector_seal() -> None:
    """🇺🇸 `open_hybrid`, given the vector's secret keys, must open `sealed` to `plaintext_utf8`.

    🇧🇷 `open_hybrid`, com as chaves secretas do vetor, precisa abrir `sealed` para `plaintext_utf8`.
    """
    vector = load_vector("hybrid_seal")
    keypair = _hybrid_keypair_from_vector(vector)
    plaintext = open_hybrid(keypair, EncryptedPayload.from_dict(vector["sealed"]), aad=vector["aad"])
    assert plaintext.decode("utf-8") == vector["plaintext_utf8"]


def test_open_hybrid_rejects_wrong_aad() -> None:
    """🇺🇸 A seal bound to one `enrollment_id` must not open under another.

    🇧🇷 Um selo amarrado a um `enrollment_id` não pode abrir sob outro.
    """
    vector = load_vector("hybrid_seal")
    keypair = _hybrid_keypair_from_vector(vector)
    with pytest.raises(CryptoError):
        open_hybrid(keypair, EncryptedPayload.from_dict(vector["sealed"]), aad="wrong-enrollment-id")


def test_decrypt_bytes_matches_vector_plaintext() -> None:
    """🇺🇸 `decrypt_bytes` on the full framed body must equal the concatenated plaintext chunks.

    🇧🇷 `decrypt_bytes` sobre o corpo framed inteiro precisa dar a concatenação dos chunks de texto claro.
    """
    vector = load_vector("secretstream")
    key = b64url_decode(vector["key_b64url"])
    framed_body = b64url_decode(vector["framed_body_b64url"])
    expected = "".join(vector["plaintext_chunks_utf8"]).encode("utf-8")
    assert decrypt_bytes(key, framed_body) == expected


def test_decrypt_stream_at_arbitrary_boundaries_matches_vector() -> None:
    """🇺🇸 Feeding the framed body one byte at a time must still reassemble correctly.

    This is the whole point of the length-prefix framing (PROTOCOL §9): the
    network never respects our chunk boundaries, so the reader must not
    either.

    🇧🇷 Alimentar o corpo framed um byte por vez ainda precisa remontar corretamente.

    Esse é o ponto inteiro do framing por prefixo de tamanho (PROTOCOL §9): a
    rede nunca respeita nossas fronteiras de chunk, então o leitor também não pode.
    """
    vector = load_vector("secretstream")
    key = b64url_decode(vector["key_b64url"])
    framed_body = b64url_decode(vector["framed_body_b64url"])
    expected = "".join(vector["plaintext_chunks_utf8"]).encode("utf-8")

    one_byte_at_a_time = (framed_body[i : i + 1] for i in range(len(framed_body)))
    assembled = b"".join(decrypt_stream(key, one_byte_at_a_time))
    assert assembled == expected


def test_document_dek_unwraps_with_the_document_label() -> None:
    """🇺🇸 A document DEK the web app sealed opens with `DOCUMENT_DEK_INFO` — one label for every resource.

    🇧🇷 Uma DEK de documento que o app web selou abre com `DOCUMENT_DEK_INFO` — um rótulo para todo recurso.
    """
    vector = load_vector("document_content")
    assert vector["dek_info"] == DOCUMENT_DEK_INFO
    dek = unwrap_key(
        b64url_decode(vector["group_kek_b64url"]), EncryptedPayload.from_dict(vector["wrapped_dek"]), DOCUMENT_DEK_INFO
    )
    assert bytes(dek.reveal()) == b64url_decode(vector["document_dek_b64url"])


def test_content_key_and_version_body_match_the_web_app() -> None:
    """🇺🇸 Content key = HKDF(dek, salt=version_id, info=security_context); the raw sealed body opens.

    🇧🇷 Chave de conteúdo = HKDF(dek, salt=version_id, info=security_context); o corpo selado cru abre.
    """
    vector = load_vector("document_content")
    dek = b64url_decode(vector["document_dek_b64url"])
    version = vector["version"]
    assert version["info"] == VERSION_CONTENT_INFO
    key = derive_content_key(dek, version["version_id"], version["security_context"])
    assert bytes(key.reveal()) == b64url_decode(version["content_key_b64url"])
    sealed = b64url_decode(version["sealed_b64url"])
    plaintext = open_version_content(dek, version["version_id"], version["security_context"], sealed)
    assert plaintext.decode("utf-8") == version["plaintext_utf8"]
    assert len(sealed) - len(plaintext) == version["sealed_overhead_bytes"] == SEALED_OVERHEAD_BYTES


def test_draft_body_matches_the_web_app() -> None:
    """🇺🇸 The draft head opens with its fixed key id (`draft:data` on patients) and the draft label.

    🇧🇷 A cabeça de rascunho abre com o id fixo (`draft:data` em pacientes) e o rótulo de rascunho.
    """
    vector = load_vector("document_content")
    draft = vector["draft"]
    assert draft["info"] == DRAFT_CONTENT_INFO
    assert draft["draft_key_id"] == draft_key_id("data", multi_stream=True)
    plaintext = open_draft_content(
        b64url_decode(vector["document_dek_b64url"]),
        draft["draft_key_id"],
        draft["security_context"],
        b64url_decode(draft["sealed_b64url"]),
    )
    assert json.loads(plaintext)["legal_name"] == "Maria da Silva"


@pytest.mark.parametrize(("name", "resource"), [("patient_index", "patients"), ("exam_index", "exams")])
def test_encrypted_index_matches_the_web_app(name: str, resource: str) -> None:
    """🇺🇸 `encrypted_index` opens under the DEK with the resource's index label.

    🇧🇷 O `encrypted_index` abre sob a DEK com o rótulo de índice do recurso.
    """
    vector = load_vector("document_content")
    entry = vector[name]
    assert entry["info"] == INDEX_INFO[resource]
    plaintext = decrypt_content(
        b64url_decode(vector["document_dek_b64url"]), EncryptedPayload.from_dict(entry["encrypted"]), entry["info"]
    )
    assert plaintext.decode("utf-8") == entry["plaintext_utf8"]


def test_version_body_rejects_the_wrong_context_and_short_frames() -> None:
    """🇺🇸 A different `security_context` or a truncated frame never opens.

    🇧🇷 Outro contexto ou quadro curto nunca abre.
    """
    vector = load_vector("document_content")
    dek = b64url_decode(vector["document_dek_b64url"])
    version = vector["version"]
    sealed = b64url_decode(version["sealed_b64url"])
    with pytest.raises(CryptoError):
        open_version_content(dek, version["version_id"], "another-context", sealed)
    with pytest.raises(CryptoError):
        open_version_content(dek, version["version_id"], version["security_context"], sealed[:28])


def test_seal_version_content_round_trips_with_fresh_salt() -> None:
    """🇺🇸 Sealing twice gives different bytes (fresh salt/nonce) that both open.

    🇧🇷 Selar duas vezes dá bytes diferentes que abrem.
    """
    vector = load_vector("document_content")
    dek = b64url_decode(vector["document_dek_b64url"])
    first = seal_version_content(dek, "v1", "ctx", b"{}")
    second = seal_version_content(dek, "v1", "ctx", b"{}")
    assert first != second
    assert open_version_content(dek, "v1", "ctx", first) == open_version_content(dek, "v1", "ctx", second) == b"{}"


def test_node_dek_and_name_match_the_web_app() -> None:
    """🇺🇸 A node DEK unwraps with `imgexam-node-dek-v1`; its name opens under it with `imgexam-node-name-v1`.

    🇧🇷 A DEK de um nó abre com `imgexam-node-dek-v1`; o nome abre sob ela com `imgexam-node-name-v1`.
    """
    vector = load_vector("node_content")
    assert (vector["dek_info"], vector["name_info"]) == (NODE_DEK_INFO, NODE_NAME_INFO)
    dek = unwrap_key(
        b64url_decode(vector["group_kek_b64url"]), EncryptedPayload.from_dict(vector["wrapped_dek"]), NODE_DEK_INFO
    )
    assert bytes(dek.reveal()) == b64url_decode(vector["node_dek_b64url"])
    name = decrypt_content(dek, EncryptedPayload.from_dict(vector["encrypted_name"]), NODE_NAME_INFO)
    assert name.decode("utf-8") == vector["name"]


def test_node_content_and_sse_c_keys_match_the_web_app() -> None:
    """🇺🇸 Content key and its SSE-C sister (and headers) byte for byte with `@repo/magic-files`.

    🇧🇷 Chave de conteúdo e a irmã de SSE-C (e os headers) byte a byte com `@repo/magic-files`.
    """
    vector = load_vector("node_content")
    dek = b64url_decode(vector["node_dek_b64url"])
    context = vector["security_context"]["value"]
    content_key = derive_content_key(dek, vector["node_id"], context)
    assert bytes(content_key.reveal()) == b64url_decode(vector["content_key_b64url"])
    sister = derive_sse_c_key(dek, vector["node_id"], context)
    assert sister == b64url_decode(vector["sse_c_key_b64url"])
    assert sse_c_headers(sister) == vector["sse_c_headers"]


@pytest.mark.parametrize("index", [0, 1, 2], ids=["remainder", "exact_multiple", "empty"])
def test_node_bodies_match_the_web_app_framing(index: int) -> None:
    """🇺🇸 Web-app bodies decrypt, and the SDK's own sealing has exactly the web app's length.

    🇧🇷 Corpos do app web decifram, e a selagem do próprio SDK tem exatamente o tamanho do app web.
    """
    vector = load_vector("node_content")
    body = vector["bodies"][index]
    key = b64url_decode(vector["content_key_b64url"])
    framed = b64url_decode(body["framed_b64url"])
    plaintext = body["plaintext_utf8"].encode("utf-8")
    assert b"".join(decrypt_stream(key, [framed])) == plaintext
    own = b"".join(encrypt_stream(key, [plaintext], chunk_size=vector["chunk_size"]))
    assert len(own) == len(framed) == body["encrypted_length"] == encrypted_size(len(plaintext), vector["chunk_size"])
    for size, expected in vector["encrypted_length_default_chunk"].items():
        assert encrypted_size(int(size)) == expected
