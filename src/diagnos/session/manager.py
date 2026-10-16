"""🇺🇸 `SessionManager`: the one object that turns "I have a token" into "I have a live, usable session".

Everything else in `session/` is a building block — `open_token_session()`
asks the vault for a session with the token's signature, `enroll()` does the
legacy `apikey-` approval dance, `OpenBaoStore` does one KV path. This
module is where they compose into the lifecycle a caller actually wants:
try to resume silently, open a session (with the token; only the legacy
token still needs a human approval), remember the result if asked to, and
tear it all down cleanly on `lock()`.

🇧🇷 `SessionManager`: o objeto que transforma "eu tenho um token" em "eu
tenho uma sessão viva e utilizável".

Tudo mais em `session/` é um bloco de construção — `open_token_session()`
pede uma sessão ao cofre com a assinatura do token, `enroll()` faz a dança
de aprovação do legado `apikey-`, `OpenBaoStore` faz um path de KV. Este
módulo é onde eles se compõem no ciclo de vida que quem chama de fato quer:
tentar retomar em silêncio, abrir uma sessão (com o token; só o token legado
ainda precisa de aprovação humana), lembrar o resultado se pedido, e
desmontar tudo direito no `lock()`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from diagnos.crypto.hybrid import HybridKeyPair
from diagnos.crypto.secure import harden_process, warn_if_unlocked
from diagnos.errors import SessionExpiredError
from diagnos.session.enrollment import PromptCallback, enroll
from diagnos.session.keyring import Keyring, SessionKeys
from diagnos.session.prompt import default_prompt as default_prompt
from diagnos.session.token_session import lock_path, open_token_session
from diagnos.session.unseal import OpenBaoStore, UnsealedState

# 🇺🇸 Same reasoning as `enrollment.py`/`unseal.py`: `diagnos.transport`
# eagerly imports `diagnos.session.keyring`, so importing any of its
# submodules at module scope here would close an import cycle. `Settings`,
# `VaultTransport` and `RequestIdentity` are only ever used as type
# hints — every real use below is a duck-typed call/attribute the manager
# receives already constructed.
# 🇧🇷 Mesmo raciocínio de `enrollment.py`/`unseal.py`: `diagnos.transport`
# importa `diagnos.session.keyring` de forma antecipada, então importar
# qualquer submódulo dele aqui no nível do módulo fecharia um ciclo.
# `Settings`, `VaultTransport` e `RequestIdentity` só são usados como
# type hint — todo uso real abaixo é uma chamada/atributo duck-typed que o
# manager recebe já construído.
if TYPE_CHECKING:
    from diagnos.transport.config import Settings
    from diagnos.transport.http import VaultTransport
    from diagnos.transport.identity import RequestIdentity
    from diagnos.transport.service_token import DiagnosToken

logger = logging.getLogger("diagnos")

# 🇺🇸 `docs/PROTOCOL.md §5`: ends a session; signed because a session must
# already exist to lock, unlike the routes that open one.
# 🇧🇷 `docs/PROTOCOL.md §5`: encerra uma sessão; assinado porque uma sessão
# já precisa existir para travar, diferente das rotas que abrem uma.
_LOCK_PATH = "/api/external/v1/session/lock"


class SessionManager:
    """🇺🇸 Orchestrates unlock (restore, or open a session), the live `Keyring`, and `lock()`.

    🇧🇷 Orquestra o unlock (restaurar, ou abrir uma sessão), o `Keyring` vivo, e o `lock()`.
    """

    def __init__(
        self,
        settings: Settings,
        token: RequestIdentity,
        transport: VaultTransport,
        *,
        on_prompt: PromptCallback = default_prompt,
        store: OpenBaoStore | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
    ) -> None:
        """🇺🇸 `store` is optional (`docs/PROTOCOL.md §11`): without one, every `unlock()` opens a fresh session.

        🇧🇷 `store` é opcional (`docs/PROTOCOL.md §11`): sem ele, todo `unlock()` abre uma sessão nova.
        """
        self._settings = settings
        self._token = token
        self._transport = transport
        self._on_prompt = on_prompt
        self._store = store
        self._sleep = sleep
        self._now = now
        # 🇺🇸 Public: *which* pair is in use is no secret, its bytes are (`zeroize()`). `keyring` is validated below.
        # 🇧🇷 Público: *qual* par está em uso não é segredo, os bytes são (`zeroize()`). `keyring` é validado abaixo.
        self.keypair: HybridKeyPair | None = None
        self._keyring: Keyring | None = None
        self._hardened = False

    @property
    def keyring(self) -> Keyring:
        """🇺🇸 The live `Keyring`, or `SessionExpiredError` if there is none or it has lapsed.

        Checking `is_valid` here, not just "is it set", is what stops a
        caller from silently signing requests with a session that is about
        to be rejected by the vault anyway — better to fail on the SDK side
        with a clear exception than to let `VaultTransport` turn it into a
        401 two layers down.

        🇧🇷 O `Keyring` vivo, ou `SessionExpiredError` se não houver um ou se
        ele tiver vencido.

        Conferir `is_valid` aqui, não só "está definido", é o que impede
        quem chama de assinar requisições em silêncio com uma sessão prestes
        a ser rejeitada pelo cofre de qualquer jeito — melhor falhar do lado
        do SDK com uma exceção clara do que deixar o `VaultTransport`
        transformar isso num 401 duas camadas abaixo.
        """
        if self._keyring is None or not self._keyring.session.is_valid(now=int(self._now())):
            raise SessionExpiredError(
                "🇺🇸 no live session; call unlock() (which opens one, or restores it from OpenBao) "
                "first. "
                "🇧🇷 nenhuma sessão viva; chame unlock() (que abre uma, ou a restaura do "
                "OpenBao) primeiro."
            )
        return self._keyring

    def session_keys(self) -> SessionKeys | None:
        """🇺🇸 The provider `VaultTransport(session_keys=...)` expects: never raises, `None` when unusable.

        Deliberately the mirror image of the `keyring` property: a transport
        asks for keys on every signed request and has its own recovery path
        for "none available" (`SessionExpiredError`, `session/keyring.py`
        `VaultTransport._send_once`), so this method hands back a plain
        `None` instead of raising a second exception on top of that one.

        🇧🇷 O provedor que `VaultTransport(session_keys=...)` espera: nunca
        lança, `None` quando inutilizável.

        De propósito o espelho da property `keyring`: um transporte pede
        chaves em toda requisição assinada e já tem seu próprio caminho de
        recuperação para "nenhuma disponível" (`SessionExpiredError`,
        `VaultTransport._send_once`), então este método devolve um `None`
        simples em vez de lançar uma segunda exceção em cima daquela.
        """
        if self._keyring is None:
            return None
        session = self._keyring.session
        if not session.is_valid(now=int(self._now())):
            return None
        return session

    def _harden_once(self) -> None:
        """🇺🇸 Process hardening, right before the first secret exists, once per manager.

        Done here and not at import time: importing a library must never
        change process-wide state, but *unlocking* is the explicit moment
        the caller decides this process will hold clinical keys — the report
        (what took effect on this platform) goes to the debug log.

        🇧🇷 Hardening do processo, logo antes de o primeiro segredo existir, uma vez por manager.

        Feito aqui e não no import: importar uma biblioteca nunca deve mudar
        estado do processo inteiro, mas *desbloquear* é o momento explícito
        em que quem chama decide que este processo vai segurar chaves
        clínicas — o relatório (o que teve efeito nesta plataforma) vai para
        o log de debug.
        """
        if self._hardened or not self._settings.harden_process:
            return
        self._hardened = True
        logger.debug("process hardening: %s", harden_process())

    def unlock(self) -> Keyring:
        """🇺🇸 Restore from `store` if it holds a still-valid session; otherwise open one and (maybe) save it.

        🇧🇷 Restaura de `store` se ele guardar uma sessão ainda válida; senão, abre uma e (talvez) a salva.
        """
        self._harden_once()
        if self._store is not None:
            restored = self._store.restore(now=int(self._now()))
            if restored is not None and restored.keyring.session.is_valid(now=int(self._now())):
                self.keypair = restored.keypair
                self._keyring = restored.keyring
                warn_if_unlocked()
                return self.keyring

        keypair, keyring = self._open()
        self.keypair = keypair
        self._keyring = keyring
        if self._store is not None:
            self._store.save(UnsealedState(keypair=keypair, keyring=keyring))
        warn_if_unlocked()
        return self.keyring

    def _hybrid_token(self) -> DiagnosToken | None:
        """🇺🇸 The service account token, or `None` for the legacy `apikey-` one. 🇧🇷 O token, ou `None` no legado."""
        # 🇺🇸 Deferred: `diagnos.transport` imports this package while it initializes (see above).
        # 🇧🇷 Adiado: o `diagnos.transport` importa este pacote enquanto inicializa (ver acima).
        from diagnos.transport.service_token import DiagnosToken

        return self._token if isinstance(self._token, DiagnosToken) else None

    def _open(self) -> tuple[HybridKeyPair, Keyring]:
        """🇺🇸 A token opens its own session; the legacy `apikey-` token enrolls with a fresh pair and a human.

        🇧🇷 Um token abre a própria sessão; o token legado `apikey-` faz enrollment com par novo e uma pessoa.
        """
        token = self._hybrid_token()
        if token is not None:
            keypair = token.keypair()
            try:
                return keypair, open_token_session(self._transport, token, keypair)
            except BaseException:
                keypair.zeroize()
                raise
        keypair = HybridKeyPair.generate()
        keyring = enroll(
            self._transport, self._token, keypair, on_prompt=self._on_prompt, sleep=self._sleep, now=self._now
        )
        return keypair, keyring

    def lock(self) -> None:
        """🇺🇸 Best-effort server-side end, then unconditional local teardown.

        The `session/lock` call is best-effort on purpose: a network error
        or an already-expired session (401) still means the caller's intent
        — "I am done with this session" — has to succeed locally. Zeroizing
        happens regardless of whether the server call did.

        🇧🇷 Encerramento do lado do servidor best-effort, depois desmonte
        local incondicional.

        A chamada a `session/lock` é best-effort de propósito: um erro de
        rede ou uma sessão já expirada (401) ainda significam que a intenção
        de quem chama — "terminei com esta sessão" — precisa dar certo
        localmente. A zeroização acontece independente da chamada ao
        servidor ter dado certo.
        """
        token = self._hybrid_token()
        try:
            self._transport.post(lock_path(token.workspace_id) if token else _LOCK_PATH, signed=True)
        except Exception:
            logger.debug("session/lock failed; ending the session locally anyway", exc_info=True)
        self._discard()

    def reopen(self) -> bool:
        """🇺🇸 After the vault lost the session (`SessionNotFound`): a token opens a new one; the legacy one cannot.

        One signed request, no human — so `VaultTransport` may retry the call
        once. The legacy token would need an approval, so it says `False` and
        the error reaches the caller.

        🇧🇷 Depois que o cofre perdeu a sessão (`SessionNotFound`): um token abre outra; o legado não consegue.

        Uma requisição assinada, sem pessoa — então o `VaultTransport` pode
        repetir a chamada uma vez. O token legado precisaria de aprovação,
        então diz `False` e o erro chega a quem chamou.
        """
        if self._hybrid_token() is None:
            return False
        self._discard()
        self.unlock()
        return True

    def _discard(self) -> None:
        """🇺🇸 Wipe the local session, the key pair and the OpenBao copy. 🇧🇷 Apaga a sessão local, o par e a cópia."""
        if self._store is not None:
            self._store.clear()
        if self._keyring is not None:
            self._keyring.zeroize()
        if self.keypair is not None:
            self.keypair.zeroize()
        self._keyring = None
        self.keypair = None
