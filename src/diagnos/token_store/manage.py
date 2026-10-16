"""🇺🇸 `save_token` and `forget_token`: what `diagnos login` and `diagnos logout` do, as SDK functions.

Saving follows the owner's rule for a private key: the system keyring when
there is a secure one, else OpenBao when it is configured, else refuse —
never a text file. `store=` narrows the choice (`keyring` or `openbao` only);
`auto` is that order. The text is checked (prefix and CRC) before it goes
anywhere, so a token pasted wrong is never stored.

🇧🇷 `save_token` e `forget_token`: o que `diagnos login` e `diagnos logout` fazem, como funções do SDK.

Guardar segue a regra do dono para uma chave privada: o chaveiro do sistema
quando há um seguro, senão o OpenBao quando está configurado, senão recusa —
nunca arquivo de texto. `store=` estreita a escolha (só `keyring` ou só
`openbao`); `auto` é essa ordem. O texto é conferido (prefixo e CRC) antes de
ir a qualquer lugar, então um token colado errado nunca é guardado.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

from diagnos.errors import TokenStoreError

from .keychain import Keychain
from .openbao import OpenBaoTokenStore

if TYPE_CHECKING:
    from diagnos.transport.config import Settings

StoreChoice = Literal["auto", "keyring", "openbao"]
"""🇺🇸 Where `save_token` may put the token. 🇧🇷 Onde o `save_token` pode pôr o token."""

_NOWHERE: Final = (
    "🇺🇸 There is no safe place to keep the token here: the system keyring is missing or does not encrypt at rest "
    "({keyring}), and OpenBao is not configured. Either use a keyring that encrypts (macOS Keychain, Windows "
    "Credential Locker, Secret Service or KWallet on Linux), or set OPENBAO_ADDR and OPENBAO_TOKEN (or "
    "OPENBAO_TOKEN_FILE) to keep it in OpenBao. In CI and ephemeral containers, pass it in DIAGNOS_TOKEN instead. "
    "The token is never written to a file. "
    "🇧🇷 Não há lugar seguro para guardar o token aqui: o chaveiro do sistema falta ou não cifra em repouso "
    "({keyring}), e o OpenBao não está configurado. Use um chaveiro que cifra (Keychain do macOS, Credential "
    "Locker do Windows, Secret Service ou KWallet no Linux), ou defina OPENBAO_ADDR e OPENBAO_TOKEN (ou "
    "OPENBAO_TOKEN_FILE) para guardá-lo no OpenBao. Em CI e containers efêmeros, passe-o em DIAGNOS_TOKEN. O "
    "token nunca é gravado em arquivo."
)
_NO_KEYRING: Final = (
    "🇺🇸 The system keyring ({keyring}) is missing or does not encrypt at rest, so the token is not stored there. "
    "Use `--store openbao` (store='openbao'), or a keyring that encrypts. "
    "🇧🇷 O chaveiro do sistema ({keyring}) falta ou não cifra em repouso, então o token não é guardado nele. Use "
    "`--store openbao` (store='openbao'), ou um chaveiro que cifra."
)


def save_token(
    text: str,
    *,
    settings: Settings,
    store: StoreChoice = "auto",
    keychain: Keychain | None = None,
    openbao: OpenBaoTokenStore | None = None,
) -> str:
    """🇺🇸 Check the token, store it, and say where (`keyring (…)` or `OpenBao …`); `TokenStoreError` if nowhere.

    `settings` gives the vault URL (the keyring entry's name) and the
    OpenBao configuration — `Settings.without_token()` when nothing is
    configured yet. `keychain`/`openbao` are for tests.

    🇧🇷 Confere o token, guarda e diz onde (`keyring (…)` ou `OpenBao …`); `TokenStoreError` se em lugar nenhum.

    `settings` dá a URL do cofre (o nome da entrada no chaveiro) e a
    configuração do OpenBao — `Settings.without_token()` quando nada está
    configurado ainda. `keychain`/`openbao` são para testes.
    """
    from diagnos.transport.service_token import DiagnosToken

    try:
        DiagnosToken.parse(text, source="diagnos login").wipe()
        keychain = keychain if keychain is not None else Keychain()
        if store != "openbao" and keychain.secure:
            keychain.save(settings.vault_url, text)
            return f"keyring ({keychain.name})"
        if store == "keyring":
            raise TokenStoreError(_NO_KEYRING.format(keyring=keychain.name))
        if settings.openbao_addr:
            target = openbao if openbao is not None else OpenBaoTokenStore(settings)
            target.save(text)
            return target.location
        raise TokenStoreError(_NOWHERE.format(keyring=keychain.name))
    finally:
        # 🇺🇸 No frame here keeps the text once an error propagates. 🇧🇷 Nenhum quadro daqui guarda o texto num erro.
        del text


def forget_token(
    *, settings: Settings, keychain: Keychain | None = None, openbao: OpenBaoTokenStore | None = None
) -> list[str]:
    """🇺🇸 Delete the stored token from the keyring and from OpenBao (when configured); where it was removed from.

    🇧🇷 Apaga o token guardado do chaveiro e do OpenBao (quando configurado); de onde foi removido.
    """
    keychain = keychain if keychain is not None else Keychain()
    removed = [f"keyring ({keychain.name})"] if keychain.delete(settings.vault_url) else []
    if settings.openbao_addr:
        target = openbao if openbao is not None else OpenBaoTokenStore(settings)
        if target.delete():
            removed.append(target.location)
    return removed
