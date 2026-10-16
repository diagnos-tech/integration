"""🇺🇸 `Diagnos`: the one object an application constructs — everything else hangs off it.

`vault = Diagnos(); vault.patients.list()` is the whole point of this
module: every other file in this package exists to make that call correct
and safe, and this is where they compose. Nothing below does cryptography or
speaks HTTP directly — it wires together a `VaultTransport`, a
`SessionManager` (or a caller-supplied stand-in, for tests) and one lazily
built resource per kind (`patients`/`exams`/`drives`), all sharing the same
`EntropyMixer` so the server's response seed (`docs/PROTOCOL.md §4`) reaches
every DEK and node key this process ever generates.

🇧🇷 `Diagnos`: o único objeto que uma aplicação constrói — todo o resto pendura nele.

`vault = Diagnos(); vault.patients.list()` é o ponto inteiro deste módulo:
todo outro arquivo deste pacote existe para essa chamada ser correta e
segura, e é aqui que eles se compõem. Nada abaixo faz criptografia ou fala
HTTP direto — isto conecta um `VaultTransport`, um `SessionManager` (ou um
substituto fornecido por quem chama, para testes) e um recurso por tipo
(`patients`/`exams`/`drives`) construído de forma preguiçosa, todos
compartilhando o mesmo `EntropyMixer` para a semente de resposta do servidor
(`docs/PROTOCOL.md §4`) alcançar toda DEK e chave de nó que este processo já
gerar.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from types import TracebackType
from typing import TYPE_CHECKING, Any

from diagnos import _client_wiring
from diagnos._client_identity import IdentityView, TokenLike, resolve_identity
from diagnos._client_wiring import _print_enrollment_prompt_fallback, _resolve_settings
from diagnos.crypto import EntropyMixer
from diagnos.errors import SessionExpiredError
from diagnos.resources.drives import Drives
from diagnos.resources.exams import Exams
from diagnos.resources.patients import Patients
from diagnos.session.enrollment import PromptCallback
from diagnos.session.manager import SessionManager
from diagnos.session.unseal import OpenBaoStore
from diagnos.transport.config import Settings
from diagnos.transport.http import VaultTransport

if TYPE_CHECKING:
    from diagnos.session.keyring import Keyring, SessionKeys


class Diagnos(IdentityView):
    """🇺🇸 The SDK's entry point: one service account's live connection to one workspace.

    `Diagnos()` finds the token in `DIAGNOS_TOKEN`, then in the system keyring
    (`diagnos login`), then in OpenBao (`OPENBAO_ADDR`) —
    `transport/token_sources.py`; `Diagnos.from_env()` reads the environment
    only; `Diagnos(token=...)` takes one explicitly. The identity properties
    (`workspace_id`, `key_id`, `identity`…) come from `IdentityView`.

    🇧🇷 O ponto de entrada do SDK: a conexão viva de uma service account com um workspace.

    `Diagnos()` acha o token em `DIAGNOS_TOKEN`, depois no chaveiro do sistema
    (`diagnos login`), depois no OpenBao (`OPENBAO_ADDR`) —
    `transport/token_sources.py`; `Diagnos.from_env()` lê só o ambiente;
    `Diagnos(token=...)` recebe um explícito. As propriedades de identidade
    (`workspace_id`, `key_id`, `identity`…) vêm de `IdentityView`.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        token: TokenLike | None = None,
        on_prompt: PromptCallback | None = None,
        auto_unseal: bool | None = None,
        transport: VaultTransport | None = None,
        session: SessionManager | None = None,
    ) -> None:
        """🇺🇸 Builds (or accepts) every layer below `patients`/`exams`/`drives`.

        `token` is a `DiagnosToken` or its text (`dgn_sk1_…`); the deprecated
        `apikey-` text is still accepted, with a `LegacyTokenWarning`.
        `transport`/`session` are escape hatches for tests, not something a
        real application ever passes — see `apps/sdk/tests/test_client.py`.

        🇧🇷 Constrói (ou aceita) toda camada abaixo de `patients`/`exams`/`drives`.

        `token` é um `DiagnosToken` ou o texto dele (`dgn_sk1_…`); o texto
        obsoleto `apikey-` ainda é aceito, com um `LegacyTokenWarning`.
        `transport`/`session` são válvulas de escape para teste, nunca algo
        que uma aplicação de verdade passa — ver `apps/sdk/tests/test_client.py`.
        """
        self._settings = _resolve_settings(settings, token)
        del token
        self._identity = resolve_identity(self._settings)
        self._entropy = EntropyMixer()
        self._transport = (
            transport
            if transport is not None
            else VaultTransport(
                self._settings,
                self._identity,
                session_keys=self._current_session_keys,
                on_seed=self._entropy.mix,
                on_session_lost=self._reopen_session,
            )
        )

        if session is not None:
            self._session = session
        else:
            auto_unseal_enabled = auto_unseal if auto_unseal is not None else self._settings.openbao_addr is not None
            store = (
                OpenBaoStore(self._settings, workspace_id=self.workspace_id, account_id=self.account_id or self.key_id)
                if auto_unseal_enabled
                else None
            )
            resolved_prompt = on_prompt if on_prompt is not None else _print_enrollment_prompt_fallback()
            session_kwargs: dict[str, Any] = {"store": store, "on_prompt": resolved_prompt}
            self._session = SessionManager(self._settings, self._identity, self._transport, **session_kwargs)

        self._patients: Patients | None = None
        self._exams: Exams | None = None
        self._drives: Drives | None = None

    def _current_session_keys(self) -> SessionKeys | None:
        """🇺🇸 The callback `VaultTransport` polls before signing every request.

        🇧🇷 O callback que `VaultTransport` consulta antes de assinar toda requisição.
        """
        return self._session.session_keys()

    def _reopen_session(self) -> bool:
        """🇺🇸 `VaultTransport`'s hook when the vault lost the session: a token opens a new one in place.

        🇧🇷 O gancho do `VaultTransport` quando o cofre perdeu a sessão: um token abre outra no lugar.
        """
        return self._session.reopen()

    def _keyring_provider(self) -> Keyring:
        """🇺🇸 The live `Keyring`, auto-unlocking on first use so `vault.patients.list()` just works.

        This is the one place laziness is deliberate: `unlock()` is
        documented as idempotent (`session/manager.py`), so paying for it on
        first resource access — instead of forcing every caller to remember
        an explicit `unlock()` — is what makes the "30 seconds to your first
        `list()`" README example true without a `with` block.

        🇧🇷 O `Keyring` vivo, com auto-unlock no primeiro uso para `vault.patients.list()` simplesmente funcionar.

        Este é o único lugar em que a preguiça é deliberada: `unlock()` é
        documentado como idempotente (`session/manager.py`), então pagar por
        ele no primeiro acesso a um recurso — em vez de forçar quem chama a
        lembrar de um `unlock()` explícito — é o que torna o exemplo do
        README "30 segundos até o primeiro `list()`" verdadeiro sem um bloco
        `with`.
        """
        try:
            keyring = self._session.keyring
        except SessionExpiredError:
            keyring = None
        return keyring if keyring is not None else self._session.unlock()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, **options: Any) -> Diagnos:
        """🇺🇸 The token from `DIAGNOS_TOKEN` (or OpenBao, with `OPENBAO_ADDR`), never the keyring; `options` go on.

        `Diagnos()` also looks in the system keyring; this is the call for CI,
        containers and servers, where what the environment says is all there is.

        🇧🇷 O token de `DIAGNOS_TOKEN` (ou do OpenBao, com `OPENBAO_ADDR`), nunca o chaveiro; `options` seguem.

        `Diagnos()` também procura no chaveiro do sistema; esta é a chamada para
        CI, containers e servidores, onde o que o ambiente diz é tudo que há.
        """
        return cls(Settings.from_env(os.environ if env is None else env, keyring=False), **options)

    @property
    def security_groups(self) -> list[str]:
        """🇺🇸 Ids of every security group this session holds a DEK for; `[]` before `unlock()`.

        🇧🇷 Ids de todo security group para o qual esta sessão tem uma DEK; `[]` antes de `unlock()`.
        """
        try:
            keyring = self._session.keyring
        except SessionExpiredError:
            keyring = None
        return keyring.security_group_ids if keyring is not None else []

    @property
    def patients(self) -> Patients:
        """🇺🇸 `vault.patients` — built once, on first access.

        🇧🇷 `vault.patients` — construído uma vez, no primeiro acesso.
        """
        if self._patients is None:
            self._patients = _client_wiring._build_patients(
                self._transport,
                self._keyring_provider,
                self._entropy,
                workspace_id=self.workspace_id,
                time_precision=self._settings.time_precision,
            )
        return self._patients

    @property
    def exams(self) -> Exams:
        """🇺🇸 `vault.exams` — built once, on first access.

        🇧🇷 `vault.exams` — construído uma vez, no primeiro acesso.
        """
        if self._exams is None:
            self._exams = _client_wiring._build_exams(
                self._transport,
                self._keyring_provider,
                self._entropy,
                workspace_id=self.workspace_id,
                time_precision=self._settings.time_precision,
            )
        return self._exams

    @property
    def drives(self) -> Drives:
        """🇺🇸 `vault.drives` — built once, on first access.

        🇧🇷 `vault.drives` — construído uma vez, no primeiro acesso.
        """
        if self._drives is None:
            self._drives = Drives(
                self._transport,
                self._keyring_provider,
                self._entropy,
                workspace_id=self.workspace_id,
            )
        return self._drives

    def unlock(self) -> Keyring:
        """🇺🇸 Opens a session with the token (or restores it from OpenBao) and returns the live `Keyring`.

        🇧🇷 Abre uma sessão com o token (ou a restaura do OpenBao) e devolve o `Keyring` vivo.
        """
        return self._session.unlock()

    def lock(self) -> None:
        """🇺🇸 Ends the session, best-effort server-side, and always wipes local key material.

        Unlike `close()`, this is never called automatically — see the
        `__exit__` docstring for why.

        🇧🇷 Encerra a sessão, best-effort do lado do servidor, e sempre apaga o material de chave local.

        Diferente de `close()`, isto nunca é chamado automaticamente — veja
        a docstring de `__exit__` para o porquê.
        """
        self._session.lock()

    def close(self) -> None:
        """🇺🇸 Closes the underlying HTTP clients. Does not `lock()` — see `__exit__`.

        🇧🇷 Fecha os clients HTTP internos. Não faz `lock()` — veja `__exit__`.
        """
        self._transport.close()

    def __enter__(self) -> Diagnos:
        """🇺🇸 `with Diagnos(...) as vault:` unlocks on entry.

        🇧🇷 `with Diagnos(...) as vault:` desbloqueia na entrada.
        """
        self.unlock()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """🇺🇸 Closes the HTTP clients but deliberately does not `lock()` the session.

        Leaving a `with` block means "done talking to the vault for now", not
        "revoke this session": another process with the same token keeps the
        session the vault shares with it. Call `lock()` to end it.

        🇧🇷 Fecha os clients HTTP mas deliberadamente não faz `lock()` da sessão.

        Sair de um bloco `with` significa "terminei de falar com o cofre por
        ora", não "revogue esta sessão": outro processo com o mesmo token
        mantém a sessão que o cofre divide com ele. Chame `lock()` para encerrá-la.
        """
        self.close()

    def __repr__(self) -> str:
        """🇺🇸 Never the seed or the token — only what identifies the workspace and the key.

        🇧🇷 Nunca a semente nem o token — só o que identifica o workspace e a chave.
        """
        return f"Diagnos(workspace_id={self.workspace_id!r}, {self._identity_repr()})"
