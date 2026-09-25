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
from types import TracebackType
from typing import TYPE_CHECKING, Any

from diagnos.crypto import EntropyMixer
from diagnos.errors import SessionExpiredError
from diagnos.models import ExamRecord, PatientRecord
from diagnos.resources._documents import VersionedDocuments
from diagnos.resources.drives import Drives
from diagnos.resources.exams import Exams
from diagnos.resources.patients import Patients
from diagnos.session.enrollment import PromptCallback
from diagnos.session.manager import SessionManager
from diagnos.session.unseal import OpenBaoStore
from diagnos.transport.config import Settings
from diagnos.transport.http import VaultTransport
from diagnos.transport.token import ServiceAccountToken, redact_api_token

if TYPE_CHECKING:
    from diagnos.session.keyring import Keyring, SessionKeys


def _resolve_settings(settings: Settings | None, token: str | None) -> Settings:
    """🇺🇸 `settings` wins outright; `token` overrides only `DIAGNOS_API_TOKEN` on top of the real environment.

    Routing an explicit `token` through `Settings.from_env` (instead of
    hand-building a `Settings`) means `vault_url`/`sse_c`/OpenBao config
    still come from the environment exactly as they would without `token` —
    a caller passing a token is choosing *which credential* to use, not
    opting out of every other env var.

    🇧🇷 `settings` vence direto; `token` sobrescreve só `DIAGNOS_API_TOKEN` em cima do ambiente de verdade.

    Rotear um `token` explícito por `Settings.from_env` (em vez de montar um
    `Settings` à mão) faz `vault_url`/`sse_c`/config do OpenBao continuarem
    vindo do ambiente exatamente como viriam sem `token` — quem chama
    passando um token está escolhendo *qual credencial* usar, não saindo de
    toda outra variável de ambiente.
    """
    if settings is not None:
        return settings
    if token is not None:
        return Settings.from_env({**os.environ, "DIAGNOS_API_TOKEN": token})
    return Settings.from_env()


def _print_enrollment_prompt_fallback() -> PromptCallback:
    """🇺🇸 A deferred-import wrapper around `SessionManager`'s own `default_prompt`.

    Returning the bound reference this way (instead of importing
    `diagnos.session.manager.default_prompt` at module scope) keeps this
    module's only hard dependency on `session/manager.py` the one class it
    actually orchestrates, `SessionManager` itself — its default keyword
    argument already covers "no `on_prompt` given".

    🇧🇷 O próprio `default_prompt` do `SessionManager` já é um padrão
    sensato; isto só existe para `Diagnos` nunca precisar importá-lo só para
    ler o nome.

    Devolver a referência assim (em vez de importar
    `diagnos.session.manager.default_prompt` no nível do módulo) mantém a
    única dependência forte deste módulo em `session/manager.py` a classe que
    ele de fato orquestra, o próprio `SessionManager` — o argumento nomeado
    padrão dele já cobre "nenhum `on_prompt` foi dado".
    """
    from diagnos.session.manager import default_prompt

    return default_prompt


