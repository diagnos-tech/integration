"""🇺🇸 In-memory secrets a live enrollment holds: session keys and group DEKs, every one a `SecretBox`.

Nothing here is `bytes` or `bytearray`: each key is a `SecretBox`, bytes in
page-locked Rust memory (`crypto/secure.py`) that never come back to the
Python heap — signing, opening a seed, unwrapping a document key all happen
inside the enclave. `zeroize()` wipes each box the moment the session ends
instead of hoping for a timely garbage collection. Nothing in this module
ever touches the network or the filesystem — that is the whole point of a
keyring: it is the one place in the SDK the vault's own protocol does not
reach.

🇧🇷 Segredos em memória de um enrollment ativo: chaves de sessão e DEKs de grupo, cada uma um `SecretBox`.

Nada aqui é `bytes` ou `bytearray`: cada chave é um `SecretBox`, bytes em
memória Rust travada em página (`crypto/secure.py`) que nunca voltam ao heap
do Python — assinar, abrir uma semente, desembrulhar uma chave de documento
acontecem dentro do enclave. `zeroize()` apaga cada caixa no instante em que
a sessão termina em vez de esperar por uma coleta de lixo a tempo. Nada
neste módulo toca rede ou disco — esse é o ponto de um keyring: é o único
lugar do SDK que o próprio protocolo do cofre não alcança.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from diagnos.crypto.secure import SecretBox
from diagnos.errors import DiagnosError

DEFAULT_VALIDITY_MARGIN_SECONDS = 60


class GroupKeyUnavailable(DiagnosError):  # noqa: N818 — a missing DEK is a permission gap, not an "Error"
    """🇺🇸 The SDK was never handed the DEK of this security group.

    This happens when an admin approves an enrollment for a narrower set of
    groups than the document being opened needs — a permissions gap, not a
    crypto failure, so it is its own exception rather than `CryptoError`.

    🇧🇷 O SDK nunca recebeu a DEK deste security group.

    Acontece quando um admin aprova um enrollment para um conjunto de grupos
    mais estreito do que o documento que está sendo aberto precisa — uma
    lacuna de permissão, não uma falha de cripto, por isso é exceção própria
    em vez de `CryptoError`.
    """


@dataclass
class SessionKeys:
    """🇺🇸 The symmetric keys of one enrollment session (`docs/PROTOCOL.md §4`).

    🇧🇷 As chaves simétricas de uma sessão de enrollment (`docs/PROTOCOL.md §4`).
    """

    session_id: str
    sign_key: SecretBox
    enc_key: SecretBox
    expires_at: int

    def is_valid(self, now: int | None = None, margin_seconds: int = DEFAULT_VALIDITY_MARGIN_SECONDS) -> bool:
        """🇺🇸 True while more than `margin_seconds` remain before `expires_at`.

        The margin exists so a request does not start signing with a session
        that expires mid-flight — a request accepted at `t` but checked by
        the vault at `t + network latency` should not depend on that race.

        🇧🇷 Verdadeiro enquanto restam mais de `margin_seconds` até `expires_at`.

        A margem existe para uma requisição não começar a assinar com uma
        sessão que expira no meio do caminho — uma requisição aceita em `t`
        mas conferida pelo cofre em `t + latência de rede` não deveria
        depender dessa corrida.
        """
        current = now if now is not None else int(time.time())
        return current + margin_seconds < self.expires_at

    def zeroize(self) -> None:
        """🇺🇸 Wipe both keys; call this the moment the session ends.

        🇧🇷 Apaga as duas chaves; chame assim que a sessão termina.
        """
        self.sign_key.wipe()
        self.enc_key.wipe()

    def __repr__(self) -> str:
        """🇺🇸 Never the keys — this is what ends up in a log line.

        🇧🇷 Nunca as chaves — é isto que acaba numa linha de log.
        """
        return (
            f"SessionKeys(session_id={self.session_id!r}, expires_at={self.expires_at!r}, "
            f"sign_key=<redacted {len(self.sign_key)}B>, enc_key=<redacted {len(self.enc_key)}B>)"
        )


@dataclass
class Keyring:
    """🇺🇸 One enrollment's full unlocked state: its session plus its group DEKs.

    🇧🇷 O estado desbloqueado completo de um enrollment: sua sessão mais as DEKs de grupo.
    """

    enrollment_id: str
    session: SessionKeys
    group_keys: dict[str, SecretBox] = field(default_factory=dict)

    def group_key(self, security_group_id: str) -> SecretBox:
        """🇺🇸 The locked 32-byte DEK of `security_group_id`, or `GroupKeyUnavailable`.

        The box itself is returned, not a copy: a `SecretBox` cannot be read
        or mutated by accident, only used inside the enclave or wiped on
        purpose, so there is nothing a caller could do to it that a copy
        would need to protect against — and one fewer locked page per call.

        🇧🇷 A DEK travada de 32 bytes de `security_group_id`, ou `GroupKeyUnavailable`.

        A própria caixa é devolvida, não uma cópia: um `SecretBox` não pode
        ser lido nem mutado por acidente, só usado dentro do enclave ou
        apagado de propósito, então não há nada que quem chama pudesse fazer
        com ela contra o que uma cópia precisasse proteger — e uma página
        travada a menos por chamada.
        """
        key = self.group_keys.get(security_group_id)
        if key is None:
            raise GroupKeyUnavailable(
                f"🇺🇸 no DEK for security group {security_group_id!r} was handed to this "
                "enrollment — ask a workspace admin to include it next approval. "
                f"🇧🇷 nenhuma DEK do security group {security_group_id!r} foi entregue a "
                "este enrollment — peça a um admin do workspace para incluí-lo na "
                "próxima aprovação."
            )
        return key

    @property
    def security_group_ids(self) -> list[str]:
        """🇺🇸 Ids of every group this enrollment holds a DEK for. 🇧🇷 Ids de todo grupo cuja DEK este enrollment tem."""
        return list(self.group_keys.keys())

    def zeroize(self) -> None:
        """🇺🇸 Wipe the session keys and every group DEK. 🇧🇷 Apaga as chaves de sessão e toda DEK de grupo."""
        self.session.zeroize()
        for key in self.group_keys.values():
            key.wipe()

    def __repr__(self) -> str:
        """🇺🇸 Group ids are fine to show; the DEKs themselves never are.

        🇧🇷 Ids de grupo podem aparecer; as DEKs em si, nunca.
        """
        return (
            f"Keyring(enrollment_id={self.enrollment_id!r}, session={self.session!r}, "
            f"group_keys=<{len(self.group_keys)} redacted for {self.security_group_ids!r}>)"
        )
