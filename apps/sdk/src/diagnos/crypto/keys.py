"""🇺🇸 Key derivation glue: DEKs, `info` strings and drive/SSE-C subkeys (PROTOCOL §7, §9, §10).

Every `info` string below is versioned and never shared between purposes —
see `hkdf.py` for why that matters. This module is where the protocol's
purpose-to-`info` table actually lives in code, so a caller never has to
type one of these strings by hand.

🇧🇷 Cola de derivação de chave: DEKs, strings de `info` e subchaves de drive/SSE-C (PROTOCOL §7, §9, §10).

Toda string de `info` abaixo é versionada e nunca compartilhada entre
propósitos — veja `hkdf.py` para o porquê disso importar. Este módulo é onde
a tabela propósito-para-`info` do protocolo de fato vive em código, para
quem chama nunca precisar digitar uma dessas strings à mão.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Final

from .entropy import EntropyMixer
from .hkdf import hkdf_sha256
from .secure import SecretBox, SecretLike, zero

DEK_LENGTH = 32

# 🇺🇸 Every label below is a frozen wire constant: the `imgexam-` prefix predates
#    the diagnos name and is baked into every ciphertext already stored, so
#    renaming one would make existing documents unreadable. See
#    `docs/PROTOCOL.md` ("Frozen labels"); the vectors in `tests/vectors/` pin them.
# 🇧🇷 Todo rótulo abaixo é uma constante de fio congelada: o prefixo `imgexam-`
#    é anterior ao nome diagnos e está em todo ciphertext já gravado, então
#    renomear um tornaria documentos existentes ilegíveis. Ver
#    `docs/PROTOCOL.pt-BR.md` ("Rótulos congelados"); os vetores em
#    `tests/vectors/` os travam.
#
# 🇺🇸 `info` for wrapping a document's DEK under its security group's key. One
#    label for patients, exams *and* templates: the web app seals every
#    document DEK with it (`DOCUMENT_DEK_INFO` in its security module), so the
#    `patient` in the name is history, not scope.
# 🇧🇷 `info` para embrulhar a DEK de um documento sob a chave do security
#    group. Um rótulo só para pacientes, exames *e* modelos: o app web sela
#    toda DEK de documento com ele (`DOCUMENT_DEK_INFO` no módulo de
#    segurança dele), então o `patient` no nome é histórico, não escopo.
DOCUMENT_DEK_INFO: Final[str] = "imgexam-patient-dek-v1"

# 🇺🇸 `info` for sealing a document's `encrypted_index` (its list/search summary) under the document DEK.
# 🇧🇷 `info` para selar o `encrypted_index` de um documento (resumo de lista/busca) sob a DEK do documento.
INDEX_INFO: Final[dict[str, str]] = {
    "patients": "imgexam-patient-index-v1",
    "exams": "imgexam-exam-index-v1",
    "templates": "imgexam-template-index-v1",
}

NODE_NAME_INFO: Final[str] = "imgexam-drive-node-name-v1"
_NODE_KEY_INFO: Final[str] = "imgexam-drive-node-key-v1"
_SSE_C_INFO: Final[str] = "imgexam-sse-c-v1"


def generate_dek(entropy: EntropyMixer) -> SecretBox:
    """🇺🇸 32 random bytes — one per document, reused across its versions — born inside a locked box.

    Drawn from the mixer rather than `os.urandom` alone so the vault's
    per-response seed (PROTOCOL §4) reaches every DEK this process creates.

    🇧🇷 32 bytes aleatórios — uma por documento, reusada entre as versões dele — nascidos dentro de uma caixa travada.

    Tirados do misturador em vez de só `os.urandom` para a semente por
    resposta do cofre (PROTOCOL §4) alcançar toda DEK que este processo cria.
    """
    return entropy.random_secret(DEK_LENGTH)


def derive_node_key(group_dek: SecretLike, node_id: str) -> SecretBox:
    """🇺🇸 A drive node's key, derived from its group DEK — no per-node wrapped key needed.

    Salting by `node_id` means every node in a drive gets an independent key
    from the *same* group DEK; revocation happens once, at the group, and
    every derived node key dies with it.

    🇧🇷 A chave de um nó de drive, derivada da DEK do grupo — sem precisar de chave embrulhada por nó.

    Usar `node_id` como salt faz cada nó de um drive ganhar uma chave
    independente a partir da *mesma* DEK de grupo; a revogação acontece uma
    vez, no grupo, e toda chave de nó derivada morre junto.
    """
    return hkdf_sha256(group_dek, _NODE_KEY_INFO, length=32, salt=node_id.encode("utf-8"))


def derive_sse_c_key(key: SecretLike) -> bytes:
    """🇺🇸 The optional SSE-C key layered on top of an already end-to-end-encrypted object (§10).

    This is the one derived key that deliberately leaves the enclave as
    `bytes`: it goes on the wire, base64-encoded, as an HTTP header to the
    object store (`sse_c_headers`), so there is nothing to hide from the
    Python heap that the request itself will not carry.

    🇧🇷 A chave opcional de SSE-C, em cima de um objeto já cifrado ponta a ponta (§10).

    É a única chave derivada que deliberadamente sai do enclave como
    `bytes`: ela vai pelo fio, em base64, como header HTTP para o object
    store (`sse_c_headers`), então não há nada a esconder do heap do Python
    que a própria requisição já não carregue.
    """
    revealed = hkdf_sha256(key, _SSE_C_INFO, length=32, salt=None).reveal()
    try:
        return bytes(revealed)
    finally:
        zero(revealed)


def sse_c_headers(key: bytes) -> dict[str, str]:
    """🇺🇸 The three R2/S3 SSE-C headers for `key` (standard base64, with padding).

    R2 requires the customer key's MD5 as an integrity check on the header
    itself, not as a security property — MD5 here is a checksum the object
    store demands, not a cryptographic commitment to anything.

    🇧🇷 Os três headers de SSE-C do R2/S3 para `key` (base64 padrão, com padding).

    O R2 exige o MD5 da chave do cliente como checagem de integridade do
    próprio header, não como propriedade de segurança — o MD5 aqui é um
    checksum que o object store pede, não um compromisso criptográfico com
    nada.
    """
    digest = hashlib.md5(key, usedforsecurity=False).digest()
    return {
        "x-amz-server-side-encryption-customer-algorithm": "AES256",
        "x-amz-server-side-encryption-customer-key": base64.b64encode(key).decode("ascii"),
        "x-amz-server-side-encryption-customer-key-MD5": base64.b64encode(digest).decode("ascii"),
    }