class Diagnos:
    """🇺🇸 The SDK's entry point: one service account's live connection to one workspace.

    🇧🇷 O ponto de entrada do SDK: a conexão viva de uma service account com um workspace.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        token: str | None = None,
        on_prompt: PromptCallback | None = None,
        auto_unseal: bool | None = None,
        transport: VaultTransport | None = None,
        session: SessionManager | None = None,
    ) -> None:
        """🇺🇸 Builds (or accepts) every layer below `patients`/`exams`/`drives`.

        `transport`/`session` are escape hatches for tests, not something a
        real application ever passes — see `apps/sdk/tests/test_client.py` for the
        pattern (a fake `session` that never touches the network).

        🇧🇷 Constrói (ou aceita) toda camada abaixo de `patients`/`exams`/`drives`.

        `transport`/`session` são válvulas de escape para teste, nunca algo
        que uma aplicação de verdade passa — ver `apps/sdk/tests/test_client.py`
        para o padrão (um `session` falso que nunca toca a rede).
        """
        self._settings = _resolve_settings(settings, token)
        self._token = ServiceAccountToken.parse(self._settings.api_token)
        self._entropy = EntropyMixer()
        self._transport = (
            transport
            if transport is not None
            else VaultTransport(
                self._settings,
                self._token,
                session_keys=self._current_session_keys,
                on_seed=self._entropy.mix,
            )
        )

        if session is not None:
            self._session = session
        else:
            auto_unseal_enabled = auto_unseal if auto_unseal is not None else self._settings.openbao_addr is not None
            store = (
                OpenBaoStore(self._settings, workspace_id=self._token.workspace_id, account_id=self._token.account_id)
                if auto_unseal_enabled
                else None
            )
            session_kwargs: dict[str, Any] = {"store": store}
            if on_prompt is not None:
                session_kwargs["on_prompt"] = on_prompt
            else:
                session_kwargs["on_prompt"] = _print_enrollment_prompt_fallback()
            self._session = SessionManager(self._settings, self._token, self._transport, **session_kwargs)

        self._patients: Patients | None = None
        self._exams: Exams | None = None
        self._drives: Drives | None = None

    def _current_session_keys(self) -> SessionKeys | None:
        """🇺🇸 The callback `VaultTransport` polls before signing every request.

        🇧🇷 O callback que `VaultTransport` consulta antes de assinar toda requisição.
        """
        return self._session.session_keys()

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

    @property
    def workspace_id(self) -> str:
        """🇺🇸 This service account's workspace, read from its token.

        🇧🇷 O workspace desta service account, lido do token dela.
        """
        return self._token.workspace_id

    @property
    def account_id(self) -> str:
        """🇺🇸 This service account's owning account, read from its token.

        🇧🇷 A conta dona desta service account, lida do token dela.
        """
        return self._token.account_id

    @property
    def name(self) -> str:
        """🇺🇸 The service account's human-readable name (`slug@<workspace_id>.diagnos.health`).

        🇧🇷 O nome legível da service account (`slug@<workspace_id>.diagnos.health`).
        """
        return self._token.name

    @property
    def key_id(self) -> str:
        """🇺🇸 Id of the token's key pair — what an admin rotates or revokes.

        🇧🇷 Id do par de chaves do token — o que um admin rotaciona ou revoga.
        """
        return self._token.key_id

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
            documents = VersionedDocuments(
                self._transport,
                self._keyring_provider,
                self._entropy,
                workspace_id=self.workspace_id,
                resource="patients",
                record_model=PatientRecord,
                settings=self._settings,
            )
            self._patients = Patients(documents)
        return self._patients

    @property
    def exams(self) -> Exams:
        """🇺🇸 `vault.exams` — built once, on first access.

        🇧🇷 `vault.exams` — construído uma vez, no primeiro acesso.
        """
        if self._exams is None:
            documents = VersionedDocuments(
                self._transport,
                self._keyring_provider,
                self._entropy,
                workspace_id=self.workspace_id,
                resource="exams",
                record_model=ExamRecord,
                settings=self._settings,
            )
            self._exams = Exams(documents)
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
                settings=self._settings,
            )
        return self._drives

    def unlock(self) -> Keyring:
        """🇺🇸 Enrolls (or restores from OpenBao) and returns the live `Keyring`; idempotent.

        🇧🇷 Faz enrollment (ou restaura do OpenBao) e devolve o `Keyring` vivo; idempotente.
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

        Exiting a `with` block means "this process is done talking to the
        vault right now", not "revoke this session forever" — an
        auto-unsealing worker that restarts a minute later should restore
        the very session this process was using, not be forced to enroll
        again because closing merely freed a socket. Call `lock()` yourself
        when the intent really is to end the session.

        🇧🇷 Fecha os clients HTTP mas deliberadamente não faz `lock()` da sessão.

        Sair de um bloco `with` significa "este processo terminou de falar
        com o cofre agora", não "revogue esta sessão para sempre" — um
        worker com auto-unseal que reinicia um minuto depois deveria
        restaurar a mesma sessão que este processo usava, não ser forçado a
        um novo enrollment só porque fechar liberou um socket. Chame
        `lock()` você mesmo quando a intenção for de fato encerrar a sessão.
        """
        self.close()

    def __repr__(self) -> str:
        """🇺🇸 Never the token — only what identifies the workspace/account.

        🇧🇷 Nunca o token — só o que identifica workspace/conta.
        """
        return (
            f"Diagnos(workspace_id={self.workspace_id!r}, account_id={self.account_id!r}, "
            f"name={self._token.name!r}, api_token={redact_api_token(self._token.raw)!r})"
        )
