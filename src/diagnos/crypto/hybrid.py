"""🇺🇸 HybridSeal — X25519 + ML-KEM-768 → HKDF-SHA256 → AES-256-GCM (PROTOCOL §6), private halves in the enclave.

The same construction seals the session (vault → SDK, on enrollment approval)
and the security-group DEKs (web app → SDK). Two KEMs, not one: an adversary
recording today's traffic and breaking X25519 tomorrow with a quantum
computer still has to break ML-KEM-768 too, and a flaw in ML-KEM's young
implementation still leaves X25519 standing. The shared secret only falls if
*both* primitives do. Reference: the vault's `hybridSeal`, pinned by `tests/vectors/hybrid_seal.json`.

The private halves never exist as Python objects: they are generated, stored
and used inside `diagnos._secure`, and what this module holds is a handle.

🇧🇷 HybridSeal — X25519 + ML-KEM-768 → HKDF-SHA256 → AES-256-GCM (PROTOCOL §6), metades privadas no enclave.

A mesma construção sela a sessão (cofre → SDK, na aprovação do enrollment) e
as DEKs de security group (app web → SDK). Dois KEMs, não um: um adversário
que grave o tráfego de hoje e quebre X25519 amanhã com computador quântico
ainda precisa quebrar ML-KEM-768; e um defeito na implementação jovem do
ML-KEM ainda deixa X25519 de pé. O segredo compartilhado só cai se *as duas*
primitivas caírem.

As metades privadas nunca existem como objetos Python: são geradas, guardadas
e usadas dentro de `diagnos._secure`, e o que este módulo segura é um handle.
"""

from __future__ import annotations

from dataclasses import dataclass

from diagnos import _secure

from .encoding import b64url_encode
from .envelope import EncryptedPayload
from .secure import SecretBox, SecretLike, as_secret

# 🇺🇸 Frozen wire constant — the `imgexam-` prefix is historical; see `keys.py`.
# 🇧🇷 Constante de fio congelada — o prefixo `imgexam-` é histórico; ver `keys.py`.
HYBRID_SEAL_INFO = "imgexam-sdk-hybrid-seal-v1"
X25519_SECRET_BYTES = _secure.X25519_SECRET_BYTES
X25519_PUBLIC_BYTES = _secure.X25519_PUBLIC_BYTES
MLKEM768_PUBLIC_BYTES = _secure.MLKEM768_PUBLIC_BYTES
MLKEM768_SECRET_BYTES = _secure.MLKEM768_SECRET_BYTES
MLKEM768_CIPHERTEXT_BYTES = _secure.MLKEM768_CIPHERTEXT_BYTES


@dataclass(frozen=True, slots=True)
class OpenedSession:
    """🇺🇸 What `sealed_session` opens to (PROTOCOL §5), with both keys already locked.

    🇧🇷 Para o que `sealed_session` abre (PROTOCOL §5), com as duas chaves já travadas.
    """

    session_id: str
    expires_at: int
    sign_key: SecretBox
    enc_key: SecretBox


