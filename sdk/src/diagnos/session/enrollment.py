"""🇺🇸 Enrollment: how an SDK process earns a session and the group keys it may use.

🇧🇷 Enrollment: como um processo do SDK conquista uma sessão e as chaves de grupo que pode usar.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from diagnos import __version__
from diagnos.crypto.envelope import EncryptedPayload
from diagnos.crypto.hybrid import HybridKeyPair
from diagnos.crypto.secure import SecretBox
from diagnos.errors import (
    CryptoError,
    DiagnosError,
    EnrollmentDeniedError,
    EnrollmentExpiredError,
    NotFoundError,
)
from diagnos.session.keyring import Keyring, SessionKeys
from diagnos.session.runtime import collect_runtime

# 🇺🇸 Deferred to type-checking only: `diagnos.transport` eagerly imports
# `diagnos.session.keyring` (for `VaultTransport`'s own type hints), so a
# module-level import here — of a *submodule* of `diagnos.transport` — would
# close a real import cycle the moment anything imports `diagnos.transport`
# before `diagnos.session`. Nothing below needs the classes at runtime: it
# only calls duck-typed methods/attributes (`transport.post(...)`,
# `token.workspace_id`) that never require the class object itself.
# 🇧🇷 Adiado só para checagem de tipos: `diagnos.transport` importa
# `diagnos.session.keyring` de forma antecipada (para os próprios type hints
# de `VaultTransport`), então um import no nível do módulo aqui — de um
# *submódulo* de `diagnos.transport` — fecharia um ciclo de import de
# verdade assim que algo importasse `diagnos.transport` antes de
# `diagnos.session`. Nada abaixo precisa das classes em tempo de execução:
# só chama métodos/atributos duck-typed (`transport.post(...)`,
# `token.workspace_id`) que nunca exigem o objeto da classe.
if TYPE_CHECKING:
    from diagnos.transport.http import VaultTransport
    from diagnos.transport.token import ServiceAccountToken

# 🇺🇸 The one shape a session DEK — and every group DEK — must have
# (`docs/PROTOCOL.md §5`): raw AES-256-GCM key material, nothing wrapped
# around it. A wrong length can only mean a protocol mismatch, never a
# recoverable state, so it fails loudly instead of silently truncating or
# padding.
# 🇧🇷 A única forma que uma DEK de sessão — e toda DEK de grupo — deve ter
# (`docs/PROTOCOL.md §5`): material de chave AES-256-GCM cru, sem nada
# embrulhado ao redor. Um tamanho errado só pode ser incompatibilidade de
# protocolo, nunca um estado recuperável, então falha alto em vez de truncar
# ou preencher em silêncio.
_GROUP_KEY_LENGTH = 32


@dataclass(frozen=True)
class EnrollmentPrompt:
    """🇺🇸 What a human needs to see: the link to open and the code to type.

    🇧🇷 O que uma pessoa precisa ver: o link para abrir e o código para digitar.
    """

    enrollment_id: str
    approval_url: str
    code: str
    expires_at: int


PromptCallback = Callable[[EnrollmentPrompt], None]


def _registry_path(workspace_id: str) -> str:
    """🇺🇸 The unsigned enrollment route both the POST and the GET poll share a prefix with.

    🇧🇷 A rota de enrollment sem assinatura cujo prefixo o POST e o GET do poll compartilham.
    """
    return f"/api/external/v1/workspaces/{workspace_id}/session/registry"


def _open_session(keypair: HybridKeyPair, enrollment_id: str, sealed_session: Any) -> SessionKeys:
    """🇺🇸 Opens `sealed_session` (AAD = `enrollment_id`) into `SessionKeys`; both keys are born inside the enclave.

    🇧🇷 Abre `sealed_session` (AAD = `enrollment_id`) em `SessionKeys`; as duas chaves nascem dentro do enclave.
    """
    payload = EncryptedPayload.from_dict(sealed_session)
    opened = keypair.open_session(payload, enrollment_id)
    return SessionKeys(
        session_id=opened.session_id,
        sign_key=opened.sign_key,
        enc_key=opened.enc_key,
        expires_at=opened.expires_at,
    )


def _open_group_keys(keypair: HybridKeyPair, enrollment_id: str, sealed_group_keys: Any) -> dict[str, SecretBox]:
    """🇺🇸 Opens every `sealed_group_keys[sg]` (AAD = `enrollment_id`) into a locked 32-byte DEK.

    🇧🇷 Abre cada `sealed_group_keys[sg]` (AAD = `enrollment_id`) numa DEK travada de 32 bytes.
    """
    group_keys: dict[str, SecretBox] = {}
    for security_group_id, sealed in dict(sealed_group_keys or {}).items():
        payload = EncryptedPayload.from_dict(sealed)
        dek = keypair.open_secret(payload, enrollment_id)
        if len(dek) != _GROUP_KEY_LENGTH:
            dek.wipe()
            raise CryptoError(
                f"🇺🇸 group DEK for {security_group_id!r} opened to {len(dek)} bytes, expected "
                f"{_GROUP_KEY_LENGTH}. "
                f"🇧🇷 DEK de grupo de {security_group_id!r} abriu com {len(dek)} bytes, esperado "
                f"{_GROUP_KEY_LENGTH}."
            )
        group_keys[security_group_id] = dek
    return group_keys


def enroll(
    transport: VaultTransport,
    token: ServiceAccountToken,
    keypair: HybridKeyPair,
    *,
    on_prompt: PromptCallback,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> Keyring:
    """🇺🇸 Register the key pair, show the prompt, poll until approved, open the sealed material.

    Both the registration `POST` and the poll `GET` go out `signed=False`
    (`docs/PROTOCOL.md §5`): a signature would need a session's `sign_key`,
    and the entire point of this call is that no session exists yet — Bearer
    auth alone is enough to prove which service account is asking, and the
    approval itself is the human decision that grants everything else.

    🇧🇷 Registra o par de chaves, mostra o prompt, faz poll até a aprovação, abre o material selado.

    Tanto o `POST` de registro quanto o `GET` do poll saem `signed=False`
    (`docs/PROTOCOL.md §5`): uma assinatura precisaria do `sign_key` de uma
    sessão, e o ponto inteiro desta chamada é que nenhuma sessão existe
    ainda — só o Bearer já basta para provar qual service account está
    pedindo, e a própria aprovação é a decisão humana que concede o resto.
    """
    path = _registry_path(token.workspace_id)
    registration = transport.post(
        path,
        json={
            "public_keys": keypair.public_keys_b64url(),
            "runtime": collect_runtime(__version__),
        },
        signed=False,
    )

    enrollment_id: str = registration["enrollment_id"]
    prompt = EnrollmentPrompt(
        enrollment_id=enrollment_id,
        approval_url=registration["approval_url"],
        code=registration["code"],
        expires_at=registration["expires_at"],
    )
    on_prompt(prompt)

    poll_interval_seconds: float = registration["poll_interval_seconds"]
    poll_path = f"{path}/{enrollment_id}"

    while True:
        if now() >= prompt.expires_at:
            raise EnrollmentExpiredError(
                "🇺🇸 nobody approved this enrollment before it expired; start again. "
                "🇧🇷 ninguém aprovou este enrollment antes de expirar; comece de novo."
            )

        try:
            poll_result = transport.get(poll_path, signed=False)
        except NotFoundError as exc:
            # 🇺🇸 The vault itself drops an enrollment past its deadline
            # (`SdkEnrollmentNotFound`); a 404 arriving after `expires_at`
            # means the same thing as our own clock check above catching it
            # first — either way, the window is closed.
            # 🇧🇷 O próprio cofre descarta um enrollment depois do prazo
            # (`SdkEnrollmentNotFound`); um 404 chegando depois de
            # `expires_at` significa o mesmo que nosso próprio relógio pegar
            # isso antes — de um jeito ou de outro, a janela fechou.
            raise EnrollmentExpiredError(
                "🇺🇸 the vault no longer knows this enrollment; the approval window closed. "
                "🇧🇷 o cofre não conhece mais este enrollment; a janela de aprovação fechou."
            ) from exc

        status = poll_result["status"]
        if status == "pending":
            sleep(poll_interval_seconds)
            continue
        if status == "denied":
            raise EnrollmentDeniedError(
                "🇺🇸 a workspace admin denied this SDK session. 🇧🇷 um admin do workspace negou esta sessão de SDK."
            )
        if status == "approved":
            approval = poll_result["approval"]
            session = _open_session(keypair, enrollment_id, approval["sealed_session"])
            group_keys = _open_group_keys(keypair, enrollment_id, approval.get("sealed_group_keys"))
            return Keyring(enrollment_id=enrollment_id, session=session, group_keys=group_keys)

        raise DiagnosError(
            f"🇺🇸 session/registry poll returned unknown status {status!r}. "
            f"🇧🇷 o poll de session/registry retornou status desconhecido {status!r}."
        )
