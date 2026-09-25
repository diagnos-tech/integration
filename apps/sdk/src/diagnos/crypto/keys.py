"""🇺🇸 Key derivation glue: DEKs, `info` strings and the SSE-C sister key (PROTOCOL §7–§10).

Every `info` string below is versioned and never shared between purposes —
see `hkdf.py` for why that matters. This module is where the protocol's
purpose-to-`info` table actually lives in code, so a caller never has to
type one of these strings by hand.

🇧🇷 Cola de derivação de chave: DEKs, strings de `info` e a chave irmã de SSE-C (PROTOCOL §7–§10).

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

# 🇺🇸 `info` for a drive node's own DEK, wrapped under its security group's key — one DEK per file or folder.
# 🇧🇷 `info` da DEK própria de um nó de drive, embrulhada sob a chave do security group — uma DEK por arquivo ou pasta.
NODE_DEK_INFO: Final[str] = "imgexam-node-dek-v1"

# 🇺🇸 `info` for sealing a node's file name under the node's DEK.
# 🇧🇷 `info` para selar o nome do arquivo de um nó sob a DEK do nó.
NODE_NAME_INFO: Final[str] = "imgexam-node-name-v1"

# 🇺🇸 Suffix appended to `security_context` to derive the SSE-C sister key of an object's content key.
# 🇧🇷 Sufixo acrescentado ao `security_context` para derivar a chave irmã de SSE-C da chave de conteúdo.
SSE_C_INFO_SUFFIX: Final[str] = "|sse-c-v1"


def generate_dek(entropy: EntropyMixer) -> SecretBox:
    """🇺🇸 32 random bytes — one per document or node — born inside a locked box.

    Drawn from the mixer rather than `os.urandom` alone so the vault's
    per-response seed (PROTOCOL §4) reaches every DEK this process creates,
    the same composed-entropy rule the web app follows.

    🇧🇷 32 bytes aleatórios — um por documento ou nó — nascidos dentro de uma caixa travada.

    Tirados do misturador em vez de só `os.urandom` para a semente por
    resposta do cofre (PROTOCOL §4) alcançar toda DEK que este processo cria,
    a mesma regra de entropia composta que o app web segue.
    """
    return entropy.random_secret(DEK_LENGTH)


def derive_sse_c_key(dek: SecretLike, key_id: str, security_context: str) -> bytes:
    """🇺🇸 The SSE-C customer key: the content key's sister, `HKDF(dek, salt=key_id, info=context + "|sse-c-v1")`.

    SSE-C is R2's second layer on top of the end-to-end encrypted body, and
    this key goes on the wire as a header — the one derived key that
    deliberately leaves the enclave as `bytes`. It is a *sister* of the
    content key (a different `info`), so whoever learns it (R2, anyone who
    sees the request) learns nothing about the key that protects the
    plaintext.

    🇧🇷 A chave de SSE-C: irmã da chave de conteúdo, `HKDF(dek, salt=key_id, info=context + "|sse-c-v1")`.

    O SSE-C é a segunda camada do R2 sobre o corpo cifrado ponta a ponta, e
    esta chave vai pelo fio como header — a única chave derivada que sai de
    propósito do enclave como `bytes`. Ela é *irmã* da chave de conteúdo (um
    `info` diferente), então quem a conhece (o R2, quem vê a requisição) não
    aprende nada sobre a chave que protege o texto claro.
    """
    info = security_context + SSE_C_INFO_SUFFIX
    revealed = hkdf_sha256(dek, info, length=32, salt=key_id.encode("utf-8")).reveal()
    try:
        return bytes(revealed)
    finally:
        zero(revealed)


def sse_c_headers(key: bytes) -> dict[str, str]:
    """🇺🇸 The three R2/S3 SSE-C headers for `key` (standard base64, with padding), as the web app sends them.

    R2 requires the customer key's MD5 as an integrity check on the header
    itself, not as a security property — MD5 here is a checksum the object
    store demands, not a cryptographic commitment to anything.

    🇧🇷 Os três headers de SSE-C do R2/S3 para `key` (base64 padrão, com padding), como o app web os manda.

    O R2 exige o MD5 da chave do cliente como checagem de integridade do
    próprio header, não como propriedade de segurança — o MD5 aqui é um
    checksum que o object store pede, não um compromisso criptográfico com
    nada.
    """
    digest = hashlib.md5(key, usedforsecurity=False).digest()
    return {
        "x-amz-server-side-encryption-customer-algorithm": "AES256",
        "x-amz-server-side-encryption-customer-key": base64.b64encode(key).decode("ascii"),
        "x-amz-server-side-encryption-customer-key-md5": base64.b64encode(digest).decode("ascii"),
    }
