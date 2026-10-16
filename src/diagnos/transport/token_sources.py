"""🇺🇸 Where the token comes from, in order — the environment first, then the stores.

1. an explicit `token=` / `--token` (a `dgn_sk1_` token, or the legacy
   `apikey-` one);
2. `DIAGNOS_TOKEN` — CI and ephemeral containers, where a secret arrives as
   an environment variable;
3. `DIAGNOS_API_TOKEN` — the deprecated `apikey-` token, accepted until
   2027-04-15: anything set in the environment beats any store, so what a
   shell exports is always what runs;
4. the system keyring (`diagnos login`), only a backend that encrypts at
   rest, and only when the caller asks (`keyring=True`: the CLI, or
   `Settings.from_env()` on the real environment);
5. OpenBao, `<OPENBAO_PATH_PREFIX>/token`, when `OPENBAO_ADDR` is set — how
   a server (`diagnos-api`) gets it.

A value in the wrong variable is refused with the right one named. The text
is passed straight from the mapping to `DiagnosToken.parse`: no frame here
keeps a copy of it.

🇧🇷 De onde o token vem, em ordem — o ambiente primeiro, depois os cofres.

1. um `token=` / `--token` explícito (um token `dgn_sk1_`, ou o legado
   `apikey-`);
2. `DIAGNOS_TOKEN` — CI e containers efêmeros, onde um segredo chega como
   variável de ambiente;
3. `DIAGNOS_API_TOKEN` — o token `apikey-` obsoleto, aceito até 2027-04-15:
   tudo que está no ambiente vence qualquer cofre, então o que um shell
   exporta é sempre o que roda;
4. o chaveiro do sistema (`diagnos login`), só backend que cifra em repouso,
   e só quando quem chama pede (`keyring=True`: a CLI, ou o
   `Settings.from_env()` no ambiente real);
5. o OpenBao, `<OPENBAO_PATH_PREFIX>/token`, quando `OPENBAO_ADDR` está
   definida — como um servidor (`diagnos-api`) o obtém.

Um valor na variável errada é recusado com a certa nomeada. O texto vai
direto do mapeamento para `DiagnosToken.parse`: nenhum quadro daqui guarda
cópia dele.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

from diagnos.errors import ConfigError
from diagnos.token_store import Keychain

from .service_token import ENV_VAR, DiagnosToken
from .token_text import PANEL

LEGACY_VAR: Final = "DIAGNOS_API_TOKEN"
NOT_CONFIGURED: Final = (
    "🇺🇸 No diagnos token found. Run `diagnos login` (it keeps the token in the system keyring, or in OpenBao), "
    f"or set {ENV_VAR} in CI and containers. Create a token under {PANEL}. "
    "🇧🇷 Nenhum token do diagnos encontrado. Rode `diagnos login` (ele guarda o token no chaveiro do sistema, ou "
    f"no OpenBao), ou defina {ENV_VAR} em CI e containers. Crie um token em {PANEL}."
)


@dataclass(frozen=True)
class FoundIdentity:
    """🇺🇸 What the sources named: a token, or the legacy `apikey-` text. 🇧🇷 O que as fontes nomearam."""

    token: DiagnosToken | None = None
    api_token: str | None = None


def _legacy(text: str, source: str) -> FoundIdentity:
    """🇺🇸 The legacy token, unless it is a `dgn_sk1_` token in the wrong place. 🇧🇷 O token legado, salvo engano."""
    if text.lstrip().startswith("dgn_sk1_"):
        raise ConfigError(
            f"🇺🇸 {source} holds a service account token ('dgn_sk1_…'); put it in {ENV_VAR} instead. "
            f"🇧🇷 {source} contém um token de conta de serviço ('dgn_sk1_…'); coloque-o em {ENV_VAR}."
        )
    return FoundIdentity(api_token=text)


def explicit(text: str, source: str) -> FoundIdentity:
    """🇺🇸 `token=` / `--token`: a `dgn_sk1_` token, or the legacy `apikey-` one. 🇧🇷 Um token, ou o legado."""
    try:
        if text.lstrip().startswith("apikey-"):
            return FoundIdentity(api_token=text)
        return FoundIdentity(token=DiagnosToken.parse(text, source=source))
    finally:
        # 🇺🇸 Gone before the frame is captured by a traceback. 🇧🇷 Some antes de um traceback capturar o quadro.
        del text


def _from_store(load: Callable[[], str | None], source: str) -> DiagnosToken | None:
    """🇺🇸 Parse what a store holds; the text leaves this frame before any error propagates.

    🇧🇷 Lê o que um cofre guarda; o texto sai deste quadro antes de qualquer erro propagar.
    """
    stored = load()
    if stored is None:
        return None
    try:
        return DiagnosToken.parse(stored, source=source)
    finally:
        del stored


def find_identity(
    env: Mapping[str, str],
    *,
    vault_url: str,
    keychain: Keychain | None,
    openbao: Callable[[], str | None] | None,
    openbao_location: str = "OpenBao",
) -> FoundIdentity:
    """🇺🇸 Apply the order in the module docstring; an empty result means nothing was configured.

    `keychain=None` skips the keyring; `openbao=None` skips OpenBao (no
    `OPENBAO_ADDR`).

    🇧🇷 Aplica a ordem da docstring do módulo; resultado vazio significa que nada foi configurado.

    `keychain=None` pula o chaveiro; `openbao=None` pula o OpenBao (sem
    `OPENBAO_ADDR`).
    """
    if env.get(ENV_VAR):
        return FoundIdentity(token=DiagnosToken.parse(env[ENV_VAR], source=ENV_VAR))
    if env.get(LEGACY_VAR):
        return _legacy(env[LEGACY_VAR], LEGACY_VAR)
    if keychain is not None and (found := _from_store(lambda: keychain.load(vault_url), "keyring")) is not None:
        return FoundIdentity(token=found)
    if openbao is not None and (found := _from_store(openbao, openbao_location)) is not None:
        return FoundIdentity(token=found)
    return FoundIdentity()