class HybridKeyPair:
    """🇺🇸 An SDK identity: one X25519 keypair plus one ML-KEM-768 keypair.

    Secrets live in the enclave for the whole life of an enrollment — this
    pair is the thing that opens every session and group key the SDK ever
    receives — and are wiped by `zeroize()` the moment the session ends.

    🇧🇷 Uma identidade de SDK: um par X25519 mais um par ML-KEM-768.

    Secretas vivem no enclave pela vida inteira de um enrollment — este par
    é o que abre toda sessão e chave de grupo que o SDK recebe — e são
    apagadas por `zeroize()` no instante em que a sessão termina.
    """

    __slots__ = ("_native",)

    def __init__(self, native: _secure.HybridKeyPair) -> None:
        """🇺🇸 Wraps an enclave keypair; use `generate()`/`from_secrets()`.

        🇧🇷 Embrulha um par do enclave; use `generate()`/`from_secrets()`.
        """
        self._native = native

    @classmethod
    def generate(cls) -> HybridKeyPair:
        """🇺🇸 A fresh identity, used at enrollment time. 🇧🇷 Uma identidade nova, usada no enrollment."""
        return cls(_secure.HybridKeyPair.generate())

    @classmethod
    def from_secrets(cls, x25519_secret: SecretLike, mlkem768_secret: SecretLike) -> HybridKeyPair:
        """🇺🇸 Rebuilds a pair from persisted secrets (an OpenBao restore).

        Only the secrets are ever persisted (PROTOCOL §11) — the public keys
        are recomputed inside the enclave rather than also stored, so there
        is one fewer place a stale or mismatched public key could sneak in.
        The ML-KEM-768 secret is the FIPS 203 expanded form (2400 bytes,
        `dk_pke ‖ ek ‖ H(ek) ‖ z`), the encoding every other implementation
        of the protocol produces.

        🇧🇷 Reconstrói um par a partir de secretas persistidas (restore do OpenBao).

        Só as secretas são persistidas (PROTOCOL §11) — as públicas são
        recalculadas dentro do enclave em vez de também guardadas, um lugar a
        menos onde uma pública velha ou incompatível poderia se infiltrar. A
        secreta ML-KEM-768 é a forma expandida da FIPS 203 (2400 bytes,
        `dk_pke ‖ ek ‖ H(ek) ‖ z`), a codificação que toda outra
        implementação do protocolo produz.
        """
        return cls(_secure.HybridKeyPair.from_secrets(as_secret(x25519_secret), as_secret(mlkem768_secret)))

    @property
    def x25519_public(self) -> bytes:
        """🇺🇸 32-byte X25519 public key. 🇧🇷 Chave pública X25519 de 32 bytes."""
        return self._native.x25519_public

    @property
    def mlkem768_public(self) -> bytes:
        """🇺🇸 1184-byte ML-KEM-768 encapsulation key. 🇧🇷 Chave de encapsulamento ML-KEM-768 de 1184 bytes."""
        return self._native.mlkem768_public

    @property
    def is_wiped(self) -> bool:
        """🇺🇸 Whether `zeroize()` already ran. 🇧🇷 Se `zeroize()` já rodou."""
        return self._native.is_wiped

    def x25519_secret(self) -> SecretBox:
        """🇺🇸 A locked copy of the X25519 secret, for `OpenBaoStore.save`.

        🇧🇷 Uma cópia travada da secreta X25519, para `OpenBaoStore.save`.
        """
        return self._native.x25519_secret()

    def mlkem768_secret(self) -> SecretBox:
        """🇺🇸 A locked copy of the expanded ML-KEM-768 secret, for `OpenBaoStore.save`.

        🇧🇷 Uma cópia travada da secreta ML-KEM-768 expandida, para `OpenBaoStore.save`.
        """
        return self._native.mlkem768_secret()

    def public_keys_b64url(self) -> dict[str, str]:
        """🇺🇸 The shape `session/registry` expects in `public_keys`.

        🇧🇷 O formato que `session/registry` espera em `public_keys`.
        """
        return {"x25519": b64url_encode(self.x25519_public), "mlkem768": b64url_encode(self.mlkem768_public)}

    def open(self, payload: EncryptedPayload, aad: str) -> bytes:
        """🇺🇸 Opens a seal to plain `bytes` — for content, never for keys (use `open_secret`).

        🇧🇷 Abre um selo para `bytes` — para conteúdo, nunca para chaves (use `open_secret`).
        """
        encapsulation, nonce, ciphertext = payload.decode()
        return self._native.open(encapsulation, nonce, ciphertext, aad.encode("utf-8"))

    def open_secret(self, payload: EncryptedPayload, aad: str) -> SecretBox:
        """🇺🇸 Opens a seal straight into a locked box (a group DEK).

        🇧🇷 Abre um selo direto numa caixa travada (uma DEK de grupo).
        """
        encapsulation, nonce, ciphertext = payload.decode()
        return self._native.open_secret(encapsulation, nonce, ciphertext, aad.encode("utf-8"))

    def open_session(self, payload: EncryptedPayload, aad: str) -> OpenedSession:
        """🇺🇸 Opens `sealed_session` (PROTOCOL §5); the JSON and both keys are parsed inside the enclave.

        🇧🇷 Abre `sealed_session` (PROTOCOL §5); o JSON e as duas chaves são lidos dentro do enclave.
        """
        encapsulation, nonce, ciphertext = payload.decode()
        session_id, expires_at, sign_key, enc_key = self._native.open_session(
            encapsulation, nonce, ciphertext, aad.encode("utf-8")
        )
        return OpenedSession(session_id=session_id, expires_at=expires_at, sign_key=sign_key, enc_key=enc_key)

    def zeroize(self) -> None:
        """🇺🇸 Wipes both secrets now; every later `open` fails.

        🇧🇷 Apaga as duas secretas agora; todo `open` depois falha.
        """
        self._native.wipe()

    def __repr__(self) -> str:
        """🇺🇸 Never the secrets. 🇧🇷 Nunca as secretas."""
        return f"HybridKeyPair(x25519={b64url_encode(self.x25519_public)[:8]}…, mlkem768=<1184 B>, secrets=<enclave>)"


def seal_hybrid(x25519_public: bytes, mlkem768_public: bytes, plaintext: bytes, aad: str) -> EncryptedPayload:
    """🇺🇸 Seals `plaintext` to a recipient's public keys; `aad` binds the seal to context.

    `aad` is always the `enrollment_id`: a seal produced for one enrollment
    must not open under another, even with the same recipient keys. The SDK
    itself only *opens* seals; this exists for tests and for tooling that
    plays the vault's or the web app's role.

    🇧🇷 Sela `plaintext` para as chaves públicas de um destinatário; `aad` amarra o selo ao contexto.

    `aad` é sempre o `enrollment_id`: um selo produzido para um enrollment não
    pode abrir em outro, mesmo com as mesmas chaves de destinatário. O SDK em
    si só *abre* selos; isto existe para testes e para ferramentas que fazem o
    papel do cofre ou do app web.
    """
    encapsulation, nonce, ciphertext = _secure.seal_hybrid(
        x25519_public, mlkem768_public, plaintext, aad.encode("utf-8")
    )
    return EncryptedPayload(
        salt=b64url_encode(encapsulation), nonce=b64url_encode(nonce), ciphertext=b64url_encode(ciphertext)
    )


def open_hybrid(keypair: HybridKeyPair, payload: EncryptedPayload, aad: str) -> bytes:
    """🇺🇸 `keypair.open(payload, aad)` as a function; wrong `aad`, wrong keys or tampering all raise `CryptoError`.

    🇧🇷 `keypair.open(payload, aad)` como função; `aad` errado, chaves erradas ou adulteração lançam `CryptoError`.
    """
    return keypair.open(payload, aad)
